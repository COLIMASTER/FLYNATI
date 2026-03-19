import csv
import html
import os
import smtplib
import ssl
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from io import StringIO
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, render_template, request

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency in local sqlite mode
    psycopg = None
    dict_row = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "rsvps.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

if USE_POSTGRES and psycopg is None:
    raise RuntimeError(
        "DATABASE_URL está definido pero falta psycopg. Añade psycopg[binary] a requirements.txt."
    )

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

DBIntegrityError = psycopg.IntegrityError if USE_POSTGRES else sqlite3.IntegrityError


class DBConnection:
    def __init__(self, raw_conn, use_postgres: bool):
        self.raw_conn = raw_conn
        self.use_postgres = use_postgres

    def execute(self, query: str, params=()):
        if params is None:
            params = ()
        if self.use_postgres:
            query = query.replace("?", "%s")
        return self.raw_conn.execute(query, params)

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()


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


def ensure_setting(conn: DBConnection, key: str, value: str) -> None:
    if USE_POSTGRES:
        conn.execute(
            """
            INSERT INTO site_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT (key) DO NOTHING
            """,
            (key, value),
        )
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO site_settings (key, value)
        VALUES (?, ?)
        """,
        (key, value),
    )


def set_setting(conn: DBConnection, key: str, value: str) -> None:
    if USE_POSTGRES:
        conn.execute(
            """
            INSERT INTO site_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, value),
        )
        return
    conn.execute(
        """
        INSERT OR REPLACE INTO site_settings (key, value)
        VALUES (?, ?)
        """,
        (key, value),
    )


def init_db_postgres() -> None:
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvps (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                attending INTEGER NOT NULL,
                party_type TEXT,
                partner_name TEXT,
                family_members TEXT,
                address TEXT,
                bus INTEGER NOT NULL,
                bus_stop TEXT,
                private_transport INTEGER,
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
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                votes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS song_votes (
                id BIGSERIAL PRIMARY KEY,
                song_id BIGINT NOT NULL,
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
                id INTEGER PRIMARY KEY,
                challenge_index INTEGER NOT NULL,
                round_index INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (id = 1)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_votes (
                id BIGSERIAL PRIMARY KEY,
                round_index INTEGER NOT NULL,
                ip TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(round_index, ip)
            )
            """
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
        ensure_setting(conn, "mischief_enabled", "1")
        ensure_setting(conn, "photos_enabled", "0")
        conn.commit()


def init_db_sqlite() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                attending INTEGER NOT NULL,
                party_type TEXT,
                partner_name TEXT,
                family_members TEXT,
                address TEXT,
                bus INTEGER NOT NULL,
                bus_stop TEXT,
                private_transport INTEGER,
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
            row["name"]
            for row in conn.execute("PRAGMA table_info(rsvps)").fetchall()
        }
        missing = {
            "party_type": "TEXT",
            "partner_name": "TEXT",
            "family_members": "TEXT",
            "address": "TEXT",
            "bus_stop": "TEXT",
            "private_transport": "INTEGER",
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
        ensure_setting(conn, "mischief_enabled", "1")
        ensure_setting(conn, "photos_enabled", "0")
        conn.commit()


def init_db() -> None:
    if USE_POSTGRES:
        init_db_postgres()
        return
    init_db_sqlite()


@contextmanager
def db_connection():
    if USE_POSTGRES:
        raw_conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        raw_conn = sqlite3.connect(DB_PATH)
        raw_conn.row_factory = sqlite3.Row
    conn = DBConnection(raw_conn, USE_POSTGRES)
    try:
        yield conn
    finally:
        raw_conn.close()


def get_setting(conn: DBConnection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM site_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if not row:
        return default
    return row["value"]


def admin_key_ok(key: str) -> bool:
    return bool(ADMIN_KEY) and key == ADMIN_KEY


def build_game_state(conn: DBConnection, ip: Optional[str] = None) -> dict:
    row = conn.execute(
        "SELECT challenge_index, round_index FROM game_state WHERE id = 1"
    ).fetchone()
    if not row:
        raise RuntimeError("Game state missing")

    challenge_index = int(row["challenge_index"])
    round_index = int(row["round_index"])
    count_row = conn.execute(
        "SELECT COUNT(*) AS vote_count FROM game_votes WHERE round_index = ?",
        (round_index,),
    ).fetchone()
    count = int(count_row["vote_count"]) if count_row else 0
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
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    to_addr = os.getenv("SMTP_TO", "alfonnati2026@gmail.com")
    if not host or not to_addr:
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "jmdea2013@gmail.com")
    password = os.getenv("SMTP_PASS", "qhco gdca nwjf vpnm")
    sender = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    party_label = {
        "solo": "Voy solo/a",
        "pareja": "Voy con pareja",
        "familia": "Voy en familia",
    }.get(payload.get("party_type"), payload.get("party_type") or "-")
    bus_label = "Si" if payload.get("bus") else "No"
    attending_label = "Si" if payload.get("attending") else "No"
    name = html.escape(payload.get("name") or "-")
    partner = html.escape(payload.get("partner_name") or "-")
    family = html.escape(payload.get("family_members") or "-")
    bus_stop = html.escape(payload.get("bus_stop") or "-")
    allergies = html.escape(payload.get("allergies") or "-")
    message = html.escape(payload.get("message") or "-")

    msg = EmailMessage()
    msg["Subject"] = "Nueva inscripción a tu boda!"
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(
        "\n".join(
            [
                "Nueva inscripción a tu boda!",
                f"Nombre: {payload.get('name') or '-'}",
                f"Asistira: {attending_label}",
                f"Tipo asistencia: {party_label}",
                f"Nombre pareja: {payload.get('partner_name') or '-'}",
                f"Familia: {payload.get('family_members') or '-'}",
                f"Autobus: {bus_label}",
                f"Parada bus: {payload.get('bus_stop') or '-'}",
                f"Alergias: {payload.get('allergies') or '-'}",
                f"Mensaje: {payload.get('message') or '-'}",
            ]
        )
    )
    msg.add_alternative(
        f"""
<!doctype html>
<html lang="es">
  <body style="margin:0;padding:24px;background:#0d1828;font-family:Georgia,'Times New Roman',serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:720px;margin:0 auto;background:linear-gradient(160deg,#11233a,#0d1828);border:1px solid rgba(255,255,255,0.2);border-radius:22px;overflow:hidden;">
      <tr>
        <td style="padding:28px 30px 12px;color:#f4ede2;">
          <p style="margin:0;font-size:11px;letter-spacing:0.35em;text-transform:uppercase;color:#d2b48c;">Alfonso & Natalia</p>
          <h1 style="margin:10px 0 6px;font-size:30px;font-weight:600;line-height:1.2;">Nueva inscripción a tu boda!</h1>
          <p style="margin:0 0 14px;color:#c8d2df;font-size:15px;">Se ha registrado un invitado y aquí tienes todos los detalles.</p>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 30px 30px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0 8px;">
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Nombre</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{name}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Asistirá</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{attending_label}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Cómo viene</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{party_label}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Nombre pareja</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{partner}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Familia</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{family}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Autobús</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{bus_label}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Parada</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{bus_stop}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Alergias</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{allergies}</td></tr>
            <tr><td style="width:210px;padding:10px 14px;background:rgba(255,255,255,0.08);border-radius:12px;color:#d2b48c;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;">Mensaje</td><td style="padding:10px 14px;background:rgba(255,255,255,0.95);border-radius:12px;color:#18283d;font-size:15px;">{message}</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
        """,
        subtype="html",
    )

    try:
        print(f"[smtp] sending from={sender} to={to_addr} host={host}:{port}")
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls(context=context)
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        print("[smtp] sent ok")
    except Exception as exc:  # pragma: no cover - avoid crashing on SMTP errors
        print(f"[smtp] {exc}")


@app.get("/")
def index():
    with db_connection() as conn:
        mischief_setting = get_setting(conn, "mischief_enabled", "1")
        photos_setting = get_setting(conn, "photos_enabled", "0")
    mischief_enabled = mischief_setting != "0"
    photos_enabled = photos_setting == "1"
    return render_template(
        "index.html",
        mischief_enabled=mischief_enabled,
        photos_enabled=photos_enabled,
    )


@app.get("/admin")
def admin():
    key = request.args.get("key", "")
    if admin_key_ok(key):
        with db_connection() as conn:
            mischief_setting = get_setting(conn, "mischief_enabled", "1")
            photos_setting = get_setting(conn, "photos_enabled", "0")
        mischief_enabled = mischief_setting != "0"
        photos_enabled = photos_setting == "1"
        return render_template(
            "admin.html",
            admin_key=key,
            mischief_enabled=mischief_enabled,
            photos_enabled=photos_enabled,
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
            SELECT id, name, attending, party_type, partner_name, family_members,
                   bus, bus_stop, allergies, message, created_at
            FROM rsvps
            ORDER BY id DESC
            """
        ).fetchall()

    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "attending": bool(row["attending"]),
            "party_type": row["party_type"] or "",
            "partner_name": row["partner_name"] or "",
            "family_members": row["family_members"] or "",
            "bus": bool(row["bus"]),
            "bus_stop": row["bus_stop"] or "",
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
                except DBIntegrityError:
                    return jsonify({"ok": False, "error": "Ya has votado"}), 400
                conn.commit()
                return jsonify({"ok": True})

        song_id = None
        if USE_POSTGRES:
            created = conn.execute(
                """
                INSERT INTO songs (title, votes, created_at)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                (title, 1, created_at),
            ).fetchone()
            if created:
                song_id = created["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO songs (title, votes, created_at)
                VALUES (?, ?, ?)
                """,
                (title, 1, created_at),
            )
            song_id = cursor.lastrowid

        if not song_id:
            return jsonify({"ok": False, "error": "No se pudo guardar la canción"}), 500

        try:
            conn.execute(
                """
                INSERT INTO song_votes (song_id, ip, created_at)
                VALUES (?, ?, ?)
                """,
                (song_id, ip, created_at),
            )
        except DBIntegrityError:
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
        except DBIntegrityError:
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
        set_setting(conn, "mischief_enabled", value)
        conn.commit()
    return jsonify({"ok": True, "enabled": enabled})


@app.post("/api/settings/photos")
def update_photos_setting():
    key = request.args.get("key", "")
    if not admin_key_ok(key):
        abort(403)
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled"))
    value = "1" if enabled else "0"
    with db_connection() as conn:
        set_setting(conn, "photos_enabled", value)
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
        except DBIntegrityError:
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
    party_type = (data.get("party_type") or "solo").strip().lower()
    if party_type not in {"solo", "pareja", "familia"}:
        return jsonify({"ok": False, "error": "Tipo de asistencia inválido"}), 400
    partner_name = (data.get("partner_name") or "").strip()
    raw_family = data.get("family_members") or []
    family_list = []
    if isinstance(raw_family, list):
        family_list = [
            str(item).strip()
            for item in raw_family
            if str(item).strip()
        ]
    elif isinstance(raw_family, str):
        family_list = [
            item.strip() for item in raw_family.split(",") if item.strip()
        ]
    family_members = ", ".join(family_list)
    bus = bool(data.get("bus"))
    bus_stop = (data.get("bus_stop") or "").strip()
    allergies = (data.get("allergies") or "").strip()
    message = (data.get("message") or "").strip()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if not attending:
        party_type = "solo"
        partner_name = ""
        family_members = ""
        bus = False
        bus_stop = ""

    if party_type != "pareja":
        partner_name = ""
    if party_type != "familia":
        family_members = ""

    if attending:
        if party_type == "pareja" and not partner_name:
            return (
                jsonify({"ok": False, "error": "Nombre de pareja requerido"}),
                400,
            )
        if party_type == "familia" and not family_list:
            return (
                jsonify(
                    {"ok": False, "error": "Indica miembros de la familia"}
                ),
                400,
            )
        if bus and not bus_stop:
            return (
                jsonify({"ok": False, "error": "Selecciona una parada"}),
                400,
            )

    if not bus:
        bus_stop = ""

    payload = {
        "name": name,
        "attending": attending,
        "party_type": party_type,
        "partner_name": partner_name,
        "family_members": family_members,
        "bus": bus,
        "bus_stop": bus_stop,
        "allergies": allergies,
        "message": message,
        "created_at": created_at,
    }

    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO rsvps (
                name,
                attending,
                party_type,
                partner_name,
                family_members,
                bus,
                bus_stop,
                allergies,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                int(attending),
                party_type,
                partner_name,
                family_members,
                int(bus),
                bus_stop,
                allergies,
                message,
                created_at,
            ),
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
            SELECT id, name, attending, party_type, partner_name, family_members,
                   bus, bus_stop, allergies, message, created_at
            FROM rsvps
            ORDER BY id DESC
            """
        ).fetchall()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "ID",
            "Nombre",
            "Asistira",
            "Tipo",
            "Pareja",
            "Familia",
            "Autobus",
            "Parada",
            "Alergias",
            "Mensaje",
            "Fecha",
        ]
    )
    for row in rows:
        party_label = {
            "solo": "Solo",
            "pareja": "Con pareja",
            "familia": "En familia",
        }.get(row["party_type"], row["party_type"] or "")
        writer.writerow(
            [
                row["id"],
                row["name"],
                "Si" if row["attending"] else "No",
                party_label,
                row["partner_name"] or "",
                row["family_members"] or "",
                "Si" if row["bus"] else "No",
                row["bus_stop"] or "",
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
