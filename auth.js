/* ============================================================
   NEKUMI — auth.js
   Login con Firebase (correo/contraseña y Google) + sincronización
   en segundo plano de favoritos, progreso de lectura y capítulos
   leídos hacia Firestore.

   Importante: el sitio sigue funcionando 100% sin iniciar sesión,
   usando localStorage como hasta ahora (ver data.js). Este archivo
   sólo AÑADE la sincronización cuando hay una cuenta conectada;
   si Firebase no carga por cualquier motivo, el resto del sitio
   sigue funcionando normal.
   ============================================================ */

const firebaseConfig = {
  apiKey: "AIzaSyA_8r6TZv6eveWs1LN4bGx7INCKAUfLoY0",
  authDomain: "nekutoon-a7417.firebaseapp.com",
  projectId: "nekutoon-a7417",
  storageBucket: "nekutoon-a7417.firebasestorage.app",
  messagingSenderId: "220922201940",
  appId: "1:220922201940:web:67be5909a2e5134191aac1",
  measurementId: "G-RH4FVFBW3J",
};

let fbApp = null;
let fbAuth = null;
let fbDb = null;
let currentUser = null;
let syncTimer = null;

function fbReady() {
  return typeof firebase !== 'undefined' && fbAuth && fbDb;
}

/* ---------- inicialización ---------- */

function initFirebase() {
  if (typeof firebase === 'undefined') {
    console.warn('[Nekumi] Firebase SDK no está cargado; el login no estará disponible, pero el sitio funciona normal.');
    return;
  }
  try {
    fbApp = firebase.initializeApp(firebaseConfig);
    fbAuth = firebase.auth();
    fbDb = firebase.firestore();
    if (firebase.analytics) { try { firebase.analytics(); } catch (e) { /* opcional */ } }
    fbAuth.onAuthStateChanged(onAuthChanged);
  } catch (e) {
    console.warn('[Nekumi] No se pudo inicializar Firebase:', e);
  }
}

/* ---------- sincronización local <-> nube ---------- */

function localSnapshot() {
  return {
    favorites: readFavorites(),
    progress: readProgressStore(),
    read: readReadStore(),
    updatedAt: Date.now(),
  };
}

function mergeMaps(localMap, cloudMap) {
  // se queda con la entrada más reciente por clave (mangaId)
  const merged = { ...localMap };
  Object.keys(cloudMap || {}).forEach((key) => {
    const cloudEntry = cloudMap[key];
    const localEntry = merged[key];
    if (!localEntry || (cloudEntry.updatedAt || 0) > (localEntry.updatedAt || 0)) {
      merged[key] = cloudEntry;
    }
  });
  return merged;
}

function mergeReadMaps(localMap, cloudMap) {
  const merged = { ...localMap };
  Object.keys(cloudMap || {}).forEach((key) => {
    const set = new Set([...(merged[key] || []), ...(cloudMap[key] || [])]);
    merged[key] = Array.from(set);
  });
  return merged;
}

async function pullAndMerge(uid) {
  const docRef = fbDb.collection('users').doc(uid);
  const snap = await docRef.get();
  const cloud = snap.exists ? snap.data() : null;
  const local = localSnapshot();

  const mergedFavorites = cloud ? Array.from(new Set([...local.favorites, ...(cloud.favorites || [])])) : local.favorites;
  const mergedProgress = cloud ? mergeMaps(local.progress, cloud.progress) : local.progress;
  const mergedRead = cloud ? mergeReadMaps(local.read, cloud.read) : local.read;

  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(mergedFavorites));
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(mergedProgress));
    localStorage.setItem(READ_CHAPTERS_KEY, JSON.stringify(mergedRead));
  } catch (e) { /* almacenamiento no disponible */ }

  await docRef.set({
    favorites: mergedFavorites,
    progress: mergedProgress,
    read: mergedRead,
    email: currentUser ? currentUser.email : null,
    updatedAt: Date.now(),
  }, { merge: true });

  document.dispatchEvent(new CustomEvent('nekumi:synced'));
}

function pushToCloud() {
  if (!fbReady() || !currentUser) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    const snap = localSnapshot();
    fbDb.collection('users').doc(currentUser.uid).set(snap, { merge: true }).catch((e) => {
      console.warn('[Nekumi] No se pudo sincronizar con la nube:', e);
    });
  }, 800);
}

function onAuthChanged(user) {
  currentUser = user;
  renderAuthUI();
  if (user) {
    pullAndMerge(user.uid).catch((e) => console.warn('[Nekumi] Error al sincronizar:', e));
  }
}

['nekumi:favorites-changed', 'nekumi:progress-changed', 'nekumi:read-changed'].forEach((evt) => {
  document.addEventListener(evt, pushToCloud);
});

/* ---------- acciones de cuenta ---------- */

async function nekumiSignUp(email, password) {
  return fbAuth.createUserWithEmailAndPassword(email, password);
}
async function nekumiSignIn(email, password) {
  return fbAuth.signInWithEmailAndPassword(email, password);
}
async function nekumiSignInGoogle() {
  const provider = new firebase.auth.GoogleAuthProvider();
  return fbAuth.signInWithPopup(provider);
}
async function nekumiSignOut() {
  return fbAuth.signOut();
}

// Conseguí tu propia site key gratis en https://www.google.com/recaptcha/admin
// (elegí reCAPTCHA v2 "Casilla no soy un robot") y reemplazá esto. Sin una key
// válida el widget no va a aparecer y el modal avisa en consola.
const RECAPTCHA_SITE_KEY = 'TU_SITE_KEY_DE_RECAPTCHA_AQUI';
let recaptchaWidgetId = null;

function loadRecaptchaScript() {
  return new Promise((resolve) => {
    if (window.grecaptcha) { resolve(); return; }
    if (document.getElementById('recaptchaScript')) {
      const check = setInterval(() => {
        if (window.grecaptcha) { clearInterval(check); resolve(); }
      }, 150);
      return;
    }
    const script = document.createElement('script');
    script.id = 'recaptchaScript';
    script.src = 'https://www.google.com/recaptcha/api.js';
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    document.head.appendChild(script);
  });
}

async function renderRecaptcha() {
  if (RECAPTCHA_SITE_KEY.startsWith('TU_SITE_KEY')) {
    console.warn('[Nekumi] Falta configurar RECAPTCHA_SITE_KEY en auth.js — el login funciona sin captcha por ahora.');
    document.getElementById('authRecaptchaBox').innerHTML = '<p class="setting-hint">⚠ Falta configurar la site key de reCAPTCHA.</p>';
    return;
  }
  await loadRecaptchaScript();
  if (recaptchaWidgetId === null && window.grecaptcha) {
    recaptchaWidgetId = window.grecaptcha.render('authRecaptchaBox', { sitekey: RECAPTCHA_SITE_KEY, theme: 'dark' });
  }
}

function recaptchaSolved() {
  if (RECAPTCHA_SITE_KEY.startsWith('TU_SITE_KEY')) return true; // sin key configurada, no bloqueamos el login
  return Boolean(window.grecaptcha && recaptchaWidgetId !== null && window.grecaptcha.getResponse(recaptchaWidgetId));
}

function resetRecaptcha() {
  if (window.grecaptcha && recaptchaWidgetId !== null) window.grecaptcha.reset(recaptchaWidgetId);
}

/* ---------- interfaz de cuenta (inyectada en todas las páginas) ---------- */

function buildAuthModal() {
  if (document.getElementById('authModal')) return;
  const modal = document.createElement('div');
  modal.id = 'authModal';
  modal.className = 'auth-modal';
  modal.hidden = true;
  modal.innerHTML = `
    <div class="auth-modal-backdrop" id="authModalBackdrop"></div>
    <div class="auth-modal-box">
      <button class="icon-btn auth-modal-close" id="authModalClose" type="button" aria-label="Cerrar">✕</button>
      <h3>Tu cuenta</h3>
      <p class="auth-modal-sub">Iniciá sesión para guardar tus favoritos y tu progreso en la nube.</p>
      <form id="authForm">
        <input type="email" id="authEmail" placeholder="Correo electrónico" autocomplete="email" required>
        <input type="password" id="authPassword" placeholder="Contraseña" autocomplete="current-password" required>
        <div class="auth-modal-actions">
          <button type="submit" class="btn" id="authSignInBtn">Iniciar sesión</button>
          <button type="button" class="btn ghost" id="authSignUpBtn">Crear cuenta</button>
        </div>
      </form>
      <div class="auth-modal-divider"><span>o</span></div>
      <button type="button" class="btn ghost auth-google-btn" id="authGoogleBtn">Continuar con Google</button>
      <div id="authRecaptchaBox" class="auth-recaptcha"></div>
      <p class="auth-modal-error" id="authModalError" hidden></p>
    </div>
  `;
  document.body.appendChild(modal);
  renderRecaptcha();

  const close = () => { modal.hidden = true; };
  document.getElementById('authModalBackdrop').addEventListener('click', close);
  document.getElementById('authModalClose').addEventListener('click', close);

  const showError = (msg) => {
    const el = document.getElementById('authModalError');
    el.textContent = msg;
    el.hidden = false;
  };

  document.getElementById('authForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!recaptchaSolved()) { showError('Confirmá el captcha antes de continuar.'); return; }
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    try {
      await nekumiSignIn(email, password);
      close();
    } catch (err) {
      showError(traduceErrorFirebase(err));
      resetRecaptcha();
    }
  });

  document.getElementById('authSignUpBtn').addEventListener('click', async () => {
    if (!recaptchaSolved()) { showError('Confirmá el captcha antes de continuar.'); return; }
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    try {
      await nekumiSignUp(email, password);
      close();
    } catch (err) {
      showError(traduceErrorFirebase(err));
      resetRecaptcha();
    }
  });

  document.getElementById('authGoogleBtn').addEventListener('click', async () => {
    try {
      await nekumiSignInGoogle();
      close();
    } catch (err) {
      showError(traduceErrorFirebase(err));
    }
  });
}

function traduceErrorFirebase(err) {
  const code = err && err.code;
  const map = {
    'auth/invalid-email': 'Ese correo no es válido.',
    'auth/user-not-found': 'No existe una cuenta con ese correo.',
    'auth/wrong-password': 'Contraseña incorrecta.',
    'auth/email-already-in-use': 'Ya existe una cuenta con ese correo.',
    'auth/weak-password': 'La contraseña debe tener al menos 6 caracteres.',
    'auth/popup-closed-by-user': 'Se cerró la ventana antes de terminar.',
  };
  return map[code] || 'Ocurrió un error. Probá de nuevo.';
}

function renderAuthUI() {
  const btn = document.getElementById('authNavBtn');
  if (!btn) return;
  if (currentUser) {
    btn.textContent = currentUser.email ? currentUser.email.split('@')[0] : 'Mi cuenta';
    btn.dataset.state = 'in';
  } else {
    btn.textContent = 'Iniciar sesión';
    btn.dataset.state = 'out';
  }
}

function injectAuthNavButton() {
  const navLinks = document.querySelector('.nav-links');
  const navMobile = document.querySelector('.nav-mobile');
  if (!navLinks || document.getElementById('authNavBtn')) return;

  const btn = document.createElement('button');
  btn.id = 'authNavBtn';
  btn.type = 'button';
  btn.className = 'auth-nav-btn';
  btn.textContent = 'Iniciar sesión';
  btn.addEventListener('click', () => {
    if (currentUser) {
      if (confirm('¿Cerrar sesión?')) nekumiSignOut();
    } else {
      buildAuthModal();
      document.getElementById('authModal').hidden = false;
    }
  });
  navLinks.appendChild(btn);

  if (navMobile) {
    const mobileBtn = btn.cloneNode(true);
    mobileBtn.id = 'authNavBtnMobile';
    mobileBtn.addEventListener('click', () => btn.click());
    navMobile.appendChild(mobileBtn);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  injectAuthNavButton();
  initFirebase();
});
