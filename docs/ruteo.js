/*
 * ruteo.js — Ruta óptima de ida y vuelta evitando subidas empinadas (mismo modelo que rutas_pendiente.py).
 *
 * Lee la red que escribe `python rutas_pendiente.py --web` (red.json + red.bin) y calcula todo en el
 * navegador, sin servidor. Costo de un tramo de largo L con pendiente g en el sentido de avance:
 *     costo = L · (1 + A·max(g,0) + F·0,1·(100·max(g − umbral, 0))²),  A = 8 (Naismith; Scarf, 2007)
 * Tiempo a pie: Tobler (1993), km/h = 6·exp(−3,5·|g + 0,05|).
 * Funciona en el navegador (window.Ruteo) y en Node (require), para probarlo.
 */
(function (raiz) {
  'use strict';

  class Red {
    constructor(meta, buffer) {
      const N = meta.N, E = meta.E;
      this.meta = meta; this.N = N; this.E = E;
      this.A = meta.A_naismith || 8;
      let o = 0;
      const i32 = n => { const a = new Int32Array(buffer, o, n); o += 4 * n; return a; };
      const f32 = n => { const a = new Float32Array(buffer, o, n); o += 4 * n; return a; };
      const u8 = n => { const a = new Uint8Array(buffer, o, n); o += n; return a; };
      const lat = i32(N), lon = i32(N);
      this.z = f32(N);
      this.u = i32(E); this.v = i32(E); this.L = f32(E); this.nombre = i32(E);
      this.esc = u8(E); this.sinEsc = u8(N);
      this.lat = new Float64Array(N); this.lon = new Float64Array(N);
      for (let i = 0; i < N; i++) { this.lat[i] = lat[i] / 1e6; this.lon[i] = lon[i] / 1e6; }
      // pendiente de cada tramo en el sentido u→v
      this.g = new Float64Array(E);
      for (let e = 0; e < E; e++) {
        const g = (this.z[this.v[e]] - this.z[this.u[e]]) / Math.max(this.L[e], 0.5);
        this.g[e] = Math.max(-0.5, Math.min(0.5, g));
      }
      // vecinos de cada nodo (formato CSR): tramo y sentido (+1 = u→v, −1 = v→u)
      const grado = new Int32Array(N + 1);
      for (let e = 0; e < E; e++) { grado[this.u[e] + 1]++; grado[this.v[e] + 1]++; }
      for (let i = 0; i < N; i++) grado[i + 1] += grado[i];
      this.ini = grado;
      this.adjT = new Int32Array(2 * E); this.adjS = new Int8Array(2 * E);
      const pos = grado.slice(0, N);
      for (let e = 0; e < E; e++) {
        let p = pos[this.u[e]]++; this.adjT[p] = e; this.adjS[p] = 1;
        p = pos[this.v[e]]++; this.adjT[p] = e; this.adjS[p] = -1;
      }
      // grilla de 50 m para encontrar el nodo más cercano a un clic
      this.lat0 = (meta.bbox[1] + meta.bbox[3]) / 2; this.lon0 = (meta.bbox[0] + meta.bbox[2]) / 2;
      this.mx = 111320 * Math.cos(this.lat0 * Math.PI / 180); this.my = 110574;
      this.celda = 50;
      this.grilla = new Map();
      for (let i = 0; i < N; i++) {
        const k = this._clave(this.lat[i], this.lon[i]);
        let l = this.grilla.get(k); if (!l) this.grilla.set(k, l = []); l.push(i);
      }
      // memoria reutilizable de Dijkstra
      this.dist = new Float64Array(N); this.prevE = new Int32Array(N);
      this._costos = {};
    }

    _xy(lat, lon) { return [(lon - this.lon0) * this.mx, (lat - this.lat0) * this.my]; }
    _clave(lat, lon) {
      const [x, y] = this._xy(lat, lon);
      return Math.floor(x / this.celda) + ',' + Math.floor(y / this.celda);
    }

    /** Nodo más cercano a (lat, lon); sin escaleras, solo nodos de la red que queda conectada sin ellas. */
    nodoCercano(lat, lon, escaleras) {
      const [x, y] = this._xy(lat, lon);
      const cx = Math.floor(x / this.celda), cy = Math.floor(y / this.celda);
      let mejor = -1, dmin = Infinity;
      for (let r = 0; r < 60; r++) {
        for (let i = -r; i <= r; i++) for (let j = -r; j <= r; j++) {
          if (Math.max(Math.abs(i), Math.abs(j)) !== r) continue;
          const l = this.grilla.get((cx + i) + ',' + (cy + j)); if (!l) continue;
          for (const n of l) {
            if (!escaleras && !this.sinEsc[n]) continue;
            const [nx, ny] = this._xy(this.lat[n], this.lon[n]);
            const d = Math.hypot(nx - x, ny - y);
            if (d < dmin) { dmin = d; mejor = n; }
          }
        }
        if (mejor >= 0 && dmin <= r * this.celda) break;
      }
      return { nodo: mejor, dist: dmin };
    }

    /** Costo de cada tramo en los dos sentidos (Infinity = prohibido). */
    costos(umbral, fuerza, escaleras, soloDistancia) {
      const clave = [umbral, fuerza, escaleras, soloDistancia].join('|');
      if (this._costos[clave]) return this._costos[clave];
      const E = this.E, ida = new Float64Array(E), vuelta = new Float64Array(E);
      const f = g => {
        const sube = Math.max(g, 0), exceso = Math.max(g - umbral, 0) * 100;
        return 1 + this.A * sube + fuerza * 0.1 * exceso * exceso;
      };
      for (let e = 0; e < E; e++) {
        if (!escaleras && this.esc[e]) { ida[e] = vuelta[e] = Infinity; continue; }
        const L = this.L[e];
        if (soloDistancia) { ida[e] = vuelta[e] = L + 1e-6; continue; }
        ida[e] = L * f(this.g[e]) + 1e-6;
        vuelta[e] = L * f(-this.g[e]) + 1e-6;
      }
      if (Object.keys(this._costos).length > 6) this._costos = {};
      return (this._costos[clave] = [ida, vuelta]);
    }

    /** Dijkstra de a a b; devuelve la lista de tramos recorridos (o null). */
    camino(a, b, [cIda, cVuelta]) {
      const dist = this.dist, prevE = this.prevE;
      dist.fill(Infinity); prevE.fill(-1);
      const heap = new Monticulo();
      dist[a] = 0; heap.push(0, a);
      while (heap.size) {
        const [d, n] = heap.pop();
        if (d > dist[n]) continue;
        if (n === b) break;
        for (let p = this.ini[n], fin = this.ini[n + 1]; p < fin; p++) {
          const e = this.adjT[p], s = this.adjS[p];
          const c = s > 0 ? cIda[e] : cVuelta[e];
          if (c === Infinity) continue;
          const m = s > 0 ? this.v[e] : this.u[e];
          const nd = d + c;
          if (nd < dist[m]) { dist[m] = nd; prevE[m] = e; heap.push(nd, m); }
        }
      }
      if (a !== b && prevE[b] < 0) return null;
      const nodos = [b], tramos = [];
      let n = b;
      while (n !== a) {
        const e = prevE[n]; tramos.push(e);
        n = this.u[e] === n ? this.v[e] : this.u[e];
        nodos.push(n);
      }
      return { nodos: nodos.reverse(), tramos: tramos.reverse() };
    }

    describir({ nodos, tramos }, umbral, completo = true) {
      const n = nodos.length;
      const d = new Float64Array(n), z = new Float64Array(n);
      for (let i = 0; i < n; i++) z[i] = this.z[nodos[i]];
      const dL = [], g = [];
      for (let i = 0; i < n - 1; i++) {
        const L = this.L[tramos[i]];
        d[i + 1] = d[i] + L; dL.push(L);
        g.push((z[i + 1] - z[i]) / Math.max(L, 0.5));
      }
      // pendiente máxima en ventanas de ≥ 30 m
      let gmax = -Infinity, j = 0;
      for (let i = 0; i < n; i++) {
        if (j < i) j = i;
        while (j < n && d[j] < d[i] + 30) j++;
        if (j >= n) break;
        gmax = Math.max(gmax, (z[j] - z[i]) / (d[j] - d[i]));
      }
      if (gmax === -Infinity) gmax = Math.max(0, ...g);
      let sube = 0, baja = 0, sobre = 0, t = 0;
      for (let i = 0; i < n - 1; i++) {
        const dz = z[i + 1] - z[i];
        if (dz > 0) sube += dz; else baja -= dz;
        if (g[i] > umbral) sobre += dL[i];
        t += dL[i] / (6 * Math.exp(-3.5 * Math.abs(g[i] + 0.05)) / 3.6);
      }
      const r1 = x => Math.round(x * 10) / 10;
      const out = {
        stats: {
          distancia_m: Math.round(d[n - 1]), subida_m: r1(sube), bajada_m: r1(baja),
          pend_max_pct: r1(100 * gmax), m_sobre_umbral: Math.round(sobre), tiempo_pie_min: r1(t / 60),
        },
        coords: nodos.map((k, i) => [this.lat[k], this.lon[k], r1(z[i])]),
      };
      if (!completo) return out;
      out.perfil = Array.from(d, (x, i) => [x, z[i]]);
      // tramos que suben más que el umbral, unidos cuando son seguidos
      out.empinados = [];
      let act = null;
      for (let i = 0; i < n - 1; i++) {
        if (!(g[i] > umbral)) { act = null; continue; }
        if (act) { act.fin = i + 1; act.g = Math.max(act.g, g[i]); }
        else out.empinados.push(act = { ini: i, fin: i + 1, g: g[i] });
      }
      out.empinados = out.empinados.map(e => ({
        coords: nodos.slice(e.ini, e.fin + 1).map(k => [this.lat[k], this.lon[k]]), pct: r1(100 * e.g),
      }));
      // calles por las que pasa (sin las de menos de 40 m)
      const calles = [];
      for (let i = 0; i < tramos.length; i++) {
        const k = this.nombre[tramos[i]];
        const nom = k >= 0 ? this.meta.nombres[k] : '';
        const ult = calles[calles.length - 1];
        if (ult && ult.nombre === nom) ult.m += dL[i]; else calles.push({ nombre: nom, m: dL[i] });
      }
      const lista = [];
      for (const c of calles) if (c.nombre && c.m >= 40 && lista[lista.length - 1] !== c.nombre) lista.push(c.nombre);
      out.calles = lista;
      return out;
    }

    /** Ida A→B, vuelta B→A y las más cortas sin mirar la pendiente. a y b: [lat, lon]. */
    rutas(a, b, { umbral = 0.06, fuerza = 2, escaleras = false } = {}) {
      const A = this.nodoCercano(a[0], a[1], escaleras), B = this.nodoCercano(b[0], b[1], escaleras);
      if (A.dist > 150 || B.dist > 150)
        return { error: `Un punto quedó a más de 150 m de la red (A: ${A.dist.toFixed(0)} m, B: ${B.dist.toFixed(0)} m). La red cubre solo la ciudad de Valdivia.` };
      const c = this.costos(umbral, fuerza, escaleras, false), c0 = this.costos(umbral, fuerza, escaleras, true);
      const out = { snap_m: [Math.round(A.dist), Math.round(B.dist)] };
      for (const [nom, o, d] of [['ida', A.nodo, B.nodo], ['vuelta', B.nodo, A.nodo]]) {
        const cam = this.camino(o, d, c), corto = this.camino(o, d, c0);
        if (!cam) return { error: 'No hay camino entre los dos puntos.' };
        out[nom] = this.describir(cam, umbral);
        out['corta_' + nom] = this.describir(corto, umbral, false);
      }
      return out;
    }

    /** Tramos con |pendiente| ≥ 6 %, en tres clases, para la capa de referencia. */
    callesEmpinadas() {
      const clases = [[0.06, 0.09, '6–9 %'], [0.09, 0.12, '9–12 %'], [0.12, 9, '> 12 %']];
      return clases.map(([lo, hi, nombre]) => {
        const lineas = [];
        for (let e = 0; e < this.E; e++) {
          const ag = Math.abs(this.g[e]);
          if (ag >= lo && ag < hi && this.L[e] >= 2)
            lineas.push([[this.lat[this.u[e]], this.lon[this.u[e]]], [this.lat[this.v[e]], this.lon[this.v[e]]]]);
        }
        return { clase: nombre, lineas };
      });
    }
  }

  /** Montículo binario de mínimos (costo, nodo). */
  class Monticulo {
    constructor() { this.k = []; this.n = []; }
    get size() { return this.k.length; }
    push(k, n) {
      const K = this.k, V = this.n; let i = K.length; K.push(k); V.push(n);
      while (i > 0) {
        const p = (i - 1) >> 1; if (K[p] <= k) break;
        K[i] = K[p]; V[i] = V[p]; i = p;
      }
      K[i] = k; V[i] = n;
    }
    pop() {
      const K = this.k, V = this.n, top = [K[0], V[0]];
      const k = K.pop(), n = V.pop();
      if (K.length) {
        let i = 0; const m = K.length;
        while (true) {
          let c = 2 * i + 1; if (c >= m) break;
          if (c + 1 < m && K[c + 1] < K[c]) c++;
          if (K[c] >= k) break;
          K[i] = K[c]; V[i] = V[c]; i = c;
        }
        K[i] = k; V[i] = n;
      }
      return top;
    }
  }

  const Ruteo = { Red };
  if (typeof module !== 'undefined' && module.exports) module.exports = Ruteo; else raiz.Ruteo = Ruteo;
})(typeof self !== 'undefined' ? self : this);
