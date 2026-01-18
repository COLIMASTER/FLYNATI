const key = window.ADMIN_KEY || "";
const tbody = document.getElementById("rsvp-body");
const refreshButton = document.getElementById("refresh");
const statTotal = document.getElementById("stat-total");
const statYes = document.getElementById("stat-yes");
const statNo = document.getElementById("stat-no");
const statBus = document.getElementById("stat-bus");
const lastUpdate = document.getElementById("last-update");

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

    const createdAt = (item.created_at || "").replace(" UTC", "");
    row.innerHTML = `
      <td>${item.id}</td>
      <td>${item.name}</td>
      <td><span class="status-pill ${item.attending ? "status-yes" : "status-no"}">${attending}</span></td>
      <td>${item.address || "-"}</td>
      <td><span class="status-pill ${item.bus ? "status-yes" : "status-no"}">${bus}</span></td>
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
    const response = await fetch(`/api/rsvps?key=${encodeURIComponent(key)}`);
    if (!response.ok) {
      throw new Error("No se pudo cargar el panel");
    }
    const data = await response.json();
    const items = data.items || [];
    renderRows(items);
    updateStats(items);
    if (lastUpdate) {
      lastUpdate.textContent = new Date().toLocaleString();
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

loadRsvps();
setInterval(loadRsvps, 5000);
