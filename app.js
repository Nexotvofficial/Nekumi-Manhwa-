/* ============================================================
   NEKUMI — página de inicio
   Todo sale de mangas.json (ver data.js). Nada hardcodeado.
   ============================================================ */

let CATALOG = [];
let activeGenre = 'Todos';
let activeStatus = 'Todos';
let onlyFavorites = false;
let searchTerm = '';

/* ---------- helpers de presentación ---------- */

function ratingOf(m) {
  return Number(m && m.rating) || 0;
}

function chapterCount(m) {
  return Number(m.total_chapters ?? (m.chapters || []).length) || 0;
}

function latestChapter(m) {
  const list = sortedChapters(m, 'desc');
  return list[0] || null;
}

function updatedAt(m) {
  const t = new Date(m && m.last_updated).getTime();
  return Number.isFinite(t) ? t : 0;
}

// "hace 3 días", "hace 2 h", "hoy"
function relativeDate(value) {
  const t = new Date(value).getTime();
  if (!Number.isFinite(t)) return '';
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 60) return 'recién';
  const hours = Math.round(mins / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'ayer';
  if (days < 30) return `hace ${days} días`;
  const months = Math.round(days / 30);
  if (months < 12) return `hace ${months} ${months === 1 ? 'mes' : 'meses'}`;
  const years = Math.round(months / 12);
  return `hace ${years} ${years === 1 ? 'año' : 'años'}`;
}

function readerHref(mangaId, chapterId) {
  return `reader.html?id=${encodeURIComponent(mangaId)}&chap=${encodeURIComponent(chapterId)}`;
}

function mangaHref(mangaId) {
  return `manga.html?id=${encodeURIComponent(mangaId)}`;
}

/* ---------- tarjeta reutilizable (también la usa manga.js) ---------- */

function cardHTML(manga) {
  if (!manga || !manga.id) return '';
  const sClass = statusClass(manga.status);
  const badgeLabel = sClass === 'ongoing' ? 'En emisión' : sClass === 'finished' ? 'Finalizado' : (manga.status || '');
  const fav = isFavorite(manga.id);
  const cover = manga.cover_thumb || manga.cover || '';
  const last = latestChapter(manga);
  return `
    <div class="card">
      <a class="card-link" href="${mangaHref(manga.id)}">
        <div class="cover">
          ${cover
            ? `<img src="${escapeHtml(cover)}" alt="Portada de ${escapeHtml(manga.title)}" loading="lazy">`
            : `<div class="cover-fallback">${escapeHtml((manga.title || '?').slice(0, 1))}</div>`}
          ${badgeLabel ? `<span class="badge ${sClass}">${escapeHtml(badgeLabel)}</span>` : ''}
          ${ratingOf(manga) ? `<span class="rating">★ ${ratingOf(manga).toFixed(1)}</span>` : ''}
        </div>
        <h3>${escapeHtml(manga.title || 'Sin título')}</h3>
        <p class="meta">${last ? escapeHtml(last.title) : `${chapterCount(manga)} caps`}</p>
      </a>
      <button class="fav-toggle ${fav ? 'active' : ''}" data-fav-id="${escapeHtml(manga.id)}" type="button" aria-label="Guardar en favoritos" title="Favorito">${fav ? '♥' : '♡'}</button>
    </div>
  `;
}

function bindFavButtons(root) {
  if (!root) return;
  root.querySelectorAll('.fav-toggle[data-fav-id]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const id = btn.dataset.favId;
      const nowFav = toggleFavorite(id);
      btn.classList.toggle('active', nowFav);
      btn.textContent = nowFav ? '♥' : '♡';
      showToast(nowFav ? 'Guardado en favoritos' : 'Quitado de favoritos', { icon: nowFav ? '♥' : '♡', duration: 1600 });
    });
  });
}

/* ============================================================
   Destacado (portada)
   ============================================================ */

let spotPicks = [];
let spotIndex = 0;
let spotTimer = null;

function buildSpotPicks(list) {
  return [...list]
    .sort((a, b) => (ratingOf(b) - ratingOf(a)) || (updatedAt(b) - updatedAt(a)))
    .slice(0, 8);
}

function renderSpotlight() {
  const manga = spotPicks[spotIndex];
  if (!manga) return;

  const cover = manga.cover || manga.cover_thumb || '';
  const last = latestChapter(manga);
  const progress = getProgress(manga.id);
  const resumeChapter = progress ? getChapter(manga, progress.chapterId) : null;
  const firstChapter = sortedChapters(manga, 'asc')[0];
  const cta = resumeChapter
    ? { href: readerHref(manga.id, resumeChapter.id), label: `Continuar · ${resumeChapter.title}` }
    : firstChapter
      ? { href: readerHref(manga.id, firstChapter.id), label: 'Empezar a leer' }
      : { href: mangaHref(manga.id), label: 'Ver el título' };

  document.getElementById('spotBackdrop').style.backgroundImage = cover ? `url("${cover}")` : 'none';

  const genres = (manga.genres || []).slice(0, 3);
  document.getElementById('spotCopy').innerHTML = `
    <p class="spot-kicker">${escapeHtml(statusClass(manga.status) === 'ongoing' ? 'En emisión' : (manga.status || 'En el catálogo'))}${last ? ` · ${escapeHtml(last.title)}` : ''}</p>
    <h1 class="spot-title">${escapeHtml(manga.title || '')}</h1>
    <div class="spot-meta">
      ${ratingOf(manga) ? `<span class="spot-rating">★ ${ratingOf(manga).toFixed(1)}</span>` : ''}
      <span>${chapterCount(manga)} capítulos</span>
      ${manga.last_updated ? `<span>actualizado ${escapeHtml(relativeDate(manga.last_updated))}</span>` : ''}
    </div>
    ${manga.synopsis ? `<p class="spot-synopsis">${escapeHtml(String(manga.synopsis).slice(0, 220))}${String(manga.synopsis).length > 220 ? '…' : ''}</p>` : ''}
    ${genres.length ? `<div class="spot-genres">${genres.map((g) => `<span>${escapeHtml(g)}</span>`).join('')}</div>` : ''}
    <div class="spot-ctas">
      <a class="btn" href="${cta.href}">${escapeHtml(cta.label)}</a>
      <a class="btn ghost" href="${mangaHref(manga.id)}">Ver capítulos</a>
    </div>
  `;

  const coverEl = document.getElementById('spotCover');
  coverEl.href = mangaHref(manga.id);
  coverEl.removeAttribute('aria-hidden');
  coverEl.removeAttribute('tabindex');
  coverEl.setAttribute('aria-label', `Abrir ${manga.title || 'el título'}`);
  coverEl.innerHTML = cover ? `<img src="${escapeHtml(cover)}" alt="Portada de ${escapeHtml(manga.title)}">` : '';

  document.querySelectorAll('#spotRail .spot-thumb').forEach((el, i) => {
    const on = i === spotIndex;
    el.classList.toggle('active', on);
    el.setAttribute('aria-current', on ? 'true' : 'false');
  });
}

function goToSpot(i) {
  spotIndex = (i + spotPicks.length) % spotPicks.length;
  renderSpotlight();
}

function startSpotAutoplay() {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || spotPicks.length < 2) return;
  stopSpotAutoplay();
  spotTimer = setInterval(() => {
    if (document.hidden) return;
    goToSpot(spotIndex + 1);
  }, 8000);
}

function stopSpotAutoplay() {
  if (spotTimer) clearInterval(spotTimer);
  spotTimer = null;
}

function initSpotlight(list) {
  spotPicks = buildSpotPicks(list);
  if (spotPicks.length === 0) {
    document.getElementById('spotlight').hidden = true;
    return;
  }

  document.getElementById('spotRail').innerHTML = spotPicks.map((m, i) => `
    <li>
      <button class="spot-thumb${i === 0 ? ' active' : ''}" data-spot="${i}" type="button" aria-label="Destacar ${escapeHtml(m.title || '')}">
        <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
      </button>
    </li>
  `).join('');

  document.getElementById('spotRail').querySelectorAll('.spot-thumb').forEach((btn) => {
    btn.addEventListener('click', () => {
      goToSpot(Number(btn.dataset.spot));
      startSpotAutoplay();
    });
  });

  document.getElementById('spotPrev').addEventListener('click', () => { goToSpot(spotIndex - 1); startSpotAutoplay(); });
  document.getElementById('spotNext').addEventListener('click', () => { goToSpot(spotIndex + 1); startSpotAutoplay(); });

  const spot = document.getElementById('spotlight');
  spot.addEventListener('mouseenter', stopSpotAutoplay);
  spot.addEventListener('mouseleave', startSpotAutoplay);
  spot.addEventListener('focusin', stopSpotAutoplay);
  spot.addEventListener('focusout', startSpotAutoplay);

  renderSpotlight();
  startSpotAutoplay();
}

/* ============================================================
   Tendencias (carrusel horizontal)
   ============================================================ */

function renderTrending(list) {
  const rail = document.getElementById('trendRail');
  const picks = [...list]
    .sort((a, b) => (ratingOf(b) - ratingOf(a)) || (chapterCount(b) - chapterCount(a)))
    .slice(0, 14);
  rail.innerHTML = picks.map((m) => `<div class="rail-item">${cardHTML(m)}</div>`).join('');
  bindFavButtons(rail);

  const step = () => Math.max(240, Math.round(rail.clientWidth * 0.8));
  document.getElementById('trendPrev').addEventListener('click', () => rail.scrollBy({ left: -step(), behavior: 'smooth' }));
  document.getElementById('trendNext').addEventListener('click', () => rail.scrollBy({ left: step(), behavior: 'smooth' }));
}

/* ============================================================
   Últimas actualizaciones
   ============================================================ */

function renderUpdates(list) {
  const rows = [...list].sort((a, b) => updatedAt(b) - updatedAt(a)).slice(0, 8);
  document.getElementById('updatesNote').textContent = rows.length ? `${rows.length} títulos` : '';
  document.getElementById('updateList').innerHTML = rows.map((m) => {
    const chaps = sortedChapters(m, 'desc').slice(0, 3);
    return `
      <li class="update-row">
        <a class="update-cover" href="${mangaHref(m.id)}" tabindex="-1" aria-hidden="true">
          <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
        </a>
        <div class="update-body">
          <a class="update-title" href="${mangaHref(m.id)}">${escapeHtml(m.title || '')}</a>
          <div class="update-chaps">
            ${chaps.map((c) => `
              <a class="chap-pill${isChapterRead(m.id, c.id) ? ' read' : ''}" href="${readerHref(m.id, c.id)}">${escapeHtml(c.title)}</a>
            `).join('') || '<span class="update-empty">Sin capítulos todavía</span>'}
          </div>
        </div>
        <span class="update-time">${escapeHtml(relativeDate(m.last_updated))}</span>
      </li>
    `;
  }).join('');
}

/* ============================================================
   Ranking lateral
   ============================================================ */

const RANKERS = {
  rating: (a, b) => ratingOf(b) - ratingOf(a),
  chapters: (a, b) => chapterCount(b) - chapterCount(a),
  fresh: (a, b) => updatedAt(b) - updatedAt(a),
};

function rankSubtitle(mode, m) {
  if (mode === 'chapters') return `${chapterCount(m)} capítulos`;
  if (mode === 'fresh') return relativeDate(m.last_updated) || `${chapterCount(m)} capítulos`;
  return (m.genres || []).slice(0, 2).join(' · ') || (m.category || '');
}

function renderRanking(list, mode) {
  const picks = [...list].sort(RANKERS[mode] || RANKERS.rating).slice(0, 8);
  document.getElementById('rankList').innerHTML = picks.map((m, i) => `
    <li class="rank-row">
      <span class="rank-num${i < 3 ? ' top' : ''}">${i + 1}</span>
      <a class="rank-cover" href="${mangaHref(m.id)}" tabindex="-1" aria-hidden="true">
        <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
      </a>
      <div class="rank-body">
        <a class="rank-title" href="${mangaHref(m.id)}">${escapeHtml(m.title || '')}</a>
        <span class="rank-sub">${escapeHtml(rankSubtitle(mode, m))}</span>
        ${ratingOf(m) ? `<span class="rank-rating">★ ${ratingOf(m).toFixed(1)}</span>` : ''}
      </div>
    </li>
  `).join('');
}

function initRanking(list) {
  const tabs = document.getElementById('rankTabs');
  tabs.querySelectorAll('.side-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      tabs.querySelectorAll('.side-tab').forEach((b) => {
        const on = b === btn;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      renderRanking(list, btn.dataset.rank);
    });
  });
  renderRanking(list, 'rating');
}

/* ============================================================
   Números del catálogo
   ============================================================ */

function renderHeroStats(list) {
  const el = document.getElementById('heroStats');
  if (!el) return;
  const totalChapters = list.reduce((sum, m) => sum + chapterCount(m), 0);
  const ongoing = list.filter((m) => statusClass(m.status) === 'ongoing').length;
  const genreCount = Math.max(collectGenres(list).length - 1, 0); // -1 por "Todos"
  const rows = [
    ['Títulos', list.length],
    ['Capítulos', totalChapters],
    ['En emisión', ongoing],
    ['Géneros', genreCount],
  ];
  el.innerHTML = rows.map(([label, value]) => `
    <div class="stat-row"><span>${label}</span><strong>${value}</strong></div>
  `).join('');
}

/* ============================================================
   Seguir leyendo
   ============================================================ */

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
      <a class="shelf-item" href="${readerHref(manga.id, p.chapterId)}">
        <div class="cover">
          <img src="${escapeHtml(manga.cover_thumb || manga.cover || '')}" alt="" loading="lazy">
          <div class="progress-bar"><span style="width:${pct}%"></span></div>
        </div>
        <h4>${escapeHtml(manga.title)}</h4>
        <p>${chap ? escapeHtml(chap.title) : ''}</p>
      </a>
    `;
  }).join('');
}

/* ============================================================
   Catálogo + filtros
   ============================================================ */

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

/* ============================================================
   Buscador
   ============================================================ */

function renderSearchSuggestions() {
  const box = document.getElementById('searchSuggestions');
  if (!box) return;
  if (!searchTerm) { box.hidden = true; box.innerHTML = ''; return; }
  const matches = CATALOG.filter((m) => (m.title || '').toLowerCase().includes(searchTerm)).slice(0, 6);
  if (matches.length === 0) { box.hidden = true; box.innerHTML = ''; return; }
  box.hidden = false;
  box.innerHTML = matches.map((m) => `
    <a class="suggestion" href="${mangaHref(m.id)}">
      <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
      <span>${escapeHtml(m.title)}</span>
    </a>
  `).join('');
}

function hideSearchSuggestions() {
  const box = document.getElementById('searchSuggestions');
  if (box) box.hidden = true;
}

/* ============================================================
   Arranque
   ============================================================ */

async function init() {
  if (!document.getElementById('spotlight')) return; // no es la página de inicio

  try {
    CATALOG = await fetchCatalog();
  } catch (e) {
    document.querySelector('main').innerHTML = `
      <div class="wrap error-state">
        <h3>El catálogo no cargó</h3>
        <p>Puede estar actualizándose en este momento. Probá de nuevo en unos segundos.</p>
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

  initSpotlight(CATALOG);
  renderContinue(CATALOG);
  renderTrending(CATALOG);
  renderUpdates(CATALOG);
  initRanking(CATALOG);
  renderHeroStats(CATALOG);
  refreshGenreChips();
  refreshStatusChips();
  renderFullGrid();

  const input = document.getElementById('searchInput');
  input.addEventListener('input', (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    renderFullGrid();
    renderSearchSuggestions();
  });
  input.addEventListener('focus', renderSearchSuggestions);
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search')) hideSearchSuggestions();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideSearchSuggestions();
  });

  // el progreso puede cambiar en otra pestaña (o al volver del lector)
  document.addEventListener('nekumi:progress-changed', () => renderContinue(CATALOG));
}

init();
