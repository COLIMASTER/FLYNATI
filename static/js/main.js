const intro = document.getElementById("intro");
const seal = intro ? intro.querySelector(".seal") : null;
const introAudio = document.getElementById("intro-audio");
const soundToggle = document.getElementById("sound-toggle");
const hero = document.querySelector(".hero");
const heroBg = document.querySelector(".hero-bg");
const venue = document.querySelector(".venue");
const venueBg = document.querySelector(".venue-bg");
const countdown = document.querySelector("[data-countdown-target]");
const countdownDays = document.getElementById("countdown-days");
const countdownHours = document.getElementById("countdown-hours");
const countdownMinutes = document.getElementById("countdown-minutes");
const countdownSeconds = document.getElementById("countdown-seconds");
const attendingToggle = document.getElementById("attending");
const attendingFields = document.getElementById("attending-fields");
const attendingNote = document.getElementById("attending-note");
const partyTypeField = document.getElementById("party-type-field");
const partyTypeRadios = document.querySelectorAll("input[name='party-type']");
const partnerField = document.getElementById("partner-field");
const partnerInput = document.getElementById("partner-name");
const familyField = document.getElementById("family-field");
const familyList = document.getElementById("family-list");
const addFamilyButton = document.getElementById("add-family");
const busToggle = document.getElementById("bus");
const busStopField = document.getElementById("bus-stop-field");
const busStopOptions = document.querySelectorAll("input[name='bus-stop']");
const allergiesToggle = document.getElementById("allergies-toggle");
const allergiesField = document.getElementById("allergies-field");
const allergiesInput = document.getElementById("allergies");
const copyIbanButton = document.getElementById("copy-iban-btn");
const thankyouOverlay = document.getElementById("thankyou-overlay");
const galleryScroll = document.querySelector(".gallery-scroll");
const galleryTrack = document.getElementById("gallery-track");
const galleryLightbox = document.getElementById("gallery-lightbox");
const galleryLightboxImage = document.getElementById("gallery-lightbox-image");
const galleryLightboxClose = document.getElementById("gallery-lightbox-close");
const songForm = document.getElementById("song-form");
const songInput = document.getElementById("song-title");
const songSuggestions = document.getElementById("song-suggestions");
const songList = document.getElementById("song-list");
const songTabs = document.querySelectorAll("[data-song-view]");
const songHint = document.querySelector(".dj-hint");
const mischiefButton = document.getElementById("mala-button");
const mischiefHint = document.getElementById("mala-hint");
const mischiefNote = document.getElementById("mala-note");
const mischiefDefaultHint = mischiefHint ? mischiefHint.textContent : "";
const songHintDefault = songHint ? songHint.textContent : "";
let introOpened = false;
let audioEnabled = true;
let thankyouTimer = null;
let thankyouCloseTimer = null;
let songView = "top";
let previousSongRanks = new Map();
let songRefreshTimer = null;
let songsCache = [];
let songsRequestCounter = 0;
let songsLastApplied = 0;
let songHintTimer = null;
let gameRefreshTimer = null;
let copyIbanTimer = null;

const openIntro = () => {
  if (!intro || intro.classList.contains("opened")) {
    return;
  }
  intro.classList.add("opened");
  introOpened = true;
  if (introAudio && audioEnabled) {
    introAudio.currentTime = 0;
    introAudio.play().catch(() => {});
  }
  setTimeout(() => {
    intro.classList.add("hidden");
    document.body.classList.remove("no-scroll");
  }, 7000);
};

if (seal) {
  seal.addEventListener("click", openIntro);
}

const updateSoundToggle = () => {
  if (!soundToggle) {
    return;
  }
  soundToggle.dataset.muted = audioEnabled ? "false" : "true";
  soundToggle.setAttribute("aria-pressed", audioEnabled ? "true" : "false");
  const label = audioEnabled ? "Sonido activado" : "Sonido desactivado";
  soundToggle.setAttribute("aria-label", label);
  soundToggle.setAttribute("title", label);
};

if (soundToggle) {
  updateSoundToggle();
  soundToggle.addEventListener("click", () => {
    audioEnabled = !audioEnabled;
    if (introAudio) {
      introAudio.muted = !audioEnabled;
      if (audioEnabled && introOpened) {
        introAudio.play().catch(() => {});
      } else {
        introAudio.pause();
      }
    }
    updateSoundToggle();
  });
}

const getPartyType = () => {
  if (!partyTypeRadios.length) {
    return "solo";
  }
  const selected = Array.from(partyTypeRadios).find((radio) => radio.checked);
  return selected ? selected.value : "solo";
};

const createFamilyRow = () => {
  const row = document.createElement("div");
  row.className = "family-row";
  const input = document.createElement("input");
  input.className = "family-member";
  input.type = "text";
  input.name = "family-members";
  input.placeholder = "Nombre y apellidos";
  const removeButton = document.createElement("button");
  removeButton.className = "family-remove";
  removeButton.type = "button";
  removeButton.textContent = "Quitar";
  row.appendChild(input);
  row.appendChild(removeButton);
  return row;
};

const ensureFamilyRow = () => {
  if (!familyList) {
    return;
  }
  const inputs = familyList.querySelectorAll("input");
  if (!inputs.length) {
    familyList.appendChild(createFamilyRow());
  }
};

const resetFamilyRows = () => {
  if (!familyList) {
    return;
  }
  familyList.innerHTML = "";
  familyList.appendChild(createFamilyRow());
};

const updatePartyFields = () => {
  const isAttending = attendingToggle ? attendingToggle.checked : false;
  if (partyTypeField) {
    partyTypeField.hidden = !isAttending;
  }
  if (!isAttending) {
    if (partnerField) {
      partnerField.hidden = true;
    }
    if (familyField) {
      familyField.hidden = true;
    }
    if (partnerInput) {
      partnerInput.required = false;
      partnerInput.value = "";
    }
    if (familyList) {
      familyList.querySelectorAll("input").forEach((input) => {
        input.required = false;
        input.value = "";
      });
    }
    return;
  }

  const partyType = getPartyType();
  const isCouple = partyType === "pareja";
  const isFamily = partyType === "familia";

  if (partnerField) {
    partnerField.hidden = !isCouple;
  }
  if (partnerInput) {
    partnerInput.required = isCouple;
    if (!isCouple) {
      partnerInput.value = "";
    }
  }
  if (familyField) {
    familyField.hidden = !isFamily;
  }
  if (familyList) {
    ensureFamilyRow();
    const inputs = familyList.querySelectorAll("input");
    inputs.forEach((input, index) => {
      input.required = isFamily && index === 0;
      if (!isFamily) {
        input.value = "";
      }
    });
  }
};

const updateBusFields = () => {
  const isAttending = attendingToggle ? attendingToggle.checked : false;
  const usesBus = Boolean(isAttending && busToggle && busToggle.checked);

  if (busStopField) {
    busStopField.hidden = !usesBus;
  }
  if (busStopOptions.length) {
    busStopOptions.forEach((option) => {
      option.required = usesBus;
      if (!usesBus) {
        option.checked = false;
      }
    });
  }
};

const updateAllergiesField = () => {
  const enabled = Boolean(
    attendingToggle &&
      attendingToggle.checked &&
      allergiesToggle &&
      allergiesToggle.checked
  );
  if (allergiesField) {
    allergiesField.hidden = !enabled;
  }
  if (allergiesInput) {
    allergiesInput.required = enabled;
    if (!enabled) {
      allergiesInput.value = "";
    }
  }
};

const updateAttendingFields = () => {
  if (!attendingToggle) {
    return;
  }
  const isAttending = attendingToggle.checked;
  if (attendingFields) {
    attendingFields.hidden = !isAttending;
  }
  if (attendingNote) {
    attendingNote.hidden = isAttending;
  }
  if (!isAttending) {
    if (allergiesToggle) {
      allergiesToggle.checked = false;
    }
    if (busToggle) {
      busToggle.checked = false;
    }
  }
  updatePartyFields();
  updateBusFields();
  updateAllergiesField();
};

if (attendingToggle) {
  updateAttendingFields();
  attendingToggle.addEventListener("change", updateAttendingFields);
}

if (partyTypeRadios.length) {
  partyTypeRadios.forEach((radio) => {
    radio.addEventListener("change", updatePartyFields);
  });
}

if (busToggle) {
  busToggle.addEventListener("change", updateBusFields);
}

if (allergiesToggle) {
  allergiesToggle.addEventListener("change", updateAllergiesField);
}

if (addFamilyButton) {
  addFamilyButton.addEventListener("click", () => {
    if (!familyList) {
      return;
    }
    familyList.appendChild(createFamilyRow());
    updatePartyFields();
  });
}

if (familyList) {
  familyList.addEventListener("click", (event) => {
    const removeButton = event.target.closest(".family-remove");
    if (!removeButton) {
      return;
    }
    const row = removeButton.closest(".family-row");
    if (row) {
      row.remove();
    }
    ensureFamilyRow();
    updatePartyFields();
  });
}

document.querySelectorAll(".section").forEach((section) => {
  const items = section.querySelectorAll(".reveal");
  items.forEach((item, index) => {
    item.style.setProperty("--reveal-delay", `${index * 0.12}s`);
  });
});

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
      }
    });
  },
  { threshold: 0.15 }
);

document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const normalizeText = (value) =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();

const updateSectionParallax = (section, bg, speed) => {
  if (!section || !bg || reduceMotion) {
    return;
  }
  const rect = section.getBoundingClientRect();
  if (rect.bottom < 0 || rect.top > window.innerHeight) {
    return;
  }
  const offset = Math.max(-rect.top, 0);
  bg.style.transform = `translateY(${offset * speed}px) scale(1.05)`;
};

const updateParallax = () => {
  updateSectionParallax(hero, heroBg, 0.3);
  updateSectionParallax(venue, venueBg, 0.2);
};

let ticking = false;
window.addEventListener("scroll", () => {
  if (!ticking) {
    window.requestAnimationFrame(() => {
      updateParallax();
      ticking = false;
    });
    ticking = true;
  }
});

updateParallax();

const showThankYouOverlay = () => {
  if (!thankyouOverlay) {
    return;
  }
  if (thankyouTimer) {
    window.clearTimeout(thankyouTimer);
  }
  if (thankyouCloseTimer) {
    window.clearTimeout(thankyouCloseTimer);
  }
  thankyouOverlay.classList.add("is-active");
  thankyouOverlay.classList.remove("is-closing");
  thankyouOverlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("overlay-open");
  thankyouCloseTimer = window.setTimeout(() => {
    thankyouOverlay.classList.add("is-closing");
  }, 7600);
  thankyouTimer = window.setTimeout(() => {
    thankyouOverlay.classList.remove("is-active");
    thankyouOverlay.classList.remove("is-closing");
    thankyouOverlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("overlay-open");
  }, 8800);
};

const setupCountdown = () => {
  if (!countdown) {
    return;
  }
  const targetValue = countdown.dataset.countdownTarget;
  if (!targetValue) {
    return;
  }
  const targetDate = new Date(targetValue);
  if (Number.isNaN(targetDate.getTime())) {
    return;
  }

  let countdownTimer = null;
  const updateCountdown = () => {
    const now = new Date();
    let diff = targetDate.getTime() - now.getTime();
    if (diff < 0) {
      diff = 0;
    }
    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (countdownDays) {
      countdownDays.textContent = String(days).padStart(2, "0");
    }
    if (countdownHours) {
      countdownHours.textContent = String(hours).padStart(2, "0");
    }
    if (countdownMinutes) {
      countdownMinutes.textContent = String(minutes).padStart(2, "0");
    }
    if (countdownSeconds) {
      countdownSeconds.textContent = String(seconds).padStart(2, "0");
    }

    if (diff === 0 && countdownTimer) {
      window.clearInterval(countdownTimer);
    }
  };

  updateCountdown();
  countdownTimer = window.setInterval(updateCountdown, 1000);
};

setupCountdown();

const fallbackCopy = (value) => {
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
};

const copyText = async (value) => {
  if (!value) {
    return false;
  }
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (error) {
      return fallbackCopy(value);
    }
  }
  return fallbackCopy(value);
};

if (copyIbanButton) {
  copyIbanButton.addEventListener("click", async () => {
    const iban = copyIbanButton.dataset.iban || "";
    const copied = await copyText(iban);

    if (copyIbanTimer) {
      window.clearTimeout(copyIbanTimer);
    }

    if (copied) {
      copyIbanButton.textContent = "Copiado";
      copyIbanButton.classList.add("is-copied");
    }

    copyIbanTimer = window.setTimeout(() => {
      copyIbanButton.textContent = "Copiar IBAN";
      copyIbanButton.classList.remove("is-copied");
    }, 2200);
  });
}

const openGalleryLightbox = (src, alt) => {
  if (!galleryLightbox || !galleryLightboxImage) {
    return;
  }
  galleryLightboxImage.src = src;
  galleryLightboxImage.alt = alt || "Recuerdo de la boda";
  galleryLightbox.classList.add("is-active");
  galleryLightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("overlay-open");
};

const closeGalleryLightbox = () => {
  if (!galleryLightbox || !galleryLightboxImage) {
    return;
  }
  galleryLightbox.classList.remove("is-active");
  galleryLightbox.setAttribute("aria-hidden", "true");
  galleryLightboxImage.src = "";
  if (!thankyouOverlay || !thankyouOverlay.classList.contains("is-active")) {
    document.body.classList.remove("overlay-open");
  }
};

if (galleryTrack && galleryLightbox && galleryLightboxImage) {
  galleryTrack.addEventListener("click", (event) => {
    const button = event.target.closest(".gallery-thumb");
    if (!button) {
      return;
    }
    const image = button.querySelector("img");
    if (!image) {
      return;
    }
    const fullSrc = button.dataset.full || image.src;
    openGalleryLightbox(fullSrc, image.alt);
  });
}

if (galleryLightboxClose) {
  galleryLightboxClose.addEventListener("click", closeGalleryLightbox);
}

if (galleryLightbox) {
  galleryLightbox.addEventListener("click", (event) => {
    if (event.target === galleryLightbox) {
      closeGalleryLightbox();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeGalleryLightbox();
  }
});

const setupGalleryAutoScroll = () => {
  if (!galleryScroll || reduceMotion) {
    return;
  }
  let paused = false;
  let pauseTimer = null;

  const pause = (duration = 3200) => {
    paused = true;
    if (pauseTimer) {
      window.clearTimeout(pauseTimer);
    }
    pauseTimer = window.setTimeout(() => {
      paused = false;
    }, duration);
  };

  const handlePause = () => pause(3600);
  galleryScroll.addEventListener("wheel", handlePause, { passive: true });
  galleryScroll.addEventListener("touchstart", handlePause, { passive: true });
  galleryScroll.addEventListener("pointerdown", handlePause);

  const step = () => {
    if (!paused) {
      const maxScroll = galleryScroll.scrollWidth - galleryScroll.clientWidth;
      if (maxScroll > 1) {
        galleryScroll.scrollLeft += 0.35;
        if (galleryScroll.scrollLeft >= maxScroll) {
          galleryScroll.scrollLeft = 0;
        }
      }
    }
    window.requestAnimationFrame(step);
  };

  window.requestAnimationFrame(step);
};

setupGalleryAutoScroll();

const uploadButton = document.querySelector(".upload-btn");
const uploadWrapper = document.querySelector(".upload-disabled");
const uploadNote = document.querySelector(".upload-note");

const setUploadState = (enabled) => {
  if (!uploadButton) {
    return;
  }
  if (enabled) {
    uploadButton.classList.remove("is-disabled");
    uploadButton.dataset.disabled = "false";
    uploadButton.setAttribute("aria-disabled", "false");
    if (uploadWrapper) {
      uploadWrapper.dataset.disabled = "false";
      uploadWrapper.removeAttribute("title");
    }
    if (uploadNote) {
      uploadNote.textContent = "Disponible.";
    }
  } else {
    uploadButton.classList.add("is-disabled");
    uploadButton.dataset.disabled = "true";
    uploadButton.setAttribute("aria-disabled", "true");
    if (uploadWrapper) {
      uploadWrapper.dataset.disabled = "true";
    }
  }
};

if (uploadButton) {
  const availableDate = uploadButton.dataset.available;
  let enabled = false;
  if (availableDate) {
    const target = new Date(`${availableDate}T00:00:00`);
    enabled = !Number.isNaN(target.getTime()) && Date.now() >= target.getTime();
  }
  setUploadState(enabled);
  if (!enabled) {
    uploadButton.addEventListener("click", (event) => {
      event.preventDefault();
    });
  }
}

const hideSongSuggestions = () => {
  if (!songSuggestions) {
    return;
  }
  songSuggestions.hidden = true;
  songSuggestions.innerHTML = "";
};

const renderSongSuggestions = (query) => {
  if (!songSuggestions) {
    return;
  }
  const normalizedQuery = normalizeText(query || "");
  if (!normalizedQuery || !songsCache.length) {
    hideSongSuggestions();
    return;
  }

  const matches = songsCache.filter((item) =>
    item.normalized.includes(normalizedQuery)
  );
  if (!matches.length) {
    hideSongSuggestions();
    return;
  }

  songSuggestions.innerHTML = "";
  matches.slice(0, 6).forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "dj-suggestion";
    const title = document.createElement("span");
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "dj-suggestion-meta";
    meta.textContent = `${item.votes} voto${item.votes === 1 ? "" : "s"}`;
    button.appendChild(title);
    button.appendChild(meta);
    button.addEventListener("click", () => {
      if (songInput) {
        songInput.value = item.title;
        songInput.focus();
      }
      hideSongSuggestions();
    });
    songSuggestions.appendChild(button);
  });
  songSuggestions.hidden = false;
};

if (songInput) {
  songInput.addEventListener("input", () => {
    renderSongSuggestions(songInput.value);
  });
  songInput.addEventListener("focus", () => {
    renderSongSuggestions(songInput.value);
  });
  songInput.addEventListener("blur", () => {
    window.setTimeout(() => {
      hideSongSuggestions();
    }, 160);
  });
  songInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideSongSuggestions();
    }
  });
}

const setSongView = (view) => {
  songView = view;
  songTabs.forEach((tab) => {
    const isActive = tab.dataset.songView === view;
    tab.classList.toggle("is-active", isActive);
  });
};

const showSongHint = (message, isError = false, duration = 2600) => {
  if (!songHint) {
    return;
  }
  if (songHintTimer) {
    window.clearTimeout(songHintTimer);
  }

  if (!message) {
    songHint.textContent = songHintDefault;
    songHint.classList.remove("is-error", "is-success");
    return;
  }

  songHint.textContent = message;
  songHint.classList.toggle("is-error", Boolean(isError));
  songHint.classList.toggle("is-success", !isError);
  songHintTimer = window.setTimeout(() => {
    songHint.textContent = songHintDefault;
    songHint.classList.remove("is-error", "is-success");
  }, duration);
};

const renderSongs = (items) => {
  if (!songList) {
    return;
  }
  const currentRanks = new Map(items.map((item, index) => [item.id, index]));
  const displayItems = songView === "top" ? items.slice(0, 10) : items;

  songList.innerHTML = "";
  if (!displayItems.length) {
    const empty = document.createElement("li");
    empty.className = "dj-empty";
    empty.textContent = "Aún no hay canciones propuestas.";
    songList.appendChild(empty);
    previousSongRanks = currentRanks;
    return;
  }

  displayItems.forEach((item, index) => {
    const li = document.createElement("li");
    li.className = "dj-item";
    li.dataset.id = item.id;

    const prevRank = previousSongRanks.get(item.id);
    const nextRank = currentRanks.get(item.id);
    if (prevRank !== undefined && nextRank !== undefined) {
      if (nextRank < prevRank) {
        li.classList.add("rank-up");
      } else if (nextRank > prevRank) {
        li.classList.add("rank-down");
      }
    }

    const rank = document.createElement("div");
    rank.className = "dj-rank";
    rank.textContent = String(index + 1);

    const info = document.createElement("div");
    info.className = "dj-info";

    const title = document.createElement("span");
    title.className = "dj-title";
    title.textContent = item.title;

    const votes = document.createElement("span");
    votes.className = "dj-votes";
    votes.textContent = `${item.votes} voto${item.votes === 1 ? "" : "s"}`;

    info.appendChild(title);
    info.appendChild(votes);

    const voteButton = document.createElement("button");
    voteButton.type = "button";
    voteButton.className = "dj-vote";
    voteButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 18V6l-4 4"></path>
        <path d="M15 6v12l4-4"></path>
        <path d="M4 20h16"></path>
      </svg>
      Votar
    `;
    voteButton.addEventListener("click", async () => {
      voteButton.disabled = true;
      try {
        const response = await fetch("/api/songs/vote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: item.id }),
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.error || "No se pudo votar");
        }
        await loadSongs();
        showSongHint("Voto registrado");
      } catch (error) {
        console.error(error);
        showSongHint(error.message || "No se pudo votar", true);
      } finally {
        voteButton.disabled = false;
      }
    });

    li.appendChild(rank);
    li.appendChild(info);
    li.appendChild(voteButton);
    songList.appendChild(li);

    if (li.classList.contains("rank-up") || li.classList.contains("rank-down")) {
      setTimeout(() => {
        li.classList.remove("rank-up", "rank-down");
      }, 900);
    }
  });

  previousSongRanks = currentRanks;
};

const loadSongs = async () => {
  const requestId = ++songsRequestCounter;
  try {
    const response = await fetch(`/api/songs?ts=${Date.now()}`, {
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      throw new Error("No se pudo cargar las canciones");
    }
    const data = await response.json();
    if (requestId < songsLastApplied) {
      return;
    }
    songsLastApplied = requestId;
    const items = data.items || [];
    songsCache = items.map((item) => ({
      ...item,
      normalized: normalizeText(item.title),
    }));
    renderSongs(items);
    if (songInput && document.activeElement === songInput) {
      renderSongSuggestions(songInput.value);
    }
  } catch (error) {
    console.error(error);
    showSongHint("No se pudo actualizar la lista", true, 3000);
  }
};

if (songTabs.length) {
  setSongView(songView);
  songTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      setSongView(tab.dataset.songView || "top");
      loadSongs();
    });
  });
}

if (songForm && songInput) {
  songForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = songInput.value.trim();
    if (!title) {
      return;
    }
    songInput.disabled = true;
    try {
      const response = await fetch("/api/songs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo enviar la canción");
      }
      songInput.value = "";
      await loadSongs();
      showSongHint("Canción añadida");
    } catch (error) {
      console.error(error);
      showSongHint(error.message || "No se pudo enviar la canción", true);
    } finally {
      songInput.disabled = false;
    }
  });
}

if (songList) {
  loadSongs();
  songRefreshTimer = window.setInterval(loadSongs, 6000);
}

const updateMischiefUI = (state) => {
  if (!mischiefButton || !mischiefHint) {
    return;
  }
  const active = Boolean(state && state.challenge_active);

  mischiefButton.hidden = active;
  mischiefButton.disabled = active;

  if (active) {
    const label = state && state.challenge ? `Reto: ${state.challenge}` : "Reto";
    const instruction = state && state.instruction ? state.instruction : "";
    mischiefHint.textContent = instruction ? `${label}\n${instruction}` : label;
    mischiefHint.classList.add("is-active");
  } else {
    mischiefHint.textContent = mischiefDefaultHint;
    mischiefHint.classList.remove("is-active");
  }

  if (mischiefNote) {
    mischiefNote.textContent = "";
  }
};

const loadMischiefState = async () => {
  try {
    const response = await fetch("/api/game");
    if (!response.ok) {
      throw new Error("No se pudo cargar el juego");
    }
    const data = await response.json();
    updateMischiefUI(data);
  } catch (error) {
    if (mischiefNote) {
      mischiefNote.textContent = error.message;
    }
  }
};

if (mischiefButton) {
  mischiefButton.addEventListener("click", async () => {
    mischiefButton.disabled = true;
    if (mischiefNote) {
      mischiefNote.textContent = "";
    }
    try {
      const response = await fetch("/api/game/vote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo registrar el voto");
      }
      const data = await response.json().catch(() => ({}));
      if (data && data.ok && data.state) {
        updateMischiefUI(data.state);
      } else {
        await loadMischiefState();
      }
    } catch (error) {
      if (mischiefNote) {
        mischiefNote.textContent = error.message;
      }
    }
  });

  loadMischiefState();
  gameRefreshTimer = window.setInterval(loadMischiefState, 7000);
}

const getFamilyMembers = () => {
  if (!familyList) {
    return [];
  }
  return Array.from(familyList.querySelectorAll("input"))
    .map((input) => input.value.trim())
    .filter(Boolean);
};

const getBusStop = () => {
  if (!busStopOptions.length) {
    return "";
  }
  const selected = Array.from(busStopOptions).find((option) => option.checked);
  return selected ? selected.value : "";
};

const form = document.getElementById("rsvp-form");
const note = document.getElementById("form-note");

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");

    const attending = attendingToggle ? attendingToggle.checked : false;
    const partyType = getPartyType();
    const isCouple = partyType === "pareja";
    const isFamily = partyType === "familia";
    const busEnabled = Boolean(attending && busToggle && busToggle.checked);
    const allergiesEnabled = Boolean(
      attending && allergiesToggle && allergiesToggle.checked
    );

    if (!form.reportValidity()) {
      return;
    }
    const payload = {
      name: document.getElementById("guest-name").value.trim(),
      attending,
      party_type: attending ? partyType : "solo",
      partner_name:
        attending && isCouple && partnerInput ? partnerInput.value.trim() : "",
      family_members: attending && isFamily ? getFamilyMembers() : [],
      bus: busEnabled,
      bus_stop: busEnabled ? getBusStop() : "",
      allergies:
        attending && allergiesEnabled && allergiesInput
          ? allergiesInput.value.trim()
          : "",
      message: attending ? document.getElementById("message").value.trim() : "",
    };

    button.disabled = true;
    button.textContent = "Enviando...";
    note.textContent = "";

    try {
      const response = await fetch("/api/rsvp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Error al enviar el formulario");
      }

      form.reset();
      resetFamilyRows();
      if (attendingToggle) {
        attendingToggle.checked = true;
      }
      updateAttendingFields();
      note.textContent = "";
      showThankYouOverlay();
    } catch (error) {
      note.textContent = error.message || "No se pudo enviar. Intenta de nuevo.";
    } finally {
      button.disabled = false;
      button.textContent = "Enviar respuesta";
    }
  });
}

