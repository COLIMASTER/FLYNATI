const key = window.ADMIN_KEY || "";
const tbody = document.getElementById("rsvp-body");
const refreshButton = document.getElementById("refresh");
const statTotal = document.getElementById("stat-total");
const statYes = document.getElementById("stat-yes");
const statNo = document.getElementById("stat-no");
const statBus = document.getElementById("stat-bus");
const lastUpdate = document.getElementById("last-update");
const mischiefToggle = document.getElementById("mischief-toggle");
const photosToggle = document.getElementById("photos-toggle");
const partyLabels = {
  solo: "Solo",
  pareja: "Con pareja",
  familia: "En familia",
};

const formatMadridTime = (value) => {
  let date;

  if (value instanceof Date) {
    date = new Date(value.getTime());
  } else if (typeof value === "string" && value.trim()) {
    const normalized = value.replace(" UTC", "Z").replace(" ", "T");
    date = new Date(normalized);
  }

  if (!date || Number.isNaN(date.getTime())) {
    return typeof value === "string" && value.trim() ? value.replace(" UTC", "") : "-";
  }

  return date.toLocaleString("es-ES", {
    hour12: false,
    timeZone: "Europe/Madrid",
  });
};

const updateMischiefToggle = (enabled) => {
  if (!mischiefToggle) {
    return;
  }
  mischiefToggle.dataset.enabled = enabled ? "true" : "false";
  mischiefToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
  mischiefToggle.textContent = enabled ? "Encendido" : "Apagado";
};

const updatePhotosToggle = (enabled) => {
  if (!photosToggle) {
    return;
  }
  photosToggle.dataset.enabled = enabled ? "true" : "false";
  photosToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
  photosToggle.textContent = enabled ? "Encendido" : "Apagado";
};

const handleDelete = async (event) => {
  const button = event.target.closest(".delete-btn");
  if (!button) {
    return;
  }
  const id = button.dataset.id;
  if (!id) {
    return;
  }
  if (!window.confirm("¿Seguro que quieres eliminar este invitado?")) {
    return;
  }
  if (!window.confirm("Esta acción no se puede deshacer. ¿Eliminar definitivamente?")) {
    return;
  }
  button.disabled = true;
  try {
    const response = await fetch(`/api/rsvps/${id}?key=${encodeURIComponent(key)}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "No se pudo eliminar");
    }
    await loadRsvps();
  } catch (error) {
    if (lastUpdate) {
      lastUpdate.textContent = error.message;
    }
  } finally {
    button.disabled = false;
  }
};

const renderRows = (items) => {
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("tr");

    const attending = item.attending ? "Sí" : "No";
    const bus = item.bus ? "Sí" : "No";
    const party = partyLabels[item.party_type] || "-";
    const partner = item.partner_name || "-";
    const family = item.family_members || "-";
    const busStop = item.bus ? item.bus_stop || "-" : "-";

    const createdAt = formatMadridTime(item.created_at || "");
    row.innerHTML = `
      <td>${item.id}</td>
      <td>${item.name}</td>
      <td>${party}</td>
      <td>${partner}</td>
      <td>${family}</td>
      <td><span class="status-pill ${item.attending ? "status-yes" : "status-no"}">${attending}</span></td>
      <td><span class="status-pill ${item.bus ? "status-yes" : "status-no"}">${bus}</span></td>
      <td>${busStop}</td>
      <td>${item.allergies || "-"}</td>
      <td>${item.message || "-"}</td>
      <td>${createdAt}</td>
      <td>
        <button class="delete-btn" type="button" data-id="${item.id}" aria-label="Eliminar invitado">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16"></path>
            <path d="M9 7V5h6v2"></path>
            <path d="M9 11v6"></path>
            <path d="M15 11v6"></path>
            <path d="M6 7l1 13h10l1-13"></path>
          </svg>
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });
};

const updateStats = (items) => {
  const total = items.length;
  const yes = items.filter((item) => item.attending).length;
  const no = total - yes;
  const bus = items.filter((item) => item.bus).length;

  if (statTotal) statTotal.textContent = total;
  if (statYes) statYes.textContent = yes;
  if (statNo) statNo.textContent = no;
  if (statBus) statBus.textContent = bus;
};

const loadRsvps = async () => {
  try {
    const url = `/api/rsvps?key=${encodeURIComponent(key)}&ts=${Date.now()}`;
    const response = await fetch(url, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("No se pudo cargar el panel");
    }
    const data = await response.json();
    const items = data.items || [];
    renderRows(items);
    updateStats(items);
    if (lastUpdate) {
      lastUpdate.textContent = formatMadridTime(new Date());
    }
  } catch (error) {
    if (lastUpdate) {
      lastUpdate.textContent = error.message;
    }
  }
};

if (refreshButton) {
  refreshButton.addEventListener("click", loadRsvps);
}

if (tbody) {
  tbody.addEventListener("click", handleDelete);
}

if (mischiefToggle) {
  updateMischiefToggle(mischiefToggle.dataset.enabled === "true");
  mischiefToggle.addEventListener("click", async () => {
    const nextEnabled = mischiefToggle.dataset.enabled !== "true";
    mischiefToggle.disabled = true;
    try {
      const response = await fetch(
        `/api/settings/mischief?key=${encodeURIComponent(key)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: nextEnabled }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo actualizar");
      }
      const data = await response.json().catch(() => ({}));
      updateMischiefToggle(Boolean(data.enabled));
    } catch (error) {
      if (lastUpdate) {
        lastUpdate.textContent = error.message;
      }
    } finally {
      mischiefToggle.disabled = false;
    }
  });
}

if (photosToggle) {
  updatePhotosToggle(photosToggle.dataset.enabled === "true");
  photosToggle.addEventListener("click", async () => {
    const nextEnabled = photosToggle.dataset.enabled !== "true";
    photosToggle.disabled = true;
    try {
      const response = await fetch(
        `/api/settings/photos?key=${encodeURIComponent(key)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: nextEnabled }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo actualizar");
      }
      const data = await response.json().catch(() => ({}));
      updatePhotosToggle(Boolean(data.enabled));
    } catch (error) {
      if (lastUpdate) {
        lastUpdate.textContent = error.message;
      }
    } finally {
      photosToggle.disabled = false;
    }
  });
}

loadRsvps();
setInterval(loadRsvps, 5000);
