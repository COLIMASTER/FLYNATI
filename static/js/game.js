const key = window.ADMIN_KEY || "";
const refreshButton = document.getElementById("game-refresh");
const countEl = document.getElementById("game-count");
const remainingEl = document.getElementById("game-remaining");
const statusEl = document.getElementById("game-status");
const challengeEl = document.getElementById("game-challenge");
const instructionEl = document.getElementById("game-instruction");
const advanceButton = document.getElementById("game-advance");
const resetButton = document.getElementById("game-reset");
const alertEl = document.getElementById("game-alert");
const alertTitle = document.getElementById("game-alert-title");
const lastUpdate = document.getElementById("game-last-update");

const songChallenges = new Set([
  "Inicia conga",
  "Inicia limbo",
  "Inicia una macarena",
]);

const updateUI = (state) => {
  if (countEl) countEl.textContent = state.count ?? 0;
  if (remainingEl) remainingEl.textContent = state.remaining ?? 0;
  if (statusEl) {
    statusEl.textContent = state.challenge_active ? "Reto activo" : "Esperando";
  }
  if (challengeEl) {
    challengeEl.textContent = state.challenge || "--";
  }
  if (instructionEl) {
    if (state.challenge_active) {
      instructionEl.textContent = state.instruction || "";
      instructionEl.classList.add("is-active");
      instructionEl.hidden = false;
    } else {
      instructionEl.textContent = "";
      instructionEl.classList.remove("is-active");
      instructionEl.hidden = true;
    }
  }
  if (advanceButton) {
    advanceButton.disabled = !state.challenge_active;
  }

  const isSongChallenge = songChallenges.has(state.challenge);
  if (alertEl) {
    alertEl.hidden = !isSongChallenge;
  }
  if (alertTitle && isSongChallenge) {
    const label = state.challenge_active
      ? "Reto musical activo"
      : "Próximo reto musical";
    alertTitle.textContent = `${label}: ${state.challenge}`;
  }
};

const loadState = async () => {
  try {
    const response = await fetch("/api/game");
    if (!response.ok) {
      throw new Error("No se pudo cargar el estado");
    }
    const data = await response.json();
    updateUI(data);
    if (lastUpdate) {
      lastUpdate.textContent = new Date().toLocaleString("es-ES");
    }
  } catch (error) {
    if (lastUpdate) {
      lastUpdate.textContent = error.message;
    }
  }
};

if (refreshButton) {
  refreshButton.addEventListener("click", loadState);
}

if (advanceButton) {
  advanceButton.addEventListener("click", async () => {
    try {
      const response = await fetch(
        `/api/game/advance?key=${encodeURIComponent(key)}`,
        { method: "POST" }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo avanzar el reto");
      }
      const data = await response.json().catch(() => ({}));
      if (data && data.state) {
        updateUI(data.state);
      } else {
        await loadState();
      }
      if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleString("es-ES");
      }
    } catch (error) {
      if (lastUpdate) {
        lastUpdate.textContent = error.message;
      }
    }
  });
}

if (resetButton) {
  resetButton.addEventListener("click", async () => {
    try {
      const response = await fetch(
        `/api/game/reset?key=${encodeURIComponent(key)}`,
        { method: "POST" }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo reiniciar el juego");
      }
      const data = await response.json().catch(() => ({}));
      if (data && data.state) {
        updateUI(data.state);
      } else {
        await loadState();
      }
      if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleString("es-ES");
      }
    } catch (error) {
      if (lastUpdate) {
        lastUpdate.textContent = error.message;
      }
    }
  });
}

loadState();
setInterval(loadState, 7000);
