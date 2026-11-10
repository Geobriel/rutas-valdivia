/* sw.js — Modo sin conexión: guarda la app y la red, y las teselas del mapa que se van viendo.
 * VERSION la reescribe `python rutas_pendiente.py --web` (y crear_exe.py) con un hash de los archivos:
 * si algo cambia, el teléfono baja la versión nueva la próxima vez que abre la app con internet. */
const VERSION = 'e8ebbd1e4511';
const APP = 'rutas-app-' + VERSION;
const TESELAS = 'rutas-teselas';
const MAX_TESELAS = 3000;
const ARCHIVOS = ['./', 'index.html', 'app.css', 'app.js', 'ruteo.js', 'red.json', 'red.bin', 'manifest.webmanifest',
  'vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css', 'vendor/leaflet/images/layers.png',
  'vendor/leaflet/images/layers-2x.png', 'iconos/icono-192.png', 'iconos/icono-512.png', 'iconos/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(APP).then(c => c.addAll(ARCHIVOS.map(a => new Request(a, { cache: 'reload' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== APP && k !== TESELAS).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.origin === location.origin) {
    // la app: primero lo guardado (funciona sin internet); si no está, la red
    e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(r => r || fetch(e.request)));
  } else if (/tile\.openstreetmap\.org|arcgisonline\.com/.test(url.hostname)) {
    // teselas: las ya vistas salen de la memoria; las nuevas se bajan y se guardan
    e.respondWith(caches.open(TESELAS).then(async c => {
      const r = await c.match(e.request);
      if (r) return r;
      const nueva = await fetch(e.request);
      if (nueva.ok) {
        await c.put(e.request, nueva.clone());
        const ks = await c.keys();
        for (let i = 0; i < ks.length - MAX_TESELAS; i++) await c.delete(ks[i]);
      }
      return nueva;
    }));
  }
});
