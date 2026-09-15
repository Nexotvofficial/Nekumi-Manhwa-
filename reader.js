/* ============================================================
   NEKUMI — lector
   La tira vertical es el contenido; el resto es solo chrome
   flotante que se aparta cuando no se necesita.
   ============================================================ */

let lastScrollY = 0;
let topbarHidden = false;

function toggleChromeOnScroll() {
  const y = window.scrollY;
  const goingDown = y > lastScrollY && y > 80;
  const topbar = document.getElementById('topbar');

  if (goingDown && !topbarHidden) {
    topbar.classList.add('hidden');
    topbarHidden = true;
  } else if (!goingDown && topbarHidden) {
    topbar.classList.remove('hidden');
    topbarHidden = false;
  }
  lastScrollY = y;

  const doc = document.documentElement;
  const scrollable = doc.scrollHeight - doc.clientHeight;
  const fraction = scrollable > 0 ? Math.min(1, y / scrollable) : 0;
  document.getElementById('progressFill').style.width = `${fraction * 100}%`;

  if (window.__mangaId && window.__chapterId) {
    saveProgress(window.__mangaId, window.__chapterId, fraction);
  }
}

function buildChapterSelect(manga, currentChapterId) {
  const select = document.getElementById('chapterSelect');
  const chaps = sortedChapters(manga, 'asc');
  select.innerHTML = chaps.map((c) => `
    <option value="${escapeHtml(c.id)}" ${c.id === currentChapterId ? 'selected' : ''}>${escapeHtml(c.title)}</option>
  `).join('');
  select.addEventListener('change', () => {
    window.location.href = `reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(select.value)}`;
  });
}

function neighbourChapters(manga, chapterId) {
  const chaps = sortedChapters(manga, 'asc');
  const idx = chaps.findIndex((c) => c.id === chapterId);
  return {
    prev: idx > 0 ? chaps[idx - 1] : null,
    next: idx >= 0 && idx < chaps.length - 1 ? chaps[idx + 1] : null,
  };
}

function renderPages(manga, chapter) {
  const el = document.getElementById('readerMain');
  const { prev, next } = neighbourChapters(manga, chapter.id);

  const pagesHTML = chapter.pages
    .map((url, i) => `<img src="${escapeHtml(url)}" alt="Página ${i + 1}" loading="${i < 2 ? 'eager' : 'lazy'}">`)
    .join('');

  el.innerHTML = `
    <div class="strip-pages">${pagesHTML}</div>
    <div class="reader-endcard">
      <h3>Fin de ${escapeHtml(chapter.title)}</h3>
      ${next
        ? `<a class="btn" href="reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(next.id)}">Siguiente capítulo →</a>`
        : `<p>Todavía no hay más capítulos publicados.</p>`
      }
      <br>
      <a class="btn ghost" href="manga.html?id=${encodeURIComponent(manga.id)}">Volver a la ficha</a>
    </div>
  `;

  document.getElementById('prevBtn').disabled = !prev;
  document.getElementById('nextBtn').disabled = !next;
  document.getElementById('prevBtn').onclick = () => {
    if (prev) window.location.href = `reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(prev.id)}`;
  };
  document.getElementById('nextBtn').onclick = () => {
    if (next) window.location.href = `reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(next.id)}`;
  };
}

async function init() {
  const mangaId = qs('id');
  const chapterId = qs('chap');
  let catalog;
  try {
    catalog = await fetchCatalog();
  } catch {
    document.getElementById('readerMain').innerHTML = `
      <div class="error-state"><h3>No pudimos cargar el catálogo</h3></div>`;
    return;
  }

  const manga = getMangaById(catalog, mangaId);
  const chapter = manga ? getChapter(manga, chapterId) : null;

  if (!manga || !chapter) {
    document.getElementById('readerMain').innerHTML = `
      <div class="error-state">
        <h3>No encontramos ese capítulo</h3>
        <p><a class="btn ghost" href="index.html">Volver al catálogo</a></p>
      </div>`;
    return;
  }

  window.__mangaId = manga.id;
  window.__chapterId = chapter.id;

  document.title = `${chapter.title} · ${manga.title} — Nekumi`;
  document.getElementById('readerTitle').textContent = `${manga.title} · ${chapter.title}`;
  document.getElementById('backLink').href = `manga.html?id=${encodeURIComponent(manga.id)}`;

  buildChapterSelect(manga, chapter.id);
  renderPages(manga, chapter);

  window.addEventListener('scroll', toggleChromeOnScroll, { passive: true });

  window.addEventListener('keydown', (e) => {
    const { prev, next } = neighbourChapters(manga, chapter.id);
    if (e.key === 'ArrowRight' && next) window.location.href = `reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(next.id)}`;
    if (e.key === 'ArrowLeft' && prev) window.location.href = `reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(prev.id)}`;
  });
}

init();
