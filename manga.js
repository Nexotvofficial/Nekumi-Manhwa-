/* ============================================================
   NEKUMI — ficha de título
   ============================================================ */

let chapterSortDesc = true;
let CURRENT_MANGA = null;

function chapterRowHTML(chap, manga, progress) {
  const isCurrent = progress && progress.chapterId === chap.id;
  const read = isChapterRead(manga.id, chap.id);
  return `
    <a class="chapter-row ${read ? 'is-read' : ''}" href="reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(chap.id)}">
      <span class="chapter-num">${chap.number}</span>
      <div class="chapter-info">
        <h4>${escapeHtml(chap.title)}</h4>
        <p>${chap.pages_count} páginas</p>
      </div>
      ${isCurrent ? '<span class="read-mark">Continuar acá</span>' : read ? '<span class="read-check" title="Ya leído">✓</span>' : ''}
    </a>
  `;
}

function renderChapterList(manga) {
  const progress = getProgress(manga.id);
  const chaps = sortedChapters(manga, chapterSortDesc ? 'desc' : 'asc');
  document.getElementById('chapterList').innerHTML = chaps
    .map((c) => chapterRowHTML(c, manga, progress))
    .join('');
}

function renderDetail(manga) {
  document.title = `${manga.title} — Nekumi`;
  const sClass = statusClass(manga.status);
  const firstChap = sortedChapters(manga, 'asc')[0];
  const progress = getProgress(manga.id);
  const continueChap = progress ? getChapter(manga, progress.chapterId) : null;
  const fav = isFavorite(manga.id);

  document.getElementById('mainContent').innerHTML = `
    <a class="detail-back" href="index.html">← Volver al catálogo</a>
    <div class="detail-head">
      <div class="detail-cover">
        <img src="${escapeHtml(manga.cover)}" alt="Portada de ${escapeHtml(manga.title)}">
      </div>
      <div>
        <div class="detail-title-row">
          <h1 class="detail-title">${escapeHtml(manga.title)}</h1>
          <button class="fav-toggle static" id="detailFav" type="button" title="Favorito">${fav ? '♥' : '♡'}</button>
        </div>
        <div class="detail-meta">
          <span class="status ${sClass}">${escapeHtml(manga.status)}</span>
          <span>${escapeHtml(manga.category)}</span>
          ${manga.rating ? `<span class="rating-inline">★ ${Number(manga.rating).toFixed(1)}</span>` : ''}
          <span>${manga.total_chapters ?? manga.chapters.length} capítulos</span>
        </div>
        <p class="detail-synopsis">${escapeHtml(manga.synopsis)}</p>
        <div class="detail-genres">
          ${(manga.genres || []).map((g) => `<span class="tag">${escapeHtml(g)}</span>`).join('')}
        </div>
        ${continueChap
          ? `<a class="btn" href="reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(continueChap.id)}">Continuar: ${escapeHtml(continueChap.title)}</a>`
          : firstChap
          ? `<a class="btn" href="reader.html?id=${encodeURIComponent(manga.id)}&chap=${encodeURIComponent(firstChap.id)}">Leer desde el capítulo 1</a>`
          : ''
        }
      </div>
    </div>

    <div class="chapter-list-head">
      <h2>Capítulos</h2>
      <button class="sort-toggle" id="sortToggle" type="button">Orden: más nuevo primero</button>
    </div>
    <div id="chapterList"></div>

    <div class="similar-section" id="similarSection" hidden>
      <h2>Títulos similares</h2>
      <div class="grid" id="similarGrid"></div>
    </div>
  `;

  renderChapterList(manga);

  document.getElementById('sortToggle').addEventListener('click', () => {
    chapterSortDesc = !chapterSortDesc;
    document.getElementById('sortToggle').textContent =
      chapterSortDesc ? 'Orden: más nuevo primero' : 'Orden: capítulo 1 primero';
    renderChapterList(manga);
  });

  const favBtn = document.getElementById('detailFav');
  favBtn.classList.toggle('active', fav);
  favBtn.addEventListener('click', () => {
    const nowFav = toggleFavorite(manga.id);
    favBtn.textContent = nowFav ? '♥' : '♡';
    favBtn.classList.toggle('active', nowFav);
  });
}

function renderSimilar(manga, catalog) {
  const genreSet = new Set(manga.genres || []);
  const similar = catalog
    .filter((m) => m.id !== manga.id && (m.genres || []).some((g) => genreSet.has(g)))
    .slice(0, 6);
  const section = document.getElementById('similarSection');
  if (similar.length === 0) { section.hidden = true; return; }
  section.hidden = false;
  document.getElementById('similarGrid').innerHTML = similar.map(cardHTML).join('');
  bindFavButtons(document.getElementById('similarGrid'));
}

async function init() {
  const id = qs('id');
  let catalog;
  try {
    catalog = await fetchCatalog();
  } catch {
    document.getElementById('mainContent').innerHTML = `
      <div class="error-state"><h3>No pudimos cargar el catálogo</h3></div>`;
    return;
  }

  const manga = getMangaById(catalog, id);
  if (!manga) {
    document.getElementById('mainContent').innerHTML = `
      <div class="error-state">
        <h3>No encontramos ese título</h3>
        <p><a class="btn ghost" href="index.html">Volver al catálogo</a></p>
      </div>`;
    return;
  }

  CURRENT_MANGA = manga;
  renderDetail(manga);
  renderSimilar(manga, catalog);

  document.getElementById('menuToggle').addEventListener('click', () => {
    document.querySelector('.nav').classList.toggle('menu-open');
  });
}

init();
