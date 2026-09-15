/* ============================================================
   NEKUMI — utilidades compartidas
   Todo el sitio se alimenta de mangas.json, generado por
   generator.py. No hay contenido hardcodeado.
   ============================================================ */

const CATALOG_URL = 'mangas.json';
const PROGRESS_KEY = 'nekumi_progress_v1';

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

function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}
