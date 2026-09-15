/* ============================================================
   NEKUMI — página de inicio
   ============================================================ */

let CATALOG = [];
let activeGenre = 'Todos';
let activeStatus = 'Todos';
let searchTerm = '';

function cardHTML(manga) {
  const sClass = statusClass(manga.status);
  const badgeLabel = sClass === 'ongoing' ? 'En emisión' : sClass === 'finished' ? 'Finalizado' : manga.status;
  return `
    <a class="card" href="manga.html?id=${encodeURIComponent(manga.id)}">
      <div class="cover">
        <img src="${escapeHtml(manga.cover_thumb || manga.cover)}" alt="Portada de ${escapeHtml(manga.title)}" loading="lazy">
        ${badgeLabel ? `<span class="badge ${sClass}">${escapeHtml(badgeLabel)}</span>` : ''}
        ${manga.rating ? `<span class="rating">★ ${Number(manga.rating).toFixed(1)}</span>` : ''}
      </div>
      <h3>${escapeHtml(manga.title)}</h3>
      <p class="meta">${escapeHtml(manga.total_chapters ?? manga.chapters.length)} caps · ${escapeHtml(manga.category)}</p>
    </a>
  `;
}

function renderHeroStrip(list) {
  const el = document.getElementById('heroStrip');
  const picks = [...list].sort((a, b) => (b.rating || 0) - (a.rating || 0)).slice(0, 5);
  if (picks.length === 0) return;
  el.innerHTML = picks.map((m) => `
    <a href="manga.html?id=${encodeURIComponent(m.id)}" tabindex="-1">
      <img src="${escapeHtml(m.cover_thumb || m.cover)}" alt="" loading="lazy">
    </a>
  `).join('');
}

function renderContinue(list) {
  const items = getAllProgress()
    .map((p) => ({ p, manga: getMangaById(list, p.mangaId) }))
    .filter((x) => x.manga)
    .slice(0, 8);

  const section = document.getElementById('continuar');
  if (items.length === 0) { section.hidden = true; return; }
  section.hidden = false;

  document.getElementById('continueShelf').innerHTML = items.map(({ p, manga }) => {
    const chap = getChapter(manga, p.chapterId);
    const pct = Math.round((p.scrollFraction || 0) * 100);
    return `
      <a class="shelf-item" href="reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(p.chapterId)}">
        <div class="cover">
          <img src="${escapeHtml(manga.cover_thumb || manga.cover)}" alt="" loading="lazy">
          <div class="progress-bar"><span style="width:${pct}%"></span></div>
        </div>
        <h4>${escapeHtml(manga.title)}</h4>
        <p>${chap ? escapeHtml(chap.title) : ''}</p>
      </a>
    `;
  }).join('');
}

function renderFresh(list) {
  const fresh = [...list]
    .sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated))
    .slice(0, 10);
  document.getElementById('freshGrid').innerHTML = fresh.map(cardHTML).join('');
  document.getElementById('freshCount').textContent = `${fresh.length} títulos`;
}

function collectGenres(list) {
  const set = new Set();
  list.forEach((m) => (m.genres || []).forEach((g) => set.add(g)));
  return ['Todos', ...Array.from(set).sort()];
}

function collectStatuses(list) {
  const set = new Set();
  list.forEach((m) => m.status && set.add(m.status));
  return ['Todos', ...Array.from(set)];
}

function renderChips(containerId, values, active, onPick) {
  const el = document.getElementById(containerId);
  el.innerHTML = values.map((v) => `
    <button class="chip ${v === active ? 'active' : ''}" data-value="${escapeHtml(v)}" type="button">${escapeHtml(v)}</button>
  `).join('');
  el.querySelectorAll('.chip').forEach((btn) => {
    btn.addEventListener('click', () => onPick(btn.dataset.value));
  });
}

function applyFilters(list) {
  return list.filter((m) => {
    if (activeGenre !== 'Todos' && !(m.genres || []).includes(activeGenre)) return false;
    if (activeStatus !== 'Todos' && m.status !== activeStatus) return false;
    if (searchTerm && !m.title.toLowerCase().includes(searchTerm)) return false;
    return true;
  });
}

function renderFullGrid() {
  const filtered = applyFilters(CATALOG);
  document.getElementById('fullGrid').innerHTML = filtered.map(cardHTML).join('');
  document.getElementById('totalCount').textContent = `${filtered.length} títulos`;
  document.getElementById('emptyState').hidden = filtered.length !== 0;
}

async function init() {
  try {
    CATALOG = await fetchCatalog();
  } catch (e) {
    document.querySelector('main').innerHTML = `
      <div class="wrap error-state">
        <h3>No pudimos cargar el catálogo</h3>
        <p>Revisá que mangas.json exista en la raíz del sitio.</p>
      </div>`;
    return;
  }

  const genres = collectGenres(CATALOG);
  const statuses = collectStatuses(CATALOG);

  function refreshGenreChips() {
    renderChips('genreChips', genres, activeGenre, (v) => {
      activeGenre = v;
      refreshGenreChips();
      renderFullGrid();
    });
  }

  function refreshStatusChips() {
    renderChips('statusChips', statuses, activeStatus, (v) => {
      activeStatus = v;
      refreshStatusChips();
      renderFullGrid();
    });
  }

  renderHeroStrip(CATALOG);
  renderContinue(CATALOG);
  renderFresh(CATALOG);
  refreshGenreChips();
  refreshStatusChips();
  renderFullGrid();

  document.getElementById('searchInput').addEventListener('input', (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    renderFullGrid();
  });
}

init();
