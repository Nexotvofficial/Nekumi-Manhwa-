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

// Guarda la última copia del catálogo que cargó bien. Si el repo se está
// regenerando justo cuando alguien visita el sitio (deploy en curso, JSON
// a mitad de escribirse, CDN todavía sin propagar, etc.), preferimos mostrar
// esta copia "un poco vieja" antes que romper la página con un error.
const CATALOG_CACHE_KEY = 'nekumi_catalog_cache_v1';

function readCatalogCache() {
  try {
    const raw = JSON.parse(localStorage.getItem(CATALOG_CACHE_KEY) || 'null');
    return Array.isArray(raw) ? raw : null;
  } catch {
    return null;
  }
}

function writeCatalogCache(list) {
  try {
    localStorage.setItem(CATALOG_CACHE_KEY, JSON.stringify(list));
  } catch {
    /* almacenamiento no disponible: no pasa nada, simplemente no habrá respaldo */
  }
}

async function fetchOnce() {
  const res = await fetch(CATALOG_URL, { cache: 'no-store' });
  if (!res.ok) throw new Error(`No se pudo cargar el catálogo (HTTP ${res.status})`);
  const data = await res.json();
  if (!Array.isArray(data)) throw new Error('mangas.json no tiene el formato esperado');
  return data;
}

// Reintenta un par de veces antes de rendirse: cubre el caso típico de que
// justo se esté re-generando mangas.json (Actions + jsDelivr/CDN con lag).
// Si todos los intentos fallan, usa la última copia buena guardada en este
// navegador en vez de dejar al usuario con la pantalla rota.
async function fetchCatalog({ retries = 2, retryDelayMs = 700 } = {}) {
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const data = await fetchOnce();
      writeCatalogCache(data);
      return data;
    } catch (e) {
      lastError = e;
      if (attempt < retries) await new Promise((r) => setTimeout(r, retryDelayMs * (attempt + 1)));
    }
  }
  const cached = readCatalogCache();
  if (cached) {
    console.warn('[Nekumi] No se pudo actualizar el catálogo, mostrando la última copia guardada:', lastError);
    return cached;
  }
  throw lastError || new Error('No se pudo cargar el catálogo');
}

function getMangaById(list, id) {
  return (list || []).find((m) => m.id === id) || null;
}

function getChapter(manga, chapterId) {
  if (!manga || !Array.isArray(manga.chapters)) return null;
  return manga.chapters.find((c) => c.id === chapterId) || null;
}

function sortedChapters(manga, dir = 'desc') {
  const arr = [...(manga && manga.chapters ? manga.chapters : [])].sort((a, b) => a.number - b.number);
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

/* ---------- toasts (notificaciones flotantes) ---------- */

function toastContainer() {
  let el = document.getElementById('toastStack');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toastStack';
    el.className = 'toast-stack';
    document.body.appendChild(el);
  }
  return el;
}

function showToast(message, { icon = '', duration = 2600 } = {}) {
  const stack = toastContainer();
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `${icon ? `<span class="toast-icon">${icon}</span>` : ''}<span>${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  requestAnimationFrame(() => el.classList.add('in'));
  setTimeout(() => {
    el.classList.remove('in');
    el.addEventListener('transitionend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 500);
  }, duration);
}

/* ---------- aviso de cookies ----------
   Nota honesta: esto es un aviso informativo, no un CMP completo. No bloquea
   la carga de Firebase/anuncios antes de que el usuario elija (eso requiere
   Google Consent Mode o un CMP como Funding Choices/CookieYes). Si vas a
   servir anuncios a usuarios de la UE/UK, conviene sumar uno de esos. */
const COOKIE_CONSENT_KEY = 'nekumi_cookie_consent_v1';

function initCookieConsent() {
  try {
    if (localStorage.getItem(COOKIE_CONSENT_KEY)) return;
  } catch {
    return;
  }
  if (document.getElementById('cookieBanner')) return;

  const el = document.createElement('div');
  el.id = 'cookieBanner';
  el.className = 'cookie-banner';
  el.innerHTML = `
    <p>Usamos almacenamiento local y, si iniciás sesión, servicios de Google (Firebase) para guardar tus favoritos y tu progreso. El sitio puede mostrar anuncios de terceros. Más info en <a href="privacy.html">Privacidad</a>.</p>
    <div class="cookie-banner-actions">
      <button class="btn ghost" id="cookieDecline" type="button">Solo lo esencial</button>
      <button class="btn" id="cookieAccept" type="button">Aceptar</button>
    </div>
  `;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('in'));

  const close = (value) => {
    try { localStorage.setItem(COOKIE_CONSENT_KEY, value); } catch { /* no pasa nada */ }
    el.classList.remove('in');
    setTimeout(() => el.remove(), 300);
  };
  document.getElementById('cookieAccept').addEventListener('click', () => close('accepted'));
  document.getElementById('cookieDecline').addEventListener('click', () => close('declined'));
}

document.addEventListener('DOMContentLoaded', initCookieConsent);
