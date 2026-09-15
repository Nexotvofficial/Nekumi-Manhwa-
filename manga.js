/* ============================================================
   NEKUMI — ficha de título (manga.html)
   ============================================================ */

let chapterSortDesc = true;
let chapterFilter = '';
let CURRENT_MANGA = null;

/* ---------- helpers ---------- */

function mHref(id) {
  return `manga.html?id=${encodeURIComponent(id)}`;
}

function rHref(mangaId, chapterId) {
  return `reader.html?id=${encodeURIComponent(mangaId)}&chap=${encodeURIComponent(chapterId)}`;
}

function relDate(value) {
  const t = new Date(value).getTime();
  if (!Number.isFinite(t)) return '';
  const days = Math.round((Date.now() - t) / 86400000);
  if (days <= 0) return 'hoy';
  if (days === 1) return 'ayer';
  if (days < 30) return `hace ${days} días`;
  const months = Math.round(days / 30);
  if (months < 12) return `hace ${months} ${months === 1 ? 'mes' : 'meses'}`;
  const years = Math.round(months / 12);
  return `hace ${years} ${years === 1 ? 'año' : 'años'}`;
}

function countRead(manga) {
  return (manga.chapters || []).filter((c) => isChapterRead(manga.id, c.id)).length;
}

/* ---------- lista de capítulos ---------- */

function chapterRowHTML(chap, manga, progress) {
  const isCurrent = progress && progress.chapterId === chap.id;
  const read = isChapterRead(manga.id, chap.id);
  return `
    <a class="chapter-row ${read ? 'is-read' : ''} ${isCurrent ? 'is-current' : ''}" href="${rHref(manga.id, chap.id)}">
      <span class="chapter-num">${escapeHtml(chap.number)}</span>
      <div class="chapter-info">
        <h4>${escapeHtml(chap.title)}</h4>
        <p>${escapeHtml(chap.pages_count ?? '?')} páginas</p>
      </div>
      ${isCurrent
        ? '<span class="read-mark">Continuar acá</span>'
        : read ? '<span class="read-check" title="Ya leído">✓</span>' : ''}
    </a>
  `;
}

function renderChapterList(manga) {
  const progress = getProgress(manga.id);
  let chaps = sortedChapters(manga, chapterSortDesc ? 'desc' : 'asc');

  if (chapterFilter) {
    chaps = chaps.filter((c) =>
      String(c.number).includes(chapterFilter) ||
      String(c.title || '').toLowerCase().includes(chapterFilter));
  }

  const list = document.getElementById('chapterList');
  list.innerHTML = chaps.length
    ? chaps.map((c) => chapterRowHTML(c, manga, progress)).join('')
    : '<p class="chapter-empty">Ningún capítulo coincide con esa búsqueda.</p>';

  const total = (manga.chapters || []).length;
  const read = countRead(manga);
  const bar = document.getElementById('readProgress');
  if (bar && total) {
    bar.innerHTML = `
      <div class="read-bar"><span style="width:${Math.round((read / total) * 100)}%"></span></div>
      <span class="read-count">${read} de ${total} capítulos leídos</span>
    `;
  }
}

/* ---------- ficha ---------- */

function renderDetail(manga, catalog) {
  document.title = `${manga.title} — Nekumi`;
  const chapters = manga.chapters || [];
  const sClass = statusClass(manga.status);
  const statusLabel = sClass === 'ongoing' ? 'En emisión' : sClass === 'finished' ? 'Finalizado' : (manga.status || '');
  const firstChap = sortedChapters(manga, 'asc')[0];
  const lastChap = sortedChapters(manga, 'desc')[0];
  const progress = getProgress(manga.id);
  const continueChap = progress ? getChapter(manga, progress.chapterId) : null;
  const fav = isFavorite(manga.id);
  const cover = manga.cover || manga.cover_thumb || '';
  const synopsis = String(manga.synopsis || '');
  const longSynopsis = synopsis.length > 320;

  const cta = continueChap
    ? { href: rHref(manga.id, continueChap.id), label: `Continuar · ${continueChap.title}` }
    : firstChap
      ? { href: rHref(manga.id, firstChap.id), label: 'Empezar a leer' }
      : null;

  const infoRows = [
    ['Estado', statusLabel],
    ['Categoría', manga.category || ''],
    ['Capítulos', String(manga.total_chapters ?? chapters.length)],
    ['Puntuación', manga.rating ? `★ ${Number(manga.rating).toFixed(1)}` : ''],
    ['Actualizado', relDate(manga.last_updated)],
  ].filter(([, v]) => v);

  document.getElementById('mainContent').innerHTML = `
    <section class="detail-hero">
      <div class="detail-hero-backdrop" ${cover ? `style="background-image:url('${escapeHtml(cover)}')"` : ''} aria-hidden="true"></div>
      <div class="wrap detail-hero-inner">
        <a class="detail-back" href="/">← Volver al catálogo</a>
        <div class="detail-head">
          <div class="detail-cover">
            ${cover ? `<img src="${escapeHtml(cover)}" alt="Portada de ${escapeHtml(manga.title)}">` : ''}
          </div>
          <div class="detail-body">
            <h1 class="detail-title">${escapeHtml(manga.title || 'Sin título')}</h1>
            <div class="detail-meta">
              ${statusLabel ? `<span class="status ${sClass}">${escapeHtml(statusLabel)}</span>` : ''}
              ${manga.rating ? `<span class="rating-inline">★ ${Number(manga.rating).toFixed(1)}</span>` : ''}
              <span>${escapeHtml(String(manga.total_chapters ?? chapters.length))} capítulos</span>
              ${manga.last_updated ? `<span>actualizado ${escapeHtml(relDate(manga.last_updated))}</span>` : ''}
            </div>
            ${synopsis ? `
              <p class="detail-synopsis ${longSynopsis ? 'clamped' : ''}" id="synopsis">${escapeHtml(synopsis)}</p>
              ${longSynopsis ? '<button class="synopsis-toggle" id="synopsisToggle" type="button">Leer más</button>' : ''}
            ` : ''}
            ${(manga.genres || []).length ? `
              <div class="detail-genres">
                ${(manga.genres || []).map((g) => `<a class="tag" href="/#catalogo">${escapeHtml(g)}</a>`).join('')}
              </div>` : ''}
            <div class="detail-ctas">
              ${chapters.length === 0
                ? '<p class="detail-note">Todavía no hay capítulos publicados para este título.</p>'
                : `
                  <a class="btn" href="${cta.href}">${escapeHtml(cta.label)}</a>
                  ${continueChap && lastChap && lastChap.id !== continueChap.id
                    ? `<a class="btn ghost" href="${rHref(manga.id, lastChap.id)}">Último capítulo</a>`
                    : firstChap && continueChap ? '' : ''}
                  <button class="btn ghost fav-btn ${fav ? 'active' : ''}" id="detailFav" type="button">${fav ? '♥ En favoritos' : '♡ Guardar'}</button>
                `}
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="wrap detail-cols">
      <section class="panel chapter-panel">
        <div class="panel-head">
          <h2>Capítulos</h2>
          <button class="sort-toggle" id="sortToggle" type="button">Más nuevo primero</button>
        </div>
        <div class="chapter-tools">
          <input type="search" id="chapterSearch" placeholder="Ir a un capítulo…" aria-label="Buscar capítulo" autocomplete="off">
        </div>
        <div class="read-progress" id="readProgress"></div>
        <div id="chapterList"></div>
      </section>

      <aside class="detail-side">
        <section class="panel side-panel">
          <div class="panel-head"><h2>Ficha</h2></div>
          <div class="info-rows">
            ${infoRows.map(([k, v]) => `<div class="info-row"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('')}
          </div>
        </section>
        <section class="panel side-panel" id="similarSection" hidden>
          <div class="panel-head"><h2>Parecidos</h2></div>
          <ul class="similar-list" id="similarList"></ul>
        </section>
      </aside>
    </div>

    ${cta ? `
      <div class="mobile-read-bar">
        <a class="btn" href="${cta.href}">${escapeHtml(cta.label)}</a>
        <button class="icon-btn fav-mobile ${fav ? 'active' : ''}" id="detailFavMobile" type="button" aria-label="Guardar en favoritos">${fav ? '♥' : '♡'}</button>
      </div>` : ''}
  `;

  renderChapterList(manga);

  const sortBtn = document.getElementById('sortToggle');
  sortBtn.addEventListener('click', () => {
    chapterSortDesc = !chapterSortDesc;
    sortBtn.textContent = chapterSortDesc ? 'Más nuevo primero' : 'Capítulo 1 primero';
    renderChapterList(manga);
  });

  document.getElementById('chapterSearch').addEventListener('input', (e) => {
    chapterFilter = e.target.value.trim().toLowerCase();
    renderChapterList(manga);
  });

  const synToggle = document.getElementById('synopsisToggle');
  if (synToggle) {
    synToggle.addEventListener('click', () => {
      const p = document.getElementById('synopsis');
      const clamped = p.classList.toggle('clamped');
      synToggle.textContent = clamped ? 'Leer más' : 'Leer menos';
    });
  }

  const favButtons = [document.getElementById('detailFav'), document.getElementById('detailFavMobile')].filter(Boolean);
  favButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const nowFav = toggleFavorite(manga.id);
      favButtons.forEach((b) => {
        b.classList.toggle('active', nowFav);
        b.textContent = b.id === 'detailFavMobile'
          ? (nowFav ? '♥' : '♡')
          : (nowFav ? '♥ En favoritos' : '♡ Guardar');
      });
      showToast(nowFav ? 'Guardado en favoritos' : 'Quitado de favoritos', { icon: nowFav ? '♥' : '♡', duration: 1600 });
    });
  });

  renderSimilar(manga, catalog);
}

/* ---------- parecidos ---------- */

function renderSimilar(manga, catalog) {
  const genreSet = new Set(manga.genres || []);
  const similar = catalog
    .filter((m) => m.id !== manga.id && (m.genres || []).some((g) => genreSet.has(g)))
    .sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0))
    .slice(0, 6);

  const section = document.getElementById('similarSection');
  if (similar.length === 0) { section.hidden = true; return; }
  section.hidden = false;

  document.getElementById('similarList').innerHTML = similar.map((m) => `
    <li class="similar-row">
      <a class="similar-cover" href="${mHref(m.id)}" tabindex="-1" aria-hidden="true">
        <img src="${escapeHtml(m.cover_thumb || m.cover || '')}" alt="" loading="lazy">
      </a>
      <div class="similar-body">
        <a class="similar-title" href="${mHref(m.id)}">${escapeHtml(m.title || '')}</a>
        <span class="similar-sub">${escapeHtml((m.genres || []).slice(0, 2).join(' · '))}</span>
      </div>
      ${m.rating ? `<span class="similar-rating">★ ${Number(m.rating).toFixed(1)}</span>` : ''}
    </li>
  `).join('');
}

/* ---------- arranque ---------- */

async function init() {
  if (!document.getElementById('mainContent')) return;

  const id = qs('id');
  let catalog;
  try {
    catalog = await fetchCatalog();
  } catch {
    document.getElementById('mainContent').innerHTML = `
      <div class="error-state">
        <h3>El catálogo no cargó</h3>
        <p>Puede estar actualizándose. Probá de nuevo en unos segundos.</p>
        <button class="btn" id="retryLoadBtn" type="button">Reintentar</button>
      </div>`;
    document.getElementById('retryLoadBtn').addEventListener('click', () => window.location.reload());
    return;
  }

  const manga = getMangaById(catalog, id);
  if (!manga) {
    document.getElementById('mainContent').innerHTML = `
      <div class="error-state">
        <h3>Ese título no está en el catálogo</h3>
        <p>Puede haber cambiado de dirección o haberse retirado.</p>
        <p><a class="btn ghost" href="/">Volver al catálogo</a></p>
      </div>`;
    return;
  }

  CURRENT_MANGA = manga;
  renderDetail(manga, catalog);

  document.getElementById('menuToggle').addEventListener('click', () => {
    document.querySelector('.nav').classList.toggle('menu-open');
  });

  // si el lector marcó capítulos en otra pestaña, refrescamos la lista
  document.addEventListener('nekumi:read-changed', () => renderChapterList(manga));
}

init();
