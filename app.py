import csv
import os
import smtplib
import ssl
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from io import StringIO
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, render_template, request


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "rsvps.db"))
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

app = Flask(__name__, static_url_path="/static")

GAME_THRESHOLD = 10
GAME_CHALLENGES = [
    "Inicia conga",
    "Inicia limbo",
    "Coge a alguien sentado en tus hombros",
    "Inicia un aplauso colectivo",
    "Inicia un pasillito y consigue que pasen los casados por el medio",
    "Inicia una macarena",
]
GAME_INSTRUCTION = (
    "Inicia el reto el primero y si consigues que te sigan recibirás un premio."
)
ALLOW_MULTIPLE_GAME_VOTES = True


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    stripped = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return " ".join(stripped.lower().split())


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def init_db() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                attending INTEGER NOT NULL,
                address TEXT,
                bus INTEGER NOT NULL,
                allergies TEXT,
                song TEXT,
                message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                votes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS song_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                ip TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(ip)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                challenge_index INTEGER NOT NULL,
                round_index INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_index INTEGER NOT NULL,
                ip TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(round_index, ip)
            )
            """
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(rsvps)").fetchall()
        }
        missing = {
            "address": "TEXT",
            "allergies": "TEXT",
            "message": "TEXT",
        }
        for column, column_type in missing.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE rsvps ADD COLUMN {column} {column_type}"
                )
        state = conn.execute("SELECT id FROM game_state WHERE id = 1").fetchone()
        if not state:
            created_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            conn.execute(
                """
                INSERT INTO game_state (id, challenge_index, round_index, updated_at)
                VALUES (1, 0, 1, ?)
                """,
                (created_at,),
            )
        conn.execute(
            """
            INSERT OR IGNORE INTO site_settings (key, value)
            VALUES ('mischief_enabled', '1')
            """
        )
        conn.commit()


def db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM site_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if not row:
        return default
    return row["value"]


def admin_key_ok(key: str) -> bool:
    return bool(ADMIN_KEY) and key == ADMIN_KEY


def build_game_state(conn: sqlite3.Connection, ip: Optional[str] = None) -> dict:
    row = conn.execute(
        "SELECT challenge_index, round_index FROM game_state WHERE id = 1"
    ).fetchone()
    if not row:
        raise RuntimeError("Game state missing")

    challenge_index = int(row["challenge_index"])
    round_index = int(row["round_index"])
    count_row = conn.execute(
        "SELECT COUNT(*) FROM game_votes WHERE round_index = ?",
        (round_index,),
    ).fetchone()
    count = int(count_row[0]) if count_row else 0
    remaining = max(0, GAME_THRESHOLD - count)
    challenge = GAME_CHALLENGES[challenge_index % len(GAME_CHALLENGES)]
    challenge_active = count >= GAME_THRESHOLD

    already_voted = False
    if ip and not ALLOW_MULTIPLE_GAME_VOTES:
        vote_row = conn.execute(
            "SELECT 1 FROM game_votes WHERE round_index = ? AND ip = ?",
            (round_index, ip),
        ).fetchone()
        already_voted = bool(vote_row)

    return {
        "count": count,
        "remaining": remaining,
        "threshold": GAME_THRESHOLD,
        "challenge_active": challenge_active,
        "challenge": challenge,
        "instruction": GAME_INSTRUCTION,
        "round_index": round_index,
        "challenge_index": challenge_index,
        "already_voted": already_voted,
    }


def send_email_notification(payload: dict) -> None:
    host = os.getenv("SMTP_HOST")
    to_addr = os.getenv("SMTP_TO")
    if not host or not to_addr:
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    msg = EmailMessage()
    msg["Subject"] = "Nuevo RSVP - Alfonso y Natalia"
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(
        "\n".join(
            [
                "Nuevo invitado registrado:",
                f"Nombre: {payload['name']}",
                f"Asistira: {'Si' if payload['attending'] else 'No'}",
                f"Direccion: {payload['address'] or '-'}",
                f"Necesita autobus: {'Si' if payload['bus'] else 'No'}",
                f"Alergias: {payload['allergies'] or '-'}",
                f"Mensaje: {payload['message'] or '-'}",
                f"Fecha: {payload['created_at']}",
            ]
        )
    )

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls(context=context)
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    except Exception as exc:  # pragma: no cover - avoid crashing on SMTP errors
        print(f"[smtp] {exc}")


@app.get("/")
def index():
    with db_connection() as conn:
        setting = get_setting(conn, "mischief_enabled", "1")
    mischief_enabled = setting != "0"
    return render_template("index.html", mischief_enabled=mischief_enabled)


@app.get("/admin")
def admin():
    key = request.args.get("key", "")
    if admin_key_ok(key):
        with db_connection() as conn:
            setting = get_setting(conn, "mischief_enabled", "1")
        mischief_enabled = setting != "0"
        return render_template(
            "admin.html",
            admin_key=key,
            mischief_enabled=mischief_enabled,
        )
    return render_template("admin_login.html", admin_key_required=bool(ADMIN_KEY))


@app.get("/dj")
def dj_view():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    return render_template("dj.html", admin_key=key)


@app.get("/admin/game")
def admin_game():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    return render_template("game.html", admin_key=key)


@app.get("/api/rsvps")
def list_rsvps():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, attending, address, bus, allergies, message, created_at
            FROM rsvps
            ORDER BY id DESC
            """
        ).fetchall()

    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "attending": bool(row["attending"]),
            "address": row["address"] or "",
            "bus": bool(row["bus"]),
            "allergies": row["allergies"] or "",
            "message": row["message"] or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return jsonify({"items": items})


@app.get("/api/songs")
def list_songs():
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, votes, created_at
            FROM songs
            ORDER BY votes DESC, created_at ASC
            """
        ).fetchall()

    items = [
        {
            "id": row["id"],
            "title": row["title"],
            "votes": int(row["votes"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return jsonify({"items": items})


@app.post("/api/songs")
def create_song():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Título requerido"}), 400
    if len(title) > 120:
        return jsonify({"ok": False, "error": "Título demasiado largo"}), 400
    normalized_title = normalize_text(title)

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ip = client_ip()

    with db_connection() as conn:
        existing_vote = conn.execute(
            "SELECT 1 FROM song_votes WHERE ip = ?",
            (ip,),
        ).fetchone()
        if existing_vote:
            return jsonify({"ok": False, "error": "Ya has votado"}), 400

        existing_rows = conn.execute(
            "SELECT id, title, votes, created_at FROM songs"
        ).fetchall()
        for existing in existing_rows:
            if normalize_text(existing["title"]) == normalized_title:
                conn.execute(
                    "UPDATE songs SET votes = votes + 1 WHERE id = ?",
                    (existing["id"],),
                )
                try:
                    conn.execute(
                        """
                        INSERT INTO song_votes (song_id, ip, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (existing["id"], ip, created_at),
                    )
                except sqlite3.IntegrityError:
                    return jsonify({"ok": False, "error": "Ya has votado"}), 400
                conn.commit()
                return jsonify({"ok": True})

        cursor = conn.execute(
            """
            INSERT INTO songs (title, votes, created_at)
            VALUES (?, ?, ?)
            """,
            (title, 1, created_at),
        )
        try:
            conn.execute(
                """
                INSERT INTO song_votes (song_id, ip, created_at)
                VALUES (?, ?, ?)
                """,
                (cursor.lastrowid, ip, created_at),
            )
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "Ya has votado"}), 400
        conn.commit()

    return jsonify({"ok": True})


@app.post("/api/songs/vote")
def vote_song():
    data = request.get_json(silent=True) or {}
    try:
        song_id = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "ID inv?lido"}), 400
    ip = client_ip()

    with db_connection() as conn:
        existing_vote = conn.execute(
            "SELECT 1 FROM song_votes WHERE ip = ?",
            (ip,),
        ).fetchone()
        if existing_vote:
            return jsonify({"ok": False, "error": "Ya has votado"}), 400
        row = conn.execute(
            "SELECT id FROM songs WHERE id = ?",
            (song_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Canci?n no encontrada"}), 404
        conn.execute(
            "UPDATE songs SET votes = votes + 1 WHERE id = ?",
            (song_id,),
        )
        try:
            conn.execute(
                """
                INSERT INTO song_votes (song_id, ip, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    song_id,
                    ip,
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                ),
            )
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "Ya has votado"}), 400
        conn.commit()

    return jsonify({"ok": True})


@app.post("/api/settings/mischief")
def update_mischief_setting():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled"))
    value = "1" if enabled else "0"
    with db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO site_settings (key, value)
            VALUES ('mischief_enabled', ?)
            """,
            (value,),
        )
        conn.commit()
    return jsonify({"ok": True, "enabled": enabled})


@app.get("/api/game")
def game_state():
    ip = client_ip()
    with db_connection() as conn:
        state = build_game_state(conn, ip=ip)
    return jsonify(state)


@app.post("/api/game/vote")
def vote_game():
    ip = client_ip()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with db_connection() as conn:
        state = build_game_state(conn, ip=ip)
        if state["challenge_active"]:
            return jsonify({"ok": False, "error": "El reto ya está activo"}), 400
        if not ALLOW_MULTIPLE_GAME_VOTES and state["already_voted"]:
            return jsonify({"ok": False, "error": "Ya has pulsado"}), 400
        try:
            stored_ip = ip
            if ALLOW_MULTIPLE_GAME_VOTES:
                stored_ip = f"{ip}-{uuid.uuid4().hex}"
            conn.execute(
                """
                INSERT INTO game_votes (round_index, ip, created_at)
                VALUES (?, ?, ?)
                """,
                (state["round_index"], stored_ip, created_at),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "Ya has pulsado"}), 400
        state = build_game_state(conn, ip=ip)
    return jsonify({"ok": True, "state": state})


@app.post("/api/game/advance")
def advance_game():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    with db_connection() as conn:
        state = build_game_state(conn)
        if not state["challenge_active"]:
            return (
                jsonify({"ok": False, "error": "Aún no se ha alcanzado el reto"}),
                400,
            )
        next_index = (state["challenge_index"] + 1) % len(GAME_CHALLENGES)
        next_round = state["round_index"] + 1
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        conn.execute(
            """
            UPDATE game_state
            SET challenge_index = ?, round_index = ?, updated_at = ?
            WHERE id = 1
            """,
            (next_index, next_round, updated_at),
        )
        conn.commit()
        state = build_game_state(conn)
    return jsonify({"ok": True, "state": state})


@app.post("/api/game/reset")
def reset_game():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE game_state
            SET challenge_index = 0, round_index = 1, updated_at = ?
            WHERE id = 1
            """,
            (updated_at,),
        )
        conn.execute("DELETE FROM game_votes")
        conn.commit()
        state = build_game_state(conn)
    return jsonify({"ok": True, "state": state})


@app.post("/api/rsvp")
def create_rsvp():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Nombre requerido"}), 400

    attending = bool(data.get("attending"))
    address = (data.get("address") or "").strip()
    bus = bool(data.get("bus"))
    allergies = (data.get("allergies") or "").strip()
    message = (data.get("message") or "").strip()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    payload = {
        "name": name,
        "attending": attending,
        "address": address,
        "bus": bus,
        "allergies": allergies,
        "message": message,
        "created_at": created_at,
    }

    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO rsvps (name, attending, address, bus, allergies, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, int(attending), address, int(bus), allergies, message, created_at),
        )
        conn.commit()

    send_email_notification(payload)
    return jsonify({"ok": True})


@app.delete("/api/rsvps/<int:rsvp_id>")
def delete_rsvp(rsvp_id: int):
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)

    with db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM rsvps WHERE id = ?",
            (rsvp_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Invitado no encontrado"}), 404
        conn.execute("DELETE FROM rsvps WHERE id = ?", (rsvp_id,))
        conn.commit()

    return jsonify({"ok": True})


@app.get("/admin/export")
def export_csv():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, attending, address, bus, allergies, message, created_at
            FROM rsvps
            ORDER BY id DESC
            """
        ).fetchall()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["ID", "Nombre", "Asistira", "Direccion", "Autobus", "Alergias", "Mensaje", "Fecha"]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["name"],
                "Si" if row["attending"] else "No",
                row["address"] or "",
                "Si" if row["bus"] else "No",
                row["allergies"] or "",
                row["message"] or "",
                row["created_at"],
            ]
        )

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=rsvps.csv"},
    )


init_db()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5088"))
    app.run(host="0.0.0.0", port=port, debug=True)
