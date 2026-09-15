/* ============================================================
   NEKUMI — página de inicio
   ============================================================ */

let CATALOG = [];
let activeGenre = 'Todos';
let activeStatus = 'Todos';
let onlyFavorites = false;
let searchTerm = '';

function cardHTML(manga) {
  if (!manga || !manga.id) return '';
  const chapters = manga.chapters || [];
  const sClass = statusClass(manga.status);
  const badgeLabel = sClass === 'ongoing' ? 'En emisión' : sClass === 'finished' ? 'Finalizado' : (manga.status || '');
  const fav = isFavorite(manga.id);
  const isHot = Number(manga.rating) >= 4.5;
  const cover = manga.cover_thumb || manga.cover || '';
  return `
    <div class="card">
      <a class="card-link" href="manga.html?id=${encodeURIComponent(manga.id)}">
        <div class="cover">
          ${cover ? `<img src="${escapeHtml(cover)}" alt="Portada de ${escapeHtml(manga.title)}" loading="lazy">` : `<div class="cover-fallback">${escapeHtml((manga.title || '?').slice(0, 1))}</div>`}
          ${badgeLabel ? `<span class="badge ${sClass}">${escapeHtml(badgeLabel)}</span>` : ''}
          ${isHot ? '<span class="hot-tag" title="Muy bien valorado">🔥</span>' : ''}
          ${manga.rating ? `<span class="rating">★ ${Number(manga.rating).toFixed(1)}</span>` : ''}
        </div>
        <h3>${escapeHtml(manga.title || 'Sin título')}</h3>
        <p class="meta">${escapeHtml(manga.total_chapters ?? chapters.length)} caps · ${escapeHtml(manga.category || '')}</p>
      </a>
      <button class="fav-toggle ${fav ? 'active' : ''}" data-fav-id="${escapeHtml(manga.id)}" type="button" aria-label="Marcar como favorito" title="Favorito">${fav ? '♥' : '♡'}</button>
    </div>
  `;
}

function bindFavButtons(root) {
  root.querySelectorAll('.fav-toggle').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const id = btn.dataset.favId;
      const nowFav = toggleFavorite(id);
      btn.classList.toggle('active', nowFav);
      btn.textContent = nowFav ? '♥' : '♡';
      showToast(nowFav ? 'Agregado a favoritos' : 'Quitado de favoritos', { icon: nowFav ? '♥' : '♡', duration: 1600 });
    });
  });
}

function renderHeroStats(list) {
  const el = document.getElementById('heroStats');
  if (!el) return;
  const totalTitles = list.length;
  const totalChapters = list.reduce((sum, m) => sum + (m.total_chapters ?? (m.chapters || []).length), 0);
  const genreCount = collectGenres(list).length - 1; // -1 por "Todos"
  const ongoing = list.filter((m) => statusClass(m.status) === 'ongoing').length;
  el.innerHTML = `
    <span class="stat-pill"><strong>${totalTitles}</strong> títulos</span>
    <span class="stat-pill"><strong>${totalChapters}</strong> capítulos</span>
    <span class="stat-pill"><strong>${ongoing}</strong> en emisión</span>
    <span class="stat-pill"><strong>${genreCount}</strong> géneros</span>
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
  const section = document.getElementById('novedades');
  if (list.length <= MIN_TITLES_FOR_FRESH_SECTION) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  const fresh = [...list]
    .sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated))
    .slice(0, 10);
  document.getElementById('freshGrid').innerHTML = fresh.map(cardHTML).join('');
  document.getElementById('freshCount').textContent = `${fresh.length} títulos`;
  bindFavButtons(document.getElementById('freshGrid'));
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
    if (onlyFavorites && !isFavorite(m.id)) return false;
    if (searchTerm && !(m.title || '').toLowerCase().includes(searchTerm)) return false;
    return true;
  });
}

function renderFullGrid() {
  const filtered = applyFilters(CATALOG);
  document.getElementById('fullGrid').innerHTML = filtered.map(cardHTML).join('');
  document.getElementById('totalCount').textContent = `${filtered.length} títulos`;
  document.getElementById('emptyState').hidden = filtered.length !== 0;
  bindFavButtons(document.getElementById('fullGrid'));
}

async function init() {
  if (!document.getElementById('heroStrip')) return; // no es la página de inicio
  try {
    CATALOG = await fetchCatalog();
  } catch (e) {
    document.querySelector('main').innerHTML = `
      <div class="wrap error-state">
        <h3>No pudimos cargar el catálogo</h3>
        <p>Puede ser algo momentáneo (el catálogo se está actualizando). Probá de nuevo en unos segundos.</p>
        <button class="btn" id="retryLoadBtn" type="button">Reintentar</button>
      </div>`;
    document.getElementById('retryLoadBtn').addEventListener('click', () => window.location.reload());
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

  function refreshFavChip() {
    const el = document.getElementById('favChip');
    el.classList.toggle('active', onlyFavorites);
    el.textContent = onlyFavorites ? '♥ Viendo solo favoritos' : '♡ Solo favoritos';
  }

  document.getElementById('favChip').addEventListener('click', () => {
    onlyFavorites = !onlyFavorites;
    refreshFavChip();
    renderFullGrid();
  });
  refreshFavChip();

  document.getElementById('menuToggle').addEventListener('click', () => {
    document.querySelector('.nav').classList.toggle('menu-open');
  });

  renderHeroStats(CATALOG);
  renderHeroStrip(CATALOG);
  renderContinue(CATALOG);
  renderFresh(CATALOG);
  refreshGenreChips();
  refreshStatusChips();
  renderFullGrid();

  document.getElementById('searchInput').addEventListener('input', (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    renderFullGrid();
    renderSearchSuggestions();
  });
  document.getElementById('searchInput').addEventListener('focus', renderSearchSuggestions);
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search')) hideSearchSuggestions();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideSearchSuggestions();
  });
}

function renderSearchSuggestions() {
  const box = document.getElementById('searchSuggestions');
  if (!searchTerm) { box.hidden = true; box.innerHTML = ''; return; }
  const matches = CATALOG.filter((m) => (m.title || '').toLowerCase().includes(searchTerm)).slice(0, 6);
  if (matches.length === 0) { box.hidden = true; box.innerHTML = ''; return; }
  box.hidden = false;
  box.innerHTML = matches.map((m) => `
    <a class="suggestion" href="manga.html?id=${encodeURIComponent(m.id)}">
      <img src="${escapeHtml(m.cover_thumb || m.cover)}" alt="" loading="lazy">
      <span>${escapeHtml(m.title)}</span>
    </a>
  `).join('');
}

function hideSearchSuggestions() {
  const box = document.getElementById('searchSuggestions');
  box.hidden = true;
}

init();
