/* ============================================================
   NEKUMI — lector
   La tira vertical es el contenido; todo lo demás es chrome
   flotante configurable que se aparta cuando no se necesita.
   ============================================================ */

let MANGA = null;
let CHAPTER = null;
let PREFS = readReaderPrefs();
let currentPageIndex = 0;       // usado en modo paginado
let lastScrollY = 0;
let topbarHidden = false;
let autoScrollActive = false;
let autoScrollRAF = null;
let pageObserver = null;

/* ---------- helpers de navegación ---------- */

function neighbourChapters(manga, chapterId) {
  const chaps = sortedChapters(manga, 'asc');
  const idx = chaps.findIndex((c) => c.id === chapterId);
  return {
    prev: idx > 0 ? chaps[idx - 1] : null,
    next: idx >= 0 && idx < chaps.length - 1 ? chaps[idx + 1] : null,
  };
}

function goToChapter(chapterId) {
  window.location.href = `reader.html?id=${encodeURIComponent(MANGA.id)}&chap=${encodeURIComponent(chapterId)}`;
}

/* ---------- chrome: barra superior / progreso ---------- */

function toggleChromeOnScroll() {
  const y = window.scrollY;
  const goingDown = y > lastScrollY && y > 80;
  const topbar = document.getElementById('topbar');

  if (goingDown && !topbarHidden) { topbar.classList.add('hidden'); topbarHidden = true; }
  else if (!goingDown && topbarHidden) { topbar.classList.remove('hidden'); topbarHidden = false; }
  lastScrollY = y;

  updateProgressFromScroll();
}

function updateProgressFromScroll() {
  const doc = document.documentElement;
  const scrollable = doc.scrollHeight - doc.clientHeight;
  const fraction = scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 0;
  document.getElementById('progressFill').style.width = `${fraction * 100}%`;
  saveProgress(MANGA.id, CHAPTER.id, fraction);
  if (fraction >= 0.96) markChapterRead(MANGA.id, CHAPTER.id);
  toggleScrollTopBtn(window.scrollY);
}

function updateProgressFromPage(index, total) {
  const fraction = total > 1 ? index / (total - 1) : 1;
  document.getElementById('progressFill').style.width = `${fraction * 100}%`;
  saveProgress(MANGA.id, CHAPTER.id, fraction);
  if (fraction >= 0.999) markChapterRead(MANGA.id, CHAPTER.id);
}

function toggleScrollTopBtn(y) {
  const btn = document.getElementById('scrollTopBtn');
  if (!btn) return;
  btn.hidden = y < 900;
}

/* ---------- render: modo tira continua ---------- */

function renderStripMode() {
  const el = document.getElementById('readerMain');
  const { next } = neighbourChapters(MANGA, CHAPTER.id);

  const pagesHTML = CHAPTER.pages
    .map((url, i) => `<img class="strip-page" data-page="${i}" src="${escapeHtml(url)}" alt="Página ${i + 1}" loading="${i < 2 ? 'eager' : 'lazy'}">`)
    .join('');

  el.innerHTML = `
    <div class="strip-pages" id="stripPages">${pagesHTML}</div>
    ${endCardHTML(next)}
  `;

  setupPageObserver();
  window.addEventListener('scroll', toggleChromeOnScroll, { passive: true });
  window.scrollTo(0, 0);
}

function setupPageObserver() {
  if (pageObserver) pageObserver.disconnect();
  const imgs = document.querySelectorAll('.strip-page');
  if (imgs.length === 0) return;
  pageObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const idx = Number(entry.target.dataset.page);
        setPageCounter(idx + 1, imgs.length);
      }
    });
  }, { threshold: 0.5 });
  imgs.forEach((img) => pageObserver.observe(img));
}

/* ---------- render: modo paginado ---------- */

function renderPagedMode() {
  const el = document.getElementById('readerMain');
  const total = CHAPTER.pages.length;
  currentPageIndex = Math.min(currentPageIndex, total - 1);

  el.innerHTML = `
    <div class="paged-view" id="pagedView">
      <button class="tap-zone tap-left" id="tapPrev" aria-label="Página anterior"></button>
      <img class="paged-page" id="pagedImg" alt="Página ${currentPageIndex + 1}">
      <button class="tap-zone tap-right" id="tapNext" aria-label="Página siguiente"></button>
    </div>
  `;

  renderPagedImage();

  document.getElementById('tapPrev').addEventListener('click', () => stepPage(-1));
  document.getElementById('tapNext').addEventListener('click', () => stepPage(1));
}

function renderPagedImage() {
  const total = CHAPTER.pages.length;
  const img = document.getElementById('pagedImg');
  img.src = CHAPTER.pages[currentPageIndex];
  img.alt = `Página ${currentPageIndex + 1}`;
  setPageCounter(currentPageIndex + 1, total);
  updateProgressFromPage(currentPageIndex, total);
}

function stepPage(dir) {
  // en modo rtl, el sentido visual de "siguiente" se invierte
  const realDir = PREFS.direction === 'rtl' ? -dir : dir;
  const total = CHAPTER.pages.length;
  const target = currentPageIndex + realDir;

  if (target < 0) {
    const { prev } = neighbourChapters(MANGA, CHAPTER.id);
    if (prev) goToChapter(prev.id);
    return;
  }
  if (target >= total) {
    const { next } = neighbourChapters(MANGA, CHAPTER.id);
    if (next) { goToChapter(next.id); } else { showEndCardInPagedMode(); }
    return;
  }
  currentPageIndex = target;
  renderPagedImage();
}

function showEndCardInPagedMode() {
  const { next } = neighbourChapters(MANGA, CHAPTER.id);
  document.getElementById('readerMain').innerHTML = endCardHTML(next);
}

function endCardHTML(next) {
  return `
    <div class="reader-endcard">
      <h3>Fin de ${escapeHtml(CHAPTER.title)}</h3>
      ${next
        ? `<a class="btn" href="reader.html?id=${encodeURIComponent(MANGA.id)}&chap=${encodeURIComponent(next.id)}">Siguiente capítulo →</a>`
        : `<p>Todavía no hay más capítulos publicados.</p>`}
      <br>
      <a class="btn ghost" href="manga.html?id=${encodeURIComponent(MANGA.id)}">Volver a la ficha</a>
    </div>
  `;
}

function setPageCounter(current, total) {
  const el = document.getElementById('pageCounter');
  el.textContent = PREFS.showPageCount ? `${current} / ${total}` : '';
}

/* ---------- render principal según modo ---------- */

function renderReader() {
  stopAutoScroll();
  if (PREFS.mode === 'paged') {
    renderPagedMode();
  } else {
    renderStripMode();
  }
}

/* ---------- miniaturas ---------- */

function renderThumbDrawer() {
  const drawer = document.getElementById('thumbDrawer');
  drawer.innerHTML = CHAPTER.pages.map((url, i) => `
    <button class="thumb" data-page="${i}" type="button">
      <img src="${escapeHtml(url)}" alt="" loading="lazy">
      <span>${i + 1}</span>
    </button>
  `).join('');
  drawer.querySelectorAll('.thumb').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.page);
      drawer.hidden = true;
      if (PREFS.mode === 'paged') {
        currentPageIndex = idx;
        renderPagedImage();
      } else {
        const target = document.querySelector(`.strip-page[data-page="${idx}"]`);
        if (target) target.scrollIntoView({ block: 'start' });
      }
    });
  });
}

/* ---------- auto-scroll (solo modo tira) ---------- */

function startAutoScroll() {
  if (PREFS.mode !== 'strip') return;
  autoScrollActive = true;
  let last = performance.now();
  function step(now) {
    if (!autoScrollActive) return;
    const dt = (now - last) / 1000;
    last = now;
    window.scrollBy(0, PREFS.autoScrollSpeed * dt);
    autoScrollRAF = requestAnimationFrame(step);
  }
  autoScrollRAF = requestAnimationFrame(step);
}

function stopAutoScroll() {
  autoScrollActive = false;
  if (autoScrollRAF) cancelAnimationFrame(autoScrollRAF);
}

/* ---------- panel de ajustes ---------- */

const READER_THEMES = {
  black:    { bg: '#08060B', surface: '#08060B' },
  charcoal: { bg: '#232228', surface: '#232228' },
  sepia:    { bg: '#E7DEC8', surface: '#E7DEC8' },
  white:    { bg: '#F5F5F5', surface: '#F5F5F5' },
};

function applyPrefsToDOM() {
  document.documentElement.style.setProperty('--reader-width', `${PREFS.width}%`);
  document.documentElement.style.setProperty('--reader-gap', `${PREFS.gap}px`);
  document.getElementById('dimOverlay').style.opacity = PREFS.dim / 100;

  const theme = READER_THEMES[PREFS.theme] || READER_THEMES.black;
  document.documentElement.style.setProperty('--reader-bg', theme.bg);
  document.body.dataset.theme = PREFS.theme;

  document.querySelectorAll('#modeSegment button').forEach((b) => b.classList.toggle('active', b.dataset.value === PREFS.mode));
  document.querySelectorAll('#directionSegment button').forEach((b) => b.classList.toggle('active', b.dataset.value === PREFS.direction));
  document.querySelectorAll('#themeSegment button').forEach((b) => b.classList.toggle('active', b.dataset.value === PREFS.theme));

  document.getElementById('widthBlock').hidden = false;
  document.getElementById('widthLabel').firstChild.textContent = PREFS.mode === 'strip' ? 'Ancho de la tira ' : 'Zoom de página ';
  document.getElementById('gapBlock').hidden = PREFS.mode !== 'strip';
  document.getElementById('autoScrollBlock').hidden = PREFS.mode !== 'strip';
  document.getElementById('directionBlock').hidden = PREFS.mode !== 'paged';

  document.getElementById('widthValue').textContent = `${PREFS.width}%`;
  document.getElementById('gapValue').textContent = `${PREFS.gap}px`;
  document.getElementById('dimValue').textContent = `${PREFS.dim}%`;
  document.getElementById('widthRange').value = PREFS.width;
  document.getElementById('gapRange').value = PREFS.gap;
  document.getElementById('dimRange').value = PREFS.dim;
  document.getElementById('autoScrollSpeed').value = PREFS.autoScrollSpeed;
  document.getElementById('autoScrollToggle').checked = autoScrollActive;
  document.getElementById('pageCountToggle').checked = PREFS.showPageCount;
}

function updatePref(key, value) {
  PREFS = { ...PREFS, [key]: value };
  saveReaderPrefs(PREFS);
}

function bindSettingsPanel() {
  const drawer = document.getElementById('settingsDrawer');

  document.getElementById('settingsBtn').addEventListener('click', () => { drawer.hidden = false; });
  document.getElementById('closeSettings').addEventListener('click', () => { drawer.hidden = true; });

  document.getElementById('modeSegment').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    updatePref('mode', btn.dataset.value);
    applyPrefsToDOM();
    currentPageIndex = 0;
    renderReader();
  });

  document.getElementById('directionSegment').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    updatePref('direction', btn.dataset.value);
    applyPrefsToDOM();
  });

  document.getElementById('themeSegment').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    updatePref('theme', btn.dataset.value);
    applyPrefsToDOM();
  });

  document.getElementById('widthRange').addEventListener('input', (e) => {
    updatePref('width', Number(e.target.value));
    applyPrefsToDOM();
  });
  document.getElementById('gapRange').addEventListener('input', (e) => {
    updatePref('gap', Number(e.target.value));
    applyPrefsToDOM();
  });
  document.getElementById('dimRange').addEventListener('input', (e) => {
    updatePref('dim', Number(e.target.value));
    applyPrefsToDOM();
  });
  document.getElementById('autoScrollSpeed').addEventListener('input', (e) => {
    updatePref('autoScrollSpeed', Number(e.target.value));
  });
  document.getElementById('autoScrollToggle').addEventListener('change', (e) => {
    if (e.target.checked) startAutoScroll(); else stopAutoScroll();
  });
  document.getElementById('pageCountToggle').addEventListener('change', (e) => {
    updatePref('showPageCount', e.target.checked);
    setPageCounter(currentPageIndex + 1, CHAPTER.pages.length);
  });

  document.getElementById('resetPrefs').addEventListener('click', () => {
    PREFS = { ...DEFAULT_READER_PREFS };
    saveReaderPrefs(PREFS);
    applyPrefsToDOM();
    currentPageIndex = 0;
    renderReader();
  });
}

/* ---------- inicialización ---------- */

async function init() {
  const mangaId = qs('id');
  const chapterId = qs('chap');
  let catalog;
  try {
    catalog = await fetchCatalog();
  } catch {
    document.getElementById('readerMain').innerHTML = `<div class="error-state"><h3>No pudimos cargar el catálogo</h3></div>`;
    return;
  }

  MANGA = getMangaById(catalog, mangaId);
  CHAPTER = MANGA ? getChapter(MANGA, chapterId) : null;

  if (!MANGA || !CHAPTER) {
    document.getElementById('readerMain').innerHTML = `
      <div class="error-state">
        <h3>No encontramos ese capítulo</h3>
        <p><a class="btn ghost" href="index.html">Volver al catálogo</a></p>
      </div>`;
    return;
  }

  document.title = `${CHAPTER.title} · ${MANGA.title} — Nekumi`;
  document.getElementById('readerTitle').textContent = `${MANGA.title} · ${CHAPTER.title}`;
  document.getElementById('backLink').href = `manga.html?id=${encodeURIComponent(MANGA.id)}`;

  const favBtn = document.getElementById('favBtn');
  favBtn.textContent = isFavorite(MANGA.id) ? '♥' : '♡';
  favBtn.classList.toggle('active', isFavorite(MANGA.id));
  favBtn.addEventListener('click', () => {
    const nowFav = toggleFavorite(MANGA.id);
    favBtn.textContent = nowFav ? '♥' : '♡';
    favBtn.classList.toggle('active', nowFav);
  });

  const select = document.getElementById('chapterSelect');
  select.innerHTML = sortedChapters(MANGA, 'asc').map((c) => `
    <option value="${escapeHtml(c.id)}" ${c.id === CHAPTER.id ? 'selected' : ''}>${escapeHtml(c.title)}</option>
  `).join('');
  select.addEventListener('change', () => goToChapter(select.value));

  const { prev, next } = neighbourChapters(MANGA, CHAPTER.id);
  document.getElementById('prevBtn').disabled = !prev;
  document.getElementById('nextBtn').disabled = !next;
  document.getElementById('prevBtn').onclick = () => prev && goToChapter(prev.id);
  document.getElementById('nextBtn').onclick = () => next && goToChapter(next.id);

  document.getElementById('fullscreenBtn').addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => {});
  });

  document.getElementById('thumbToggle').addEventListener('click', () => {
    const drawer = document.getElementById('thumbDrawer');
    drawer.hidden = !drawer.hidden;
  });
  renderThumbDrawer();

  document.getElementById('scrollTopBtn').addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  bindSettingsPanel();
  applyPrefsToDOM();
  renderReader();

  window.addEventListener('keydown', (e) => {
    if (document.getElementById('settingsDrawer').hidden === false && e.key === 'Escape') {
      document.getElementById('settingsDrawer').hidden = true;
      return;
    }
    if (PREFS.mode === 'paged') {
      if (e.key === 'ArrowRight' || e.key === ' ') stepPage(1);
      if (e.key === 'ArrowLeft') stepPage(-1);
    } else {
      if (e.key === 'ArrowRight' && next) goToChapter(next.id);
      if (e.key === 'ArrowLeft' && prev) goToChapter(prev.id);
      if (e.key === ' ') { e.preventDefault(); window.scrollBy({ top: window.innerHeight * 0.85, behavior: 'smooth' }); }
    }
    if (e.key.toLowerCase() === 'f') document.getElementById('fullscreenBtn').click();
  });
}

init();
