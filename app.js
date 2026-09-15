/* ============================================================
   NEKUMI v12 — página de inicio (fix skeletons + populares)
   ============================================================ */

let CATALOG = [];
let activeGenre = 'Todos';
let activeStatus = 'Todos';
let onlyFavorites = false;
let searchTerm = '';

let HERO_PICKS = [];
let heroIndex = 0;
let heroTimer = null;
let popularTab = 'semana';

/* ---------- tarjeta ---------- */

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

/* ---------- fechas ---------- */

function parseNekumiDate(dateStr) {
  const d = new Date(String(dateStr || '').replace(' UTC', 'Z').replace(' ', 'T'));
  return isNaN(d.getTime()) ? new Date(0) : d;
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - parseNekumiDate(dateStr).getTime();
  if (isNaN(diff) || diff < 0) return '';
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'ahora mismo';
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `hace ${h} h`;
  const days = Math.floor(h / 24);
  if (days < 7) return `hace ${days} día${days > 1 ? 's' : ''}`;
  const w = Math.floor(days / 7);
  if (w < 5) return `hace ${w} sem`;
  const mo = Math.floor(days / 30);
  return `hace ${mo} mes${mo > 1 ? 'es' : ''}`;
}

/* ---------- HERO carrusel ---------- */

function heroSlideHTML(m, i) {
  const cover = m.cover_thumb || m.cover || '';
  const chaps = sortedChapters(m, 'desc');
  const latest = chaps[0];
  const readHref = latest
    ? `reader.html?id=${encodeURIComponent(m.id)}&chap=${encodeURIComponent(latest.id)}`
    : `manga.html?id=${encodeURIComponent(m.id)}`;
  return `
    <article class="hero-slide ${i === 0 ? 'active' : ''}" data-slide="${i}">
      <div class="hero-slide-bg" style="background-image:url('${escapeHtml(cover)}')"></div>
      <div class="wrap hero-slide-inner">
        <div class="hero-slide-cover">
          ${cover ? `<img src="${escapeHtml(cover)}" alt="Portada de ${escapeHtml(m.title)}">` : ''}
        </div>
        <div class="hero-slide-info">
          <span class="hero-eyebrow">${m.featured ? '★ Destacado' : '🔥 En tendencia'}</span>
          <h2 class="hero-slide-title">${escapeHtml(m.title || 'Sin título')}</h2>
          <div class="hero-slide-meta">
            ${m.rating ? `<span class="rating-inline">★ ${Number(m.rating).toFixed(1)}</span>` : ''}
            <span>${escapeHtml(m.status || '')}</span>
            <span>${m.total_chapters ?? (m.chapters || []).length} capítulos</span>
          </div>
          <div class="hero-slide-genres">
            ${(m.genres || []).slice(0, 4).map((g) => `<span class="tag">${escapeHtml(g)}</span>`).join('')}
          </div>
          <div class="hero-ctas">
            <a class="btn" href="${readHref}">▶ Leer ahora</a>
            <a class="btn ghost" href="manga.html?id=${encodeURIComponent(m.id)}">Ver ficha</a>
          </div>
        </div>
      </div>
    </article>
  `;
}

function goToSlide(i) {
  if (HERO_PICKS.length === 0) return;
  heroIndex = (i + HERO_PICKS.length) % HERO_PICKS.length;
  document.querySelectorAll('.hero-slide').forEach((s, idx) => s.classList.toggle('active', idx === heroIndex));
  document.querySelectorAll('.hero-dot').forEach((d, idx) => d.classList.toggle('active', idx === heroIndex));
}

function restartHeroTimer() {
  clearInterval(heroTimer);
  if (HERO_PICKS.length > 1) heroTimer = setInterval(() => goToSlide(heroIndex + 1), 6000);
}

function renderHero(list) {
  const box = document.getElementById('heroSlides');
  if (!box) return;
  HERO_PICKS = [...list]
    .sort((a, b) => ((b.featured ? 1 : 0) - (a.featured ? 1 : 0)) || ((b.rating || 0) - (a.rating || 0)))
    .slice(0, 6);
  if (HERO_PICKS.length === 0) { document.getElementById('heroCarousel').hidden = true; return; }
  box.innerHTML = HERO_PICKS.map(heroSlideHTML).join('');

  const dots = document.getElementById('heroDots');
  const prev = document.getElementById('heroPrev');
  const next = document.getElementById('heroNext');
  dots.innerHTML = HERO_PICKS
    .map((_, i) => `<button class="hero-dot ${i === 0 ? 'active' : ''}" data-slide="${i}" type="button" aria-label="Ir al destacado ${i + 1}"></button>`)
    .join('');

  // con una sola slide no hay nada que rotar: ocultamos flechas/puntos
  const single = HERO_PICKS.length <= 1;
  prev.hidden = single;
  next.hidden = single;
  dots.hidden = single;

  prev.addEventListener('click', () => { goToSlide(heroIndex - 1); restartHeroTimer(); });
  next.addEventListener('click', () => { goToSlide(heroIndex + 1); restartHeroTimer(); });
  dots.addEventListener('click', (e) => {
    const dot = e.target.closest('.hero-dot');
    if (dot) { goToSlide(Number(dot.dataset.slide)); restartHeroTimer(); }
  });

  const carousel = document.getElementById('heroCarousel');
  carousel.addEventListener('mouseenter', () => clearInterval(heroTimer));
  carousel.addEventListener('mouseleave', restartHeroTimer);
  restartHeroTimer();
}

/* ---------- Trending ---------- */

function renderTrending(list) {
  const el = document.getElementById('trendingGrid');
  if (!el) return;
  const top = [...list].sort((a, b) => (b.rating || 0) - (a.rating || 0)).slice(0, 5);
  el.innerHTML = top.map((m, i) => `
    <div class="trending-card">
      <span class="rank-num">${i + 1}</span>
      ${cardHTML(m)}
    </div>
  `).join('');
  bindFavButtons(el);
}

/* ---------- Últimas actualizaciones ---------- */

function latestItemHTML(m) {
  const cover = m.cover_thumb || m.cover || '';
  const chaps = sortedChapters(m, 'desc').slice(0, 3);
  return `
    <article class="latest-item">
      <a class="latest-cover" href="manga.html?id=${encodeURIComponent(m.id)}">
        ${cover ? `<img src="${escapeHtml(cover)}" alt="" loading="lazy">` : `<div class="cover-fallback">${escapeHtml((m.title || '?').slice(0, 1))}</div>`}
      </a>
      <div class="latest-info">
        <a class="latest-title" href="manga.html?id=${encodeURIComponent(m.id)}">${escapeHtml(m.title || 'Sin título')}</a>
        <div class="latest-chapters">
          ${chaps.map((c) => `
            <a class="latest-chap" href="reader.html?id=${encodeURIComponent(m.id)}&chap=${encodeURIComponent(c.id)}">
              <span>Capítulo ${escapeHtml(String(c.number))}</span>
              <span class="latest-time">${timeAgo(m.last_updated)}</span>
            </a>
          `).join('')}
        </div>
      </div>
      ${m.rating ? `<span class="latest-rating">★ ${Number(m.rating).toFixed(1)}</span>` : ''}
    </article>
  `;
}

function renderLatest(list) {
  const el = document.getElementById('latestList');
  if (!el) return;
  const fresh = [...list]
    .sort((a, b) => parseNekumiDate(b.last_updated) - parseNekumiDate(a.last_updated))
    .slice(0, 12);
  el.innerHTML = fresh.map(latestItemHTML).join('');
  document.getElementById('freshCount').textContent = `${fresh.length} títulos`;
}

/* ---------- Sidebar populares (v12: pestañas que sí se diferencian) ---------- */

const POPULAR_TABS = {
  semana:  { label: 'Semana',  hint: 'Los actualizados más recientemente' },
  mes:     { label: 'Mes',     hint: 'Los mejor valorados del catálogo' },
  siempre: { label: 'Siempre', hint: 'Rating + trayectoria (capítulos)' },
};

function popularSorted(tab) {
  const list = [...CATALOG];
  if (tab === 'semana') {
    return list.sort((a, b) =>
      (parseNekumiDate(b.last_updated) - parseNekumiDate(a.last_updated)) ||
      ((b.rating || 0) - (a.rating || 0)) ||
      ((b.total_chapters || 0) - (a.total_chapters || 0))
    ).slice(0, 10);
  }
  if (tab === 'mes') {
    return list.sort((a, b) =>
      ((b.rating || 0) - (a.rating || 0)) ||
      (parseNekumiDate(b.last_updated) - parseNekumiDate(a.last_updated))
    ).slice(0, 10);
  }
  return list.sort((a, b) =>
    (((b.rating || 0) * 10) + (b.total_chapters || 0)) - (((a.rating || 0) * 10) + (a.total_chapters || 0))
  ).slice(0, 10);
}

// qué mostrar debajo del título según la pestaña activa, para que se note
// que el orden realmente cambia
function popularMetaHTML(m, tab) {
  if (tab === 'semana') return escapeHtml(timeAgo(m.last_updated) || 'reciente');
  if (tab === 'mes') return m.rating ? `★ ${Number(m.rating).toFixed(1)}` : 'Sin votos todavía';
  const caps = m.total_chapters ?? (m.chapters || []).length;
  return `${m.rating ? `★ ${Number(m.rating).toFixed(1)} · ` : ''}${caps} capítulos`;
}

function renderPopular() {
  const el = document.getElementById('popularList');
  if (!el) return;
  const items = popularSorted(popularTab);
  if (items.length === 0) {
    el.innerHTML = '<li class="popular-empty">Todavía no hay títulos para rankear.</li>';
    return;
  }
  el.innerHTML = items.map((m, i) => `
    <li class="popular-item">
      <span class="popular-rank ${i < 3 ? 'top' : ''}">${i + 1}</span>
      <a class="popular-cover" href="manga.html?id=${encodeURIComponent(m.id)}">
        <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
      </a>
      <div class="popular-info">
        <a class="popular-title" href="manga.html?id=${encodeURIComponent(m.id)}">${escapeHtml(m.title || 'Sin título')}</a>
        <span class="popular-meta">${popularMetaHTML(m, popularTab)}</span>
      </div>
    </li>
  `).join('') + `
    <li class="popular-hint">${escapeHtml(POPULAR_TABS[popularTab].hint)}</li>
  `;
}

function bindPopularTabs() {
  const tabs = document.getElementById('popularTabs');
  if (!tabs) return;
  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('.popular-tab');
    if (!btn) return;
    popularTab = btn.dataset.tab;
    tabs.querySelectorAll('.popular-tab').forEach((b) => b.classList.toggle('active', b === btn));
    renderPopular();
  });
}

/* ---------- Seguir leyendo ---------- */

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

/* ---------- Catálogo ---------- */

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

/* ---------- barra de aviso ---------- */

function initTopbarAd() {
  const bar = document.getElementById('topbarAd');
  const btn = document.getElementById('topbarAdClose');
  if (!bar || !btn) return;
  try {
    if (localStorage.getItem('nekumi_topbar_dismissed')) { bar.hidden = true; return; }
  } catch { /* sin storage */ }
  btn.addEventListener('click', () => {
    bar.hidden = true;
    try { localStorage.setItem('nekumi_topbar_dismissed', '1'); } catch { /* sin storage */ }
  });
}

/* ---------- carga del catálogo con timeout ---------- */

function fetchCatalogWithTimeout(ms) {
  return Promise.race([
    fetchCatalog(),
    new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms)),
  ]);
}

function renderLoadError() {
  ['heroCarousel'].forEach((id) => { const el = document.getElementById(id); if (el) el.hidden = true; });
  const main = document.querySelector('.home-main');
  if (main) {
    main.innerHTML = `
      <div class="error-state">
        <h3>No pudimos cargar el catálogo</h3>
        <p>Puede ser algo momentáneo (el catálogo se está actualizando o el CDN está lento). Probá de nuevo.</p>
        <button class="btn" id="retryLoadBtn" type="button">Reintentar</button>
      </div>`;
    document.getElementById('retryLoadBtn').addEventListener('click', () => window.location.reload());
  }
}

/* ---------- init ---------- */

async function init() {
  if (!document.getElementById('heroSlides')) return;
  initTopbarAd();
  try {
    CATALOG = await fetchCatalogWithTimeout(12000);
  } catch (e) {
    console.warn('[Nekumi] Falló la carga del catálogo:', e);
    renderLoadError();
    return;
  }

  const genres = collectGenres(CATALOG);
  const statuses = collectStatuses(CATALOG);

  function refreshGenreChips() {
    renderChips('genreChips', genres, activeGenre, (v) => { activeGenre = v; refreshGenreChips(); renderFullGrid(); });
  }
  function refreshStatusChips() {
    renderChips('statusChips', statuses, activeStatus, (v) => { activeStatus = v; refreshStatusChips(); renderFullGrid(); });
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

  renderHero(CATALOG);
  renderContinue(CATALOG);
  renderTrending(CATALOG);
  renderLatest(CATALOG);
  renderPopular();
  bindPopularTabs();
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
  document.getElementById('searchSuggestions').hidden = true;
}

init();
