/* app.js — Interfaz: mapa, puntos A y B, GPS, perfiles, GPX, enlace para compartir y modo sin conexión. */
'use strict';
const $ = s => document.querySelector(s);
const panel = $('#panel');
let red = null, A = null, B = null, ultimo = null, capaEmp = null, seguimiento = null, yoMarca = null, yoCirculo = null;

// --- ajustes guardados en este navegador (si se puede) ----------------------------------------
const guardado = (() => { try { return JSON.parse(localStorage.getItem('rutas-ajustes') || '{}'); } catch { return {}; } })();
function guardar() {
  try { localStorage.setItem('rutas-ajustes', JSON.stringify({ u: $('#umbral').value, f: $('#fuerza').value, e: $('#escaleras').checked })); } catch { /* sin almacenamiento */ }
}
if (guardado.u) $('#umbral').value = guardado.u;
if (guardado.f) $('#fuerza').value = guardado.f;
if (guardado.e) $('#escaleras').checked = true;

// --- mapa ----------------------------------------------------------------------------------------
const mapa = L.map('mapa', { zoomControl: true }).setView([-39.8142, -73.2459], 14);
const calles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, crossOrigin: true,
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · alturas FABDEM' }).addTo(mapa);
const satelite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 19, crossOrigin: true, attribution: 'Imagen © Esri' });
L.control.layers({ 'Calles': calles, 'Satélite': satelite }).addTo(mapa);
const capaRutas = L.layerGroup().addTo(mapa);

// en el celular el panel va abajo: el mapa se acomoda a su alto
let encuadre = null;          // límites a mostrar apenas el panel tenga su tamaño final
function encuadrar(limites) {
  encuadre = limites;
  mapa.invalidateSize(); mapa.fitBounds(limites, { padding: [40, 40], animate: false });
  setTimeout(() => { encuadre = null; }, 1500);
}
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--alto-panel', panel.offsetHeight + 'px');
  mapa.invalidateSize();
  if (encuadre) mapa.fitBounds(encuadre, { padding: [40, 40], animate: false });
}).observe(panel);
$('#plegar').onclick = () => {
  panel.classList.toggle('abierto');
  $('#plegar').textContent = panel.classList.contains('abierto') ? 'Detalles ▾' : 'Detalles ▴';
};

const icono = (t, c) => L.divIcon({ className: '', iconSize: [28, 28], iconAnchor: [14, 14],
  html: `<div style="width:28px;height:28px;border-radius:50%;background:${c};color:#fff;font:700 14px system-ui;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 0 4px #0009">${t}</div>` });

function estado(txt, error = false) { $('#estado').textContent = txt; $('#estado').className = error ? 'error' : ''; }

function ponerA(latlng) {
  if (A) A.setLatLng(latlng);
  else { A = L.marker(latlng, { draggable: true, icon: icono('A', '#1f6feb') }).addTo(mapa); A.on('dragend', calcular); }
}
function ponerB(latlng) {
  if (B) B.setLatLng(latlng);
  else { B = L.marker(latlng, { draggable: true, icon: icono('B', '#e8590c') }).addTo(mapa); B.on('dragend', calcular); }
}

mapa.on('click', e => {
  if (!red) return;
  if (!A) { ponerA(e.latlng); estado('Ahora toca el destino (B).'); }
  else { ponerB(e.latlng); calcular(); }
});

// --- controles -----------------------------------------------------------------------------------
const etiquetas = () => { $('#vu').textContent = $('#umbral').value; $('#vf').textContent = $('#fuerza').value; };
etiquetas();
for (const id of ['umbral', 'fuerza']) $('#' + id).addEventListener('input', etiquetas);
for (const id of ['umbral', 'fuerza', 'escaleras']) $('#' + id).addEventListener('change', () => { guardar(); calcular(); });

$('#limpiar').onclick = () => {
  if (A) mapa.removeLayer(A); if (B) mapa.removeLayer(B);
  A = B = ultimo = null; capaRutas.clearLayers();
  $('#resumen').innerHTML = $('#perfiles').innerHTML = '';
  history.replaceState(null, '', location.pathname + location.search);
  estado('Toca el mapa para poner el inicio (A), o usa 📍.');
};

$('#capa').onchange = () => {
  if (!$('#capa').checked) { if (capaEmp) mapa.removeLayer(capaEmp); return; }
  if (!capaEmp) {
    const col = { '6–9 %': '#f4c20d', '9–12 %': '#f08c00', '> 12 %': '#c92a2a' };
    const renderer = L.canvas({ padding: 0.3 });
    capaEmp = L.layerGroup(red.callesEmpinadas().map(c =>
      L.polyline(c.lineas, { color: col[c.clase], weight: 3, opacity: 0.85, renderer, interactive: false })));
  }
  capaEmp.addTo(mapa);
};

// --- GPS -----------------------------------------------------------------------------------------
function dondeEstoy(pos) {
  const ll = [pos.coords.latitude, pos.coords.longitude];
  if (!yoMarca) {
    yoCirculo = L.circle(ll, { radius: pos.coords.accuracy, color: '#1f6feb', weight: 1, fillOpacity: 0.1, interactive: false }).addTo(mapa);
    yoMarca = L.circleMarker(ll, { radius: 7, color: '#fff', weight: 2, fillColor: '#1f6feb', fillOpacity: 1 }).addTo(mapa);
  } else { yoMarca.setLatLng(ll); yoCirculo.setLatLng(ll).setRadius(pos.coords.accuracy); }
  return ll;
}
const errorGPS = e => estado(e.code === 1 ? 'No diste permiso para usar la ubicación.' : 'No pude obtener la ubicación (' + e.message + ').', true);

$('#miUbic').onclick = () => {
  if (!navigator.geolocation) return estado('Este navegador no tiene GPS.', true);
  estado('Buscando tu ubicación…');
  navigator.geolocation.getCurrentPosition(pos => {
    const ll = dondeEstoy(pos);
    ponerA(L.latLng(ll));
    mapa.setView(ll, Math.max(mapa.getZoom(), 16));
    if (B) calcular(); else estado(`Inicio en tu ubicación (±${Math.round(pos.coords.accuracy)} m). Ahora toca el destino (B).`);
  }, errorGPS, { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 });
};

$('#seguir').onclick = () => {
  if (seguimiento !== null) {
    navigator.geolocation.clearWatch(seguimiento); seguimiento = null;
    $('#seguir').classList.remove('activo');
    if (yoMarca) { mapa.removeLayer(yoMarca); mapa.removeLayer(yoCirculo); yoMarca = yoCirculo = null; }
    return;
  }
  if (!navigator.geolocation) return estado('Este navegador no tiene GPS.', true);
  $('#seguir').classList.add('activo');
  let primera = true;
  seguimiento = navigator.geolocation.watchPosition(pos => {
    const ll = dondeEstoy(pos);
    if (primera) { mapa.setView(ll, Math.max(mapa.getZoom(), 16)); primera = false; }
    else if (!mapa.getBounds().pad(-0.15).contains(ll)) mapa.panTo(ll);
  }, errorGPS, { enableHighAccuracy: true, maximumAge: 5000 });
};

// --- cálculo y dibujo ----------------------------------------------------------------------------
function calcular() {
  if (!red || !A || !B) return;
  const a = A.getLatLng(), b = B.getLatLng();
  const params = { umbral: $('#umbral').value / 100, fuerza: +$('#fuerza').value, escaleras: $('#escaleras').checked };
  estado('Calculando…');
  setTimeout(() => {            // deja que el navegador pinte «Calculando…»
    const t0 = performance.now();
    const r = red.rutas([a.lat, a.lng], [b.lat, b.lng], params);
    if (r.error) { capaRutas.clearLayers(); $('#resumen').innerHTML = $('#perfiles').innerHTML = ''; return estado(r.error, true); }
    ultimo = r;
    dibujar(r);
    const f = x => x.toFixed(5);
    history.replaceState(null, '', `#a=${f(a.lat)},${f(a.lng)}&b=${f(b.lat)},${f(b.lng)}&u=${$('#umbral').value}&f=${$('#fuerza').value}&e=${params.escaleras ? 1 : 0}`);
    estado(`Listo en ${Math.round(performance.now() - t0)} ms. Puntos ajustados a la calle: A ${r.snap_m[0]} m, B ${r.snap_m[1]} m.`);
  }, 20);
}

function dibujar(r) {
  capaRutas.clearLayers();
  const ll = c => c.map(p => [p[0], p[1]]);
  const gris = { color: '#6c757d', weight: 3, dashArray: '2 7', opacity: 0.95 };
  L.polyline(ll(r.corta_ida.coords), gris).bindTooltip('más corta ida (sin mirar pendientes)').addTo(capaRutas);
  L.polyline(ll(r.corta_vuelta.coords), gris).bindTooltip('más corta vuelta (sin mirar pendientes)').addTo(capaRutas);
  L.polyline(ll(r.vuelta.coords), { color: '#e8590c', weight: 8, opacity: 0.7 }).bindTooltip('vuelta B→A').addTo(capaRutas);
  L.polyline(ll(r.ida.coords), { color: '#1f6feb', weight: 4, opacity: 0.95 }).bindTooltip('ida A→B').addTo(capaRutas);
  for (const k of ['ida', 'vuelta'])
    for (const e of r[k].empinados)
      L.polyline(e.coords, { color: '#d00000', weight: 3 }).bindTooltip(`subida de ${e.pct} % (${k})`).addTo(capaRutas);

  const fila = (n, chip, s) => `<tr><td>${chip}${n}</td><td>${(s.distancia_m / 1000).toFixed(2)}</td><td>${s.subida_m}</td>
    <td>${s.pend_max_pct}</td><td>${s.m_sobre_umbral}</td><td>${Math.round(s.tiempo_pie_min)}</td></tr>`;
  const c = col => `<span class="chip" style="background:${col}"></span>`, p = '<span class="chip punteado"></span>';
  $('#resumen').innerHTML = `<table>
    <tr><th></th><th>km</th><th>sube m</th><th>máx %</th><th>m &gt; umbral</th><th>min a pie</th></tr>
    ${fila('Ida', c('#1f6feb'), r.ida.stats)}${fila('Vuelta', c('#e8590c'), r.vuelta.stats)}
    ${fila('Corta ida', p, r.corta_ida.stats)}${fila('Corta vuelta', p, r.corta_vuelta.stats)}</table>
    <p class="nota">Ida A→B, vuelta B→A; «corta»: la más corta sin mirar pendientes (gris punteado). «máx %»: la subida
    más empinada, medida en 30 m. En rojo en el mapa: tramos que suben más que el umbral.</p>`;
  $('#perfiles').innerHTML = `
    <p class="tit">Ida (A→B)</p><p class="calles">${r.ida.calles.join(' → ') || ''}</p>${perfil(r.ida.perfil, '#1f6feb')}
    <p class="tit">Vuelta (B→A)</p><p class="calles">${r.vuelta.calles.join(' → ') || ''}</p>${perfil(r.vuelta.perfil, '#e8590c')}`;
}

function perfil(p, color) {
  const W = 330, H = 110, m = { l: 34, r: 6, t: 6, b: 16 };
  const dmax = p[p.length - 1][0] || 1;
  let zmin = Infinity, zmax = -Infinity;
  for (const q of p) { zmin = Math.min(zmin, q[1]); zmax = Math.max(zmax, q[1]); }
  if (zmax - zmin < 10) { const c = (zmax + zmin) / 2; zmin = c - 5; zmax = c + 5; }
  const X = d => m.l + (W - m.l - m.r) * d / dmax, Y = z => m.t + (H - m.t - m.b) * (1 - (z - zmin) / (zmax - zmin));
  const pts = p.map(q => `${X(q[0]).toFixed(1)},${Y(q[1]).toFixed(1)}`).join(' ');
  return `<svg class="perfil" viewBox="0 0 ${W} ${H}" role="img" aria-label="Perfil de altura">
    <polyline points="${X(0)},${Y(zmin)} ${pts} ${X(dmax)},${Y(zmin)}" fill="${color}26" stroke="none"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6"/>
    <text x="${m.l - 4}" y="${Y(zmax) + 4}" font-size="10" text-anchor="end" fill="currentColor" opacity=".6">${zmax.toFixed(0)} m</text>
    <text x="${m.l - 4}" y="${Y(zmin)}" font-size="10" text-anchor="end" fill="currentColor" opacity=".6">${zmin.toFixed(0)} m</text>
    <text x="${W - m.r}" y="${H - 3}" font-size="10" text-anchor="end" fill="currentColor" opacity=".6">${(dmax / 1000).toFixed(2)} km</text></svg>`;
}

// --- GPX y compartir -----------------------------------------------------------------------------
$('#gpx').onclick = () => {
  if (!ultimo) return estado('Primero calcula una ruta.', true);
  const trk = (n, c) => `<trk><name>${n}</name><trkseg>${c.map(p => `<trkpt lat="${p[0]}" lon="${p[1]}"><ele>${p[2]}</ele></trkpt>`).join('')}</trkseg></trk>`;
  const gpx = `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Rutas sin cuestas" xmlns="http://www.topografix.com/GPX/1/1">${trk('Ida A-B', ultimo.ida.coords)}${trk('Vuelta B-A', ultimo.vuelta.coords)}</gpx>`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([gpx], { type: 'application/gpx+xml' }));
  a.download = 'ruta_ida_vuelta.gpx'; document.body.appendChild(a); a.click(); a.remove();
};
$('#compartir').onclick = async () => {
  if (!ultimo) return estado('Primero calcula una ruta.', true);
  const url = location.href;
  try {
    if (navigator.share) await navigator.share({ title: 'Ruta sin cuestas', url });
    else { await navigator.clipboard.writeText(url); estado('Enlace copiado: al abrirlo se ve esta misma ruta.'); }
  } catch { /* el usuario canceló */ }
};

// --- instalar como app ---------------------------------------------------------------------------
let avisoInstalar = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); avisoInstalar = e; $('#instalar').hidden = false; });
$('#instalar').onclick = async () => { if (avisoInstalar) { avisoInstalar.prompt(); await avisoInstalar.userChoice; avisoInstalar = null; $('#instalar').hidden = true; } };
const esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
if (esIOS && !navigator.standalone) $('#instalarIOS').hidden = false;
if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('sw.js').catch(() => {});

// --- carga de la red -----------------------------------------------------------------------------
(async function cargar() {
  try {
    const meta = await (await fetch('red.json')).json();
    estado(`Cargando la red de calles (${(meta.N / 1000).toFixed(0)} mil nodos)…`);
    const buf = await (await fetch('red.bin')).arrayBuffer();
    red = new Ruteo.Red(meta, buf);
    const bb = meta.bbox;
    L.rectangle([[bb[1], bb[0]], [bb[3], bb[2]]], { color: '#888', weight: 1, fill: false, dashArray: '4', interactive: false }).addTo(mapa);
    $('#info').innerHTML = Object.entries(meta.resumen).map(([k, v]) => `${k}: <b>${v}</b>`).join('<br>')
      + `<br>DEM: ${meta.dem}<br>Red armada el ${meta.fecha} (versión ${meta.version}).`;
    // ¿viene una ruta en el enlace?
    const h = new URLSearchParams(location.hash.slice(1));
    if (h.get('u')) $('#umbral').value = h.get('u');
    if (h.get('f')) $('#fuerza').value = h.get('f');
    if (h.get('e')) $('#escaleras').checked = h.get('e') === '1';
    etiquetas();
    if (h.get('a') && h.get('b')) {
      const pa = h.get('a').split(',').map(Number), pb = h.get('b').split(',').map(Number);
      ponerA(L.latLng(pa)); ponerB(L.latLng(pb));
      calcular();
      setTimeout(() => encuadrar([pa, pb]), 100);
    } else {
      mapa.fitBounds([[bb[1], bb[0]], [bb[3], bb[2]]]);
      estado('Toca el mapa para poner el inicio (A), o usa 📍.');
    }
  } catch (e) {
    estado('No pude cargar la red: ' + e.message, true);
  }
})();
