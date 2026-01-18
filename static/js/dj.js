const topList = document.getElementById("dj-top-list");
const allList = document.getElementById("dj-all-list");
const refreshButton = document.getElementById("dj-refresh");
const lastUpdate = document.getElementById("dj-last-update");

const renderTop = (items) => {
  if (!topList) {
    return;
  }
  topList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "dj-empty";
    empty.textContent = "Aún no hay canciones propuestas.";
    topList.appendChild(empty);
    return;
  }

  items.slice(0, 10).forEach((item, index) => {
    const li = document.createElement("li");
    li.className = "dj-top-item";

    const rank = document.createElement("div");
    rank.className = "dj-rank";
    rank.textContent = String(index + 1);

    const song = document.createElement("div");
    song.className = "dj-song";

    const title = document.createElement("span");
    title.className = "dj-song-title";
    title.textContent = item.title;

    const votes = document.createElement("span");
    votes.className = "dj-song-votes";
    votes.textContent = `${item.votes} voto${item.votes === 1 ? "" : "s"}`;

    song.appendChild(title);
    song.appendChild(votes);

    li.appendChild(rank);
    li.appendChild(song);
    topList.appendChild(li);
  });
};

const renderAll = (items) => {
  if (!allList) {
    return;
  }
  allList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "dj-empty";
    empty.textContent = "Aún no hay canciones propuestas.";
    allList.appendChild(empty);
    return;
  }

  const maxVotes = Math.max(...items.map((item) => item.votes), 1);
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "dj-bar";

    const head = document.createElement("div");
    head.className = "dj-bar-head";

    const title = document.createElement("span");
    title.className = "dj-bar-title";
    title.textContent = item.title;

    const votes = document.createElement("span");
    votes.className = "dj-bar-votes";
    votes.textContent = `${item.votes} voto${item.votes === 1 ? "" : "s"}`;

    head.appendChild(title);
    head.appendChild(votes);

    const track = document.createElement("div");
    track.className = "dj-bar-track";

    const fill = document.createElement("div");
    fill.className = "dj-bar-fill";
    fill.style.width = `${Math.round((item.votes / maxVotes) * 100)}%`;

    track.appendChild(fill);
    card.appendChild(head);
    card.appendChild(track);
    allList.appendChild(card);
  });
};

const loadSongs = async () => {
  try {
    const response = await fetch("/api/songs");
    if (!response.ok) {
      throw new Error("No se pudieron cargar las canciones");
    }
    const data = await response.json();
    const items = data.items || [];
    renderTop(items);
    renderAll(items);
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
  refreshButton.addEventListener("click", loadSongs);
}

loadSongs();
setInterval(loadSongs, 7000);
