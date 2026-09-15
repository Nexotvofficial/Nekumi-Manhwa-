/* ============================================================
   NEKUMI — candado de dominio
   Este archivo debe ser el PRIMER <script> del <head> en cada
   página. Si el sitio se está sirviendo desde un dominio que no
   sea el oficial (alguien clonó el repo o hace un mirror/iframe),
   redirige automáticamente a nekutoon.com conservando la ruta.
   En localhost / 127.0.0.1 / archivos locales no hace nada, para
   que puedas seguir probando el sitio en tu máquina.
   ============================================================ */
(function () {
  var OFFICIAL_HOSTS = ['nekutoon.com', 'www.nekutoon.com'];
  var DEV_HOSTS = ['localhost', '127.0.0.1', ''];
  var host = window.location.hostname;

  if (DEV_HOSTS.indexOf(host) !== -1) return;

  if (OFFICIAL_HOSTS.indexOf(host) === -1) {
    window.location.replace('https://nekutoon.com' + window.location.pathname + window.location.search);
    return;
  }

  // fuerza siempre https y el host sin "www."
  if (window.location.protocol !== 'https:' || host === 'www.nekutoon.com') {
    window.location.replace('https://nekutoon.com' + window.location.pathname + window.location.search);
  }

  // evita que alguien empotre el sitio en un <iframe> ajeno
  if (window.top !== window.self) {
    try {
      window.top.location = window.self.location;
    } catch (e) {
      document.documentElement.style.display = 'none';
    }
  }
})();
