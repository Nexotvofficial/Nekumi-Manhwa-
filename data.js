/* ============================================================
   NEKUMI — utilidades compartidas
   Todo el sitio se alimenta de mangas.json, generado por
   generator.py. No hay contenido hardcodeado.
   ============================================================ */

const CATALOG_URL = 'mangas.json';
const PROGRESS_KEY = 'nekumi_progress_v1';
const FAVORITES_KEY = 'nekumi_favorites_v1';
const READER_PREFS_KEY = 'nekumi_reader_prefs_v1';

// Cuántos títulos como mínimo debe tener el catálogo para mostrar
// la sección "Recién actualizado" en el inicio.
const MIN_TITLES_FOR_FRESH_SECTION = 3;

const DEFAULT_READER_PREFS = {
  mode: 'strip',          // 'strip' | 'paged'
  width: 760,             // ancho máx. de la tira / página, en px (ver .strip-pages / .paged-page)
  gap: 0,                 // separación entre páginas (modo tira)
  direction: 'ltr',       // 'ltr' | 'rtl' (modo paginado)
  dim: 0,                 // atenuar pantalla (0-70)
  theme: 'black',         // 'black' | 'charcoal' | 'sepia' | 'white'
  autoScrollSpeed: 40,
  showPageCount: true,
  showExtraPages: false,  // páginas de créditos/publicidad insertadas por el scan
};

function defaultReaderPrefsForDevice() {
  // El ancho ahora es en px y se combina con min(100%, Npx) en el CSS, así que
  // el mismo valor por defecto ya se ve bien tanto en celular como en escritorio.
  return { ...DEFAULT_READER_PREFS };
}

// Cada "page" del capítulo puede ser un string (url) o, si el generador detectó
// que es una página de créditos/publicidad del scan, un objeto {url, extra:true}.
function pageUrl(page) {
  return typeof page === 'string' ? page : page.url;
}

function pageIsExtra(page) {
  return typeof page === 'string' ? false : Boolean(page.extra);
}

async function fetchCatalog() {
  const res = await fetch(CATALOG_URL, { cache: 'no-store' });
  if (!res.ok) throw new Error('No se pudo cargar el catálogo');
  return res.json();
}

function getMangaById(list, id) {
  return list.find((m) => m.id === id) || null;
}

function getChapter(manga, chapterId) {
  return manga.chapters.find((c) => c.id === chapterId) || null;
}

function sortedChapters(manga, dir = 'desc') {
  const arr = [...manga.chapters].sort((a, b) => a.number - b.number);
  return dir === 'desc' ? arr.reverse() : arr;
}

function statusClass(status) {
  const s = (status || '').toLowerCase();
  if (s.includes('emisi') || s.includes('curso') || s.includes('ongoing')) return 'ongoing';
  if (s.includes('final') || s.includes('complet')) return 'finished';
  return '';
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/* ---------- favoritos (localStorage) ---------- */

function readFavorites() {
  try {
    const raw = JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]');
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function writeFavorites(list) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(list));
  } catch {
    /* almacenamiento no disponible: se ignora silenciosamente */
  }
  // avisa a otras partes de la página (p. ej. auth.js) que los favoritos cambiaron
  document.dispatchEvent(new CustomEvent('nekumi:favorites-changed', { detail: { list } }));
}

function isFavorite(id) {
  return readFavorites().includes(id);
}

function toggleFavorite(id) {
  const list = readFavorites();
  const idx = list.indexOf(id);
  if (idx === -1) {
    list.push(id);
    writeFavorites(list);
    return true;
  }
  list.splice(idx, 1);
  writeFavorites(list);
  return false;
}

/* ---------- progreso de lectura (localStorage) ---------- */

function readProgressStore() {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveProgress(mangaId, chapterId, scrollFraction) {
  try {
    const store = readProgressStore();
    store[mangaId] = {
      chapterId,
      scrollFraction,
      updatedAt: Date.now(),
    };
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(store));
    document.dispatchEvent(new CustomEvent('nekumi:progress-changed', { detail: { mangaId, chapterId, scrollFraction } }));
  } catch {
    /* almacenamiento no disponible: se ignora silenciosamente */
  }
}

function getProgress(mangaId) {
  const store = readProgressStore();
  return store[mangaId] || null;
}

function getAllProgress() {
  const store = readProgressStore();
  return Object.entries(store)
    .sort((a, b) => b[1].updatedAt - a[1].updatedAt)
    .map(([mangaId, data]) => ({ mangaId, ...data }));
}

/* ---------- preferencias del lector (localStorage) ---------- */

function readReaderPrefs() {
  try {
    const stored = localStorage.getItem(READER_PREFS_KEY);
    if (!stored) return defaultReaderPrefsForDevice();
    return { ...DEFAULT_READER_PREFS, ...JSON.parse(stored) };
  } catch {
    return defaultReaderPrefsForDevice();
  }
}

function saveReaderPrefs(prefs) {
  try {
    localStorage.setItem(READER_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* almacenamiento no disponible: se ignora silenciosamente */
  }
}

/* ---------- capítulos leídos (localStorage) ---------- */

const READ_CHAPTERS_KEY = 'nekumi_read_v1';

function readReadStore() {
  try {
    return JSON.parse(localStorage.getItem(READ_CHAPTERS_KEY) || '{}');
  } catch {
    return {};
  }
}

function isChapterRead(mangaId, chapterId) {
  const store = readReadStore();
  return Boolean(store[mangaId] && store[mangaId].includes(chapterId));
}

function markChapterRead(mangaId, chapterId) {
  try {
    const store = readReadStore();
    const list = store[mangaId] || [];
    if (!list.includes(chapterId)) {
      list.push(chapterId);
      store[mangaId] = list;
      localStorage.setItem(READ_CHAPTERS_KEY, JSON.stringify(store));
      document.dispatchEvent(new CustomEvent('nekumi:read-changed', { detail: { mangaId, chapterId } }));
    }
  } catch {
    /* almacenamiento no disponible: se ignora silenciosamente */
  }
}

function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}
