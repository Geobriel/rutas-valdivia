"""
rutas_pendiente.py — Ruta óptima de ida y de vuelta en Valdivia evitando subidas empinadas.

Uso (con el .venv de SiSCoSu, que ya tiene todo lo necesario):

    python rutas_pendiente.py                 # abre el mapa en el navegador
    python rutas_pendiente.py --actualizar    # vuelve a bajar las calles de OSM
    python rutas_pendiente.py --exportar      # además guarda la red corregida en salidas/red_corregida.gpkg
    python rutas_pendiente.py --sin-mapa --web   # escribe la red para la app web y el .exe (docs/)
    python rutas_pendiente.py --dem otro.tif  # usa otro DEM (p. ej., un LiDAR) en vez de FABDEM

En el mapa: primer clic = inicio (A), segundo clic = destino (B). Los marcadores se pueden arrastrar.
Se calculan la ida A→B y la vuelta B→A. Todas las vías valen en los dos sentidos (se ignora el
sentido del tránsito), pero el costo de cada tramo depende del sentido: subir cuesta, bajar no.

Pasos
-----
1. Calles: todas las vías `highway=*` de OpenStreetMap del recuadro (API Overpass), salvo las que
   no se pueden recorrer (en construcción, proyectadas, autopistas, acceso privado sin permiso).
2. Corrección de topología (la red queda con un nodo en cada punto donde de verdad se conectan):
   a. nodos duplicados (a < 0,2 m, mismo nivel) → se funden;
   b. vías que se cruzan o se tocan sin nodo común, en el mismo nivel (misma `layer`, ninguna es
      puente o túnel distinto) → se agrega el nodo de cruce;
   c. vías que terminan a menos de 3 m de otra vía del mismo nivel sin tocarla (error típico
      de dibujo) → se unen con un conector corto;
   d. tramos de largo cero y lazos → se eliminan;
   e. pedazos de red aislados → se descartan (se guarda solo la red conectada más grande).
   Los puentes y túneles NO se conectan con lo que pasa por debajo o por encima.
3. Altura: DEM FABDEM 30 m (Hawker et al., 2022), que es el Copernicus GLO-30 sin edificios ni
   árboles, interpolado bilinealmente en nodos cada ≤ 10 m. En puentes y túneles la altura del
   DEM es la del río o del cerro, así que ahí se interpola entre los extremos del puente.
4. Costo de un tramo de largo L con pendiente g en el sentido de avance (g > 0 = subida):
       costo = L · (1 + A·g⁺ + F·0,1·(100·max(g − umbral, 0))²)
   - A·g⁺: cada metro subido equivale a A metros planos (A = 8, regla de Naismith; Scarf, 2007).
   - el término cuadrático castiga fuerte las subidas sobre el umbral (por defecto 6 %), con
     fuerza F ajustable en el mapa. Bajar no se castiga.
   La ruta óptima es la de menor costo total (Dijkstra). Tiempo a pie con Tobler (1993).

Referencias
- Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022). A 30 m global
  map of elevation with forests and buildings removed. Environmental Research Letters, 17(2), 024016.
  https://doi.org/10.1088/1748-9326/ac4d4f  (licencia CC BY-NC-SA 4.0, uso no comercial)
- Scarf, P. (2007). Route choice in mountain navigation, Naismith's rule, and the equivalence of
  distance and climb. Journal of Sports Sciences, 25(6), 719–726. https://doi.org/10.1080/02640410600874906
- Tobler, W. (1993). Three presentations on geographical analysis and modeling (Technical Report 93-1).
  NCGIA, University of California, Santa Barbara.
"""

import argparse
import json
import math
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import requests
import rioxarray as rxr
import shapely
from pyproj import Transformer
from scipy.interpolate import RegularGridInterpolator
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

RAIZ = Path(__file__).resolve().parent
CACHE = RAIZ / "cache"
SALIDAS = RAIZ / "salidas"

BBOX_VALDIVIA = (-73.31, -39.875, -73.16, -39.765)   # oeste, sur, este, norte (grados)
FABDEM_ZIP = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/{bloque}_FABDEM_V1-2.zip"
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]

A_NAISMITH = 8.0     # metros planos equivalentes a 1 m de subida
PASO = 10.0          # largo máximo de cada tramo de la red (m)
EPS_NODO = 0.2       # dos puntos a menos de esto son el mismo nodo (m)
TOL_CONECTOR = 3.0   # una vía que termina a menos de esto de otra se conecta (m)

# vías que no se pueden recorrer
EXCLUIR_HIGHWAY = {"proposed", "construction", "abandoned", "razed", "disused", "platform",
                   "bus_stop", "corridor", "elevator", "raceway", "rest_area", "services",
                   "via_ferrata", "escape", "emergency_bay", "busway", "bus_guideway",
                   "motorway", "motorway_link"}
PERMISO = {"yes", "designated", "permissive", "destination"}

A_UTM = Transformer.from_crs(4326, 32718, always_xy=True)
A_GEO = Transformer.from_crs(32718, 4326, always_xy=True)


# ----------------------------------------------------------------------------------------------
# 1. Datos de entrada
# ----------------------------------------------------------------------------------------------

def bajar_osm(bbox, actualizar=False):
    """Todas las vías highway=* del recuadro, con sus nodos, desde Overpass (en caché)."""
    w, s, e, n = bbox
    archivo = CACHE / f"osm_{w}_{s}_{e}_{n}.json"
    if archivo.exists() and not actualizar:
        print(f"OSM: leo la caché {archivo.name}")
        return json.loads(archivo.read_text(encoding="utf-8"))
    consulta = f'[out:json][timeout:300];way["highway"]({s},{w},{n},{e});(._;>;);out body;'
    for url in OVERPASS:
        try:
            print(f"OSM: descargando calles de {url} ...")
            r = requests.post(url, data={"data": consulta}, timeout=200,
                              headers={"User-Agent": "rutas-pendiente/1.0"})
            r.raise_for_status()
            datos = r.json()
            break
        except Exception as error:  # probar el otro servidor
            print(f"   falló ({error})")
    else:
        raise RuntimeError("No pude bajar OSM de ningún servidor Overpass.")
    CACHE.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    return datos


def extension_osm(osm, bbox):
    """Recuadro que cubre el recuadro pedido y TODOS los nodos bajados: Overpass entrega las vías
    completas aunque se salgan del recuadro, y el DEM tiene que cubrirlas (si no, quedan sin altura)."""
    lon = [el["lon"] for el in osm["elements"] if el["type"] == "node"]
    lat = [el["lat"] for el in osm["elements"] if el["type"] == "node"]
    r = lambda x, f: round(f(x * 100) / 100, 2)          # a la centésima de grado, hacia afuera
    return [r(min(bbox[0], min(lon)), math.floor), r(min(bbox[1], min(lat)), math.floor),
            r(max(bbox[2], max(lon)), math.ceil), r(max(bbox[3], max(lat)), math.ceil)]


def bajar_fabdem(bbox):
    """Recorta FABDEM al recuadro leyendo solo la tesela necesaria dentro del zip remoto."""
    w, s, e, n = bbox
    archivo = CACHE / f"fabdem_{w}_{s}_{e}_{n}.tif"
    if archivo.exists():
        print(f"DEM: leo la caché {archivo.name}")
        return archivo
    lat0, lon0 = math.floor(s), math.floor(w)
    if math.floor(n) != lat0 or math.floor(e) != lon0:
        raise RuntimeError("El recuadro cruza dos teselas de FABDEM; usa --dem con un DEM propio.")
    tesela = f"{'S' if lat0 < 0 else 'N'}{abs(lat0):02d}{'W' if lon0 < 0 else 'E'}{abs(lon0):03d}"
    la, lo = math.floor(lat0 / 10) * 10, math.floor(lon0 / 10) * 10
    def nombre(lat, lon):
        return f"{'S' if lat < 0 else 'N'}{abs(lat):02d}{'W' if lon < 0 else 'E'}{abs(lon):03d}"
    bloque = f"{nombre(la, lo)}-{nombre(la + 10, lo + 10)}"
    ruta = f"/vsizip//vsicurl/{FABDEM_ZIP.format(bloque=bloque)}/{tesela}_FABDEM_V1-2.tif"
    print(f"DEM: leyendo FABDEM {tesela} desde el zip remoto (solo el recorte) ...")
    # open_rasterio abre perezoso; clip_box recorta por coordenadas; to_raster lee y escribe.
    dem = rxr.open_rasterio(ruta, masked=True)
    dem = dem.rio.clip_box(w - 0.01, s - 0.01, e + 0.01, n + 0.01)
    CACHE.mkdir(parents=True, exist_ok=True)
    dem.rio.to_raster(archivo, compress="deflate")
    return archivo


def interpolador_dem(ruta_dem):
    """Devuelve f(x, y en UTM 18S) → altura, con interpolación bilineal sobre el DEM."""
    dem = rxr.open_rasterio(ruta_dem, masked=True).squeeze("band", drop=True)
    crs_dem = dem.rio.crs
    valores = dem.values.astype("float64")            # aquí se lee el raster
    ys, xs = dem.y.values, dem.x.values
    if ys[0] > ys[-1]:                                  # el interpolador quiere ejes crecientes
        ys, valores = ys[::-1], valores[::-1]
    if np.isnan(valores).any():                         # rellenar huecos con el vecino válido
        from scipy.ndimage import distance_transform_edt
        idx = distance_transform_edt(np.isnan(valores), return_distances=False, return_indices=True)
        valores = valores[tuple(idx)]
    f = RegularGridInterpolator((ys, xs), valores, bounds_error=False, fill_value=np.nan)
    a_dem = Transformer.from_crs(32718, crs_dem, always_xy=True)
    def altura(x, y):
        X, Y = a_dem.transform(x, y)
        return f(np.column_stack([Y, X]))
    return altura


# ----------------------------------------------------------------------------------------------
# 2. Red y corrección de topología
# ----------------------------------------------------------------------------------------------

class UnionFind:
    """Conjuntos disjuntos: para fundir nodos que son el mismo punto."""
    def __init__(self, n):
        self.p = list(range(n))

    def nuevo(self):
        self.p.append(len(self.p))
        return len(self.p) - 1

    def find(self, a):
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra
            return True
        return False

    def raices(self, arr):
        return np.fromiter((self.find(int(a)) for a in arr), dtype=np.int64, count=len(arr))


def _nivel(tags):
    """Nivel vertical de una vía: (layer, es_puente, es_túnel). Solo se conectan vías del mismo nivel."""
    try:
        layer = int(float(str(tags.get("layer", "0")).split(";")[0]))
    except ValueError:
        layer = 0
    puente = tags.get("bridge", "no") not in ("no",)
    tunel = tags.get("tunnel", "no") not in ("no", "building_passage")
    return (layer, puente, tunel)


def _cortar(su, sv, attr, cortes):
    """Parte segmentos en los puntos indicados. cortes: {segmento: [(t, nodo), ...]}."""
    if not cortes:
        return su, sv, attr
    quedan = np.ones(len(su), bool)
    nu, nv, ni = [], [], []
    for s, lista in cortes.items():
        quedan[s] = False
        por_nodo = {}
        for t, nodo in lista:
            por_nodo.setdefault(nodo, t)
        intermedios = [n for n, _ in sorted(por_nodo.items(), key=lambda kv: kv[1])]
        cadena = [int(su[s])] + intermedios + [int(sv[s])]
        for a, b in zip(cadena[:-1], cadena[1:]):
            if a != b:
                nu.append(a); nv.append(b); ni.append(s)
    ni = np.array(ni, dtype=np.int64)
    return (np.concatenate([su[quedan], np.array(nu, dtype=np.int64)]),
            np.concatenate([sv[quedan], np.array(nv, dtype=np.int64)]),
            np.concatenate([attr[quedan], attr[ni]]))


class Red:
    """Red de calles corregida, con alturas, lista para calcular rutas."""

    def __init__(self, osm, ruta_dem, bbox):
        t0 = time.time()
        self.correcciones = []        # (x, y, tipo) para revisar en QGIS
        self.resumen = {}
        self.bbox = bbox
        self._armar(osm, bbox)
        self._corregir()
        self._densificar_y_componentes()
        self._alturas(ruta_dem)
        self._cache_costos = {}
        self._lock = threading.Lock()
        print(f"Red lista en {time.time() - t0:.0f} s: {len(self.xy):,} nodos, {len(self.pu):,} tramos.")
        for k, v in self.resumen.items():
            print(f"   {k}: {v}")

    # --- 2.1 segmentos crudos de OSM -------------------------------------------------------
    def _armar(self, osm, bbox):
        nodos = {el["id"]: (el["lon"], el["lat"]) for el in osm["elements"] if el["type"] == "node"}
        vias = [el for el in osm["elements"] if el["type"] == "way"]
        self.vias = []                # tags de cada vía usada
        self.niveles = {}             # (layer, puente, túnel) → código
        ids = {}
        lon, lat, su, sv, attr = [], [], [], [], []
        descartadas = 0
        for via in vias:
            t = via.get("tags", {})
            hw = t.get("highway", "")
            sin_permiso = (t.get("access") in ("private", "no")
                           and t.get("foot") not in PERMISO and t.get("bicycle") not in PERMISO)
            if hw in EXCLUIR_HIGHWAY or sin_permiso or t.get("area") == "yes" and hw != "pedestrian":
                descartadas += 1
                continue
            nv = _nivel(t)
            cod = self.niveles.setdefault(nv, len(self.niveles))
            iv = len(self.vias)
            self.vias.append({"id": via["id"], "highway": hw, "nombre": t.get("name", "")})
            idx = []
            for nid in via["nodes"]:
                if nid not in nodos:
                    continue
                if nid not in ids:
                    ids[nid] = len(lon)
                    lon.append(nodos[nid][0]); lat.append(nodos[nid][1])
                idx.append(ids[nid])
            for a, b in zip(idx[:-1], idx[1:]):
                if a != b:
                    su.append(a); sv.append(b)
                    attr.append((iv, cod, hw == "steps", nv[1] or nv[2]))
        x, y = A_UTM.transform(np.array(lon), np.array(lat))
        self._xy = [np.column_stack([x, y])]          # se agregan nodos nuevos al final
        self._n = len(lon)
        self.uf = UnionFind(self._n)
        self.su, self.sv = np.array(su, dtype=np.int64), np.array(sv, dtype=np.int64)
        # columnas de attr: vía (-1 = conector), nivel, escalera, elevado (puente o túnel)
        self.attr = np.array(attr, dtype=np.int64)
        self.resumen["vías OSM usadas"] = f"{len(self.vias):,} (descartadas {descartadas:,})"

    def _nuevo_nodo(self, xy):
        self._xy.append(np.asarray(xy, dtype=float).reshape(1, 2))
        self._n += 1
        return self.uf.nuevo()

    def _coords(self):
        if len(self._xy) > 1:
            self._xy = [np.vstack(self._xy)]
        return self._xy[0]

    def _geoms(self):
        xy = self._coords()
        return shapely.linestrings(np.stack([xy[self.su], xy[self.sv]], axis=1))

    # --- 2.2 corrección ----------------------------------------------------------------------
    def _corregir(self):
        xy = self._coords()

        # a. nodos duplicados: puntos distintos en el mismo lugar y del mismo nivel
        nivel_nodo = {}
        for (a, b), cod in zip(zip(self.su, self.sv), self.attr[:, 1]):
            nivel_nodo.setdefault(int(a), set()).add(int(cod))
            nivel_nodo.setdefault(int(b), set()).add(int(cod))
        n_dup = 0
        for a, b in cKDTree(xy).query_pairs(EPS_NODO):
            if nivel_nodo.get(a, set()) & nivel_nodo.get(b, set()) and self.uf.union(a, b):
                n_dup += 1
                self.correcciones.append((*xy[a], "nodo duplicado"))
        self.resumen["a. nodos duplicados fundidos"] = n_dup

        # b. cruces y toques sin nodo común (mismo nivel)
        geoms = self._geoms()
        arbol = shapely.STRtree(geoms)
        i, j = arbol.query(geoms, predicate="intersects")
        m = (i < j) & (self.attr[i, 1] == self.attr[j, 1])
        i, j = i[m], j[m]
        ru, rv = self.uf.raices(self.su), self.uf.raices(self.sv)
        comparten = (ru[i] == ru[j]) | (ru[i] == rv[j]) | (rv[i] == ru[j]) | (rv[i] == rv[j])
        i, j = i[~comparten], j[~comparten]
        inter = shapely.intersection(geoms[i], geoms[j])
        cortes, n_cruce, n_toque = {}, 0, 0

        def ubicar(s, X):
            a, b = xy[self.su[s]], xy[self.sv[s]]
            if np.hypot(*(X - a)) < EPS_NODO:
                return int(self.su[s]), None
            if np.hypot(*(X - b)) < EPS_NODO:
                return int(self.sv[s]), None
            d = b - a
            return None, float(np.dot(X - a, d) / np.dot(d, d))

        for k in range(len(i)):
            for X in shapely.get_coordinates(inter[k]):
                (ni, ti), (nj, tj) = ubicar(i[k], X), ubicar(j[k], X)
                if ni is not None and nj is not None:
                    if self.uf.union(ni, nj):
                        n_toque += 1
                        self.correcciones.append((*X, "extremos que se tocan"))
                elif ni is not None:
                    cortes.setdefault(int(j[k]), []).append((tj, ni)); n_toque += 1
                    self.correcciones.append((*X, "vía que toca a otra sin nodo"))
                elif nj is not None:
                    cortes.setdefault(int(i[k]), []).append((ti, nj)); n_toque += 1
                    self.correcciones.append((*X, "vía que toca a otra sin nodo"))
                else:
                    c = self._nuevo_nodo(X)
                    cortes.setdefault(int(i[k]), []).append((ti, c))
                    cortes.setdefault(int(j[k]), []).append((tj, c))
                    n_cruce += 1
                    self.correcciones.append((*X, "cruce sin nodo"))
        self.su, self.sv, self.attr = _cortar(self.su, self.sv, self.attr, cortes)
        self.resumen["b. cruces sin nodo"] = n_cruce
        self.resumen["b. toques sin nodo"] = n_toque

        # c. vías que terminan muy cerca de otra sin tocarla → conector
        xy = self._coords()
        ru, rv = self.uf.raices(self.su), self.uf.raices(self.sv)
        ok = ru != rv
        grado = np.bincount(np.concatenate([ru[ok], rv[ok]]), minlength=self._n)
        sueltos = np.flatnonzero(grado == 1)
        # segmento al que pertenece cada extremo suelto
        seg_de = np.full(self._n, -1)
        seg_de[ru[ok]] = np.flatnonzero(ok)
        seg_de[rv[ok]] = np.flatnonzero(ok)
        puntos = shapely.points(xy[sueltos])
        geoms = self._geoms()
        p, s = shapely.STRtree(geoms).query(puntos, predicate="dwithin", distance=TOL_CONECTOR)
        d_nodo = sueltos[p]
        m = ((self.attr[s, 1] == self.attr[seg_de[d_nodo], 1])
             & (ru[s] != d_nodo) & (rv[s] != d_nodo))
        p, s = p[m], s[m]
        dist = shapely.distance(puntos[p], geoms[s])
        orden = np.lexsort((dist, p))
        p, s, dist = p[orden], s[orden], dist[orden]
        primero = np.r_[True, p[1:] != p[:-1]]
        cortes, nuevos = {}, []
        for pk, sk in zip(p[primero], s[primero]):
            d = int(sueltos[pk])
            t = float(shapely.line_locate_point(geoms[sk], puntos[pk], normalized=True))
            a, b = xy[self.su[sk]], xy[self.sv[sk]]
            X = a + t * (b - a)
            if np.hypot(*(X - a)) < 0.5:
                destino = int(self.su[sk])
            elif np.hypot(*(X - b)) < 0.5:
                destino = int(self.sv[sk])
            else:
                destino = self._nuevo_nodo(X)
                cortes.setdefault(int(sk), []).append((t, destino))
            at = self.attr[seg_de[d]].copy()
            at[0], at[2] = -1, 0                      # conector, no es escalera
            nuevos.append((d, destino, at))
            self.correcciones.append((*xy[d], "vía cortada antes de llegar (conector)"))
        self.su, self.sv, self.attr = _cortar(self.su, self.sv, self.attr, cortes)
        if nuevos:
            self.su = np.concatenate([self.su, [n[0] for n in nuevos]])
            self.sv = np.concatenate([self.sv, [n[1] for n in nuevos]])
            self.attr = np.vstack([self.attr, [n[2] for n in nuevos]])
        self.resumen["c. conectores agregados (≤ 3 m)"] = len(nuevos)

        # d. tramos de largo ~0 → mismo nodo; lazos fuera
        xy = self._coords()
        ru, rv = self.uf.raices(self.su), self.uf.raices(self.sv)
        largo = np.hypot(*(xy[ru] - xy[rv]).T)
        for a, b in zip(ru[(largo < 0.01) & (ru != rv)], rv[(largo < 0.01) & (ru != rv)]):
            self.uf.union(int(a), int(b))
        ru, rv = self.uf.raices(self.su), self.uf.raices(self.sv)
        ok = ru != rv
        self.resumen["d. lazos y tramos de largo cero quitados"] = int((~ok).sum())
        self.su, self.sv, self.attr = ru[ok], rv[ok], self.attr[ok]

    # --- 2.3 tramos de ≤ 10 m y red conectada -----------------------------------------------
    def _densificar_y_componentes(self):
        xy = self._coords()
        A, B = xy[self.su], xy[self.sv]
        L = np.hypot(*(B - A).T)
        S, N = len(L), len(xy)
        k = np.maximum(1, np.ceil(L / PASO).astype(np.int64))
        n_int = k - 1
        # nodos intermedios de cada segmento
        seg_int = np.repeat(np.arange(S), n_int)
        m_int = np.arange(n_int.sum()) - np.repeat(np.cumsum(n_int) - n_int, n_int) + 1
        xy_int = A[seg_int] + (m_int / k[seg_int])[:, None] * (B - A)[seg_int]
        base = N + np.cumsum(n_int) - n_int
        # tramos
        rep = np.repeat(np.arange(S), k)
        j = np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)
        pu = np.where(j == 0, self.su[rep], base[rep] + j - 1)
        pv = np.where(j == k[rep] - 1, self.sv[rep], base[rep] + j)
        xy = np.vstack([xy, xy_int])
        attr = self.attr[rep]
        self.seg_de_tramo = rep           # segmento corregido de origen (para exportar)
        self._seg_xy = (A, B)

        # quedarse con la red conectada más grande
        usados = np.unique(np.concatenate([pu, pv]))
        nuevo = np.full(len(xy), -1); nuevo[usados] = np.arange(len(usados))
        pu, pv, xy = nuevo[pu], nuevo[pv], xy[usados]
        n = len(xy)
        adj = coo_matrix((np.ones(len(pu)), (pu, pv)), shape=(n, n))
        nc, etiqueta = connected_components(adj, directed=False)
        grande = np.bincount(etiqueta).argmax()
        quedan = etiqueta[pu] == grande
        L_t = np.hypot(*(xy[pv] - xy[pu]).T)
        self.resumen["e. pedazos aislados descartados"] = (
            f"{nc - 1:,} ({L_t[~quedan].sum() / 1000:.1f} km de {L_t.sum() / 1000:.0f} km)")
        pu, pv, attr, self.seg_de_tramo = pu[quedan], pv[quedan], attr[quedan], self.seg_de_tramo[quedan]
        usados = np.unique(np.concatenate([pu, pv]))
        nuevo = np.full(n, -1); nuevo[usados] = np.arange(len(usados))
        self.pu, self.pv, self.xy = nuevo[pu], nuevo[pv], xy[usados]
        self.via, self.esc, self.elev = attr[:, 0], attr[:, 2].astype(bool), attr[:, 3].astype(bool)
        self.L = np.hypot(*(self.xy[self.pv] - self.xy[self.pu]).T)
        n = len(self.xy)
        lon, lat = A_GEO.transform(self.xy[:, 0], self.xy[:, 1])
        self.lonlat = np.column_stack([lon, lat])

        # sin escaleras la red puede partirse: nodos alcanzables desde la parte más grande
        ok = ~self.esc
        adj = coo_matrix((np.ones(ok.sum()), (self.pu[ok], self.pv[ok])), shape=(n, n))
        _, et = connected_components(adj, directed=False)
        tiene = np.zeros(n, bool); tiene[self.pu[ok]] = True; tiene[self.pv[ok]] = True
        grande = np.bincount(et[tiene]).argmax()
        self.arbol = {True: cKDTree(self.xy),
                      False: (lambda idx: (cKDTree(self.xy[idx]), idx))(np.flatnonzero(tiene & (et == grande)))}

    # --- 3. alturas ---------------------------------------------------------------------------
    def _alturas(self, ruta_dem):
        altura = interpolador_dem(ruta_dem)
        z = altura(self.xy[:, 0], self.xy[:, 1])
        n = len(z)
        # resguardo: un nodo fuera del DEM queda sin altura (NaN) y su tramo, con costo NaN, quedaría
        # inservible; se le da la altura del nodo con altura más cercano
        sin_z = np.isnan(z)
        if sin_z.any():
            _, cerca = cKDTree(self.xy[~sin_z]).query(self.xy[sin_z])
            z[sin_z] = z[~sin_z][cerca]
        self.resumen["nodos fuera del DEM (altura del vecino)"] = int(sin_z.sum())
        # puentes y túneles: interpolar desde los extremos (IDW con distancia por la red,
        # que entre dos extremos es exactamente una interpolación lineal)
        inc = np.bincount(self.pu, minlength=n) + np.bincount(self.pv, minlength=n)
        e = self.elev
        inc_e = np.bincount(self.pu[e], minlength=n) + np.bincount(self.pv[e], minlength=n)
        interior = (inc_e == inc) & (inc > 0)
        borde = (inc_e > 0) & (inc_e < inc)
        adj = coo_matrix((self.L[e], (self.pu[e], self.pv[e])), shape=(n, n)).tocsr()
        _, et = connected_components(adj, directed=False)
        n_puentes = 0
        for c in np.unique(et[interior]):
            nodos = np.flatnonzero((et == c) & (inc_e > 0))
            bordes = np.flatnonzero(borde[nodos])
            if len(bordes) == 0:
                continue
            sub = adj[nodos][:, nodos]
            D = dijkstra(sub, directed=False, indices=bordes)
            dentro = interior[nodos]
            with np.errstate(divide="ignore"):
                w = np.where(np.isfinite(D) & (D > 0), 1 / D, 0)
            zb = z[nodos[bordes]][:, None]
            suma = w.sum(axis=0)
            zi = np.where(suma > 0, (w * zb).sum(axis=0) / np.where(suma > 0, suma, 1), np.nan)
            cambiar = dentro & np.isfinite(zi)
            z[nodos[cambiar]] = zi[cambiar]
            n_puentes += 1
        self.resumen["puentes/túneles con altura interpolada"] = n_puentes
        self.z = z
        dz = z[self.pv] - z[self.pu]
        self.g = np.clip(dz / np.maximum(self.L, 0.5), -0.5, 0.5)   # pendiente en sentido u→v

    # --- 4. rutas -------------------------------------------------------------------------------
    def _matriz(self, umbral, fuerza, escaleras, solo_distancia):
        clave = (round(umbral, 4), round(fuerza, 3), escaleras, solo_distancia)
        with self._lock:
            if clave in self._cache_costos:
                return self._cache_costos[clave]
        ok = np.ones(len(self.L), bool) if escaleras else ~self.esc
        L, g = self.L[ok], self.g[ok]
        def costo(gr):
            if solo_distancia:
                return L.copy()
            sube = np.maximum(gr, 0)
            exceso = np.maximum(gr - umbral, 0) * 100
            return L * (1 + A_NAISMITH * sube + fuerza * 0.1 * exceso ** 2)
        filas = np.concatenate([self.pu[ok], self.pv[ok]])
        cols = np.concatenate([self.pv[ok], self.pu[ok]])
        datos = np.concatenate([costo(g), costo(-g)]) + 1e-6
        tramo = np.concatenate([np.flatnonzero(ok)] * 2)
        # aristas paralelas: quedarse con la más barata (csgraph sumaría los duplicados)
        orden = np.lexsort((datos, cols, filas))
        filas, cols, datos, tramo = filas[orden], cols[orden], datos[orden], tramo[orden]
        primero = np.r_[True, (filas[1:] != filas[:-1]) | (cols[1:] != cols[:-1])]
        n = len(self.xy)
        M = coo_matrix((datos[primero], (filas[primero], cols[primero])), shape=(n, n)).tocsr()
        with self._lock:
            if len(self._cache_costos) > 8:
                self._cache_costos.clear()
            self._cache_costos[clave] = M
        return M

    def nodo_cercano(self, lon, lat, escaleras):
        x, y = A_UTM.transform(lon, lat)
        if escaleras:
            d, i = self.arbol[True].query([x, y])
            return int(i), float(d)
        arbol, idx = self.arbol[False]
        d, i = arbol.query([x, y])
        return int(idx[i]), float(d)

    def _camino(self, M, a, b):
        _, pred = dijkstra(M, directed=True, indices=a, return_predecessors=True)
        if pred[b] < 0 and a != b:
            return None
        nodos = [b]
        while nodos[-1] != a:
            nodos.append(int(pred[nodos[-1]]))
        return np.array(nodos[::-1])

    def _describir(self, nodos, umbral, completo=True):
        xy, z = self.xy[nodos], self.z[nodos]
        dL = np.hypot(*np.diff(xy, axis=0).T)
        dz = np.diff(z)
        d = np.r_[0, np.cumsum(dL)]
        g = dz / np.maximum(dL, 0.5)
        # pendiente máxima medida en ventanas de ≥ 30 m (un tramo de 10 m es demasiado ruidoso)
        j = np.searchsorted(d, d + 30)
        v = j < len(d)
        gmax = float(((z[j[v]] - z[v]) / (d[j[v]] - d[v])).max()) if v.any() else float(g.max(initial=0))
        # Tobler (1993): km/h = 6·exp(−3,5·|g + 0,05|)
        vel = 6 * np.exp(-3.5 * np.abs(g + 0.05)) / 3.6
        stats = {
            "distancia_m": round(float(d[-1])),
            "subida_m": round(float(dz[dz > 0].sum()), 1),
            "bajada_m": round(float(-dz[dz < 0].sum()), 1),
            "pend_max_pct": round(100 * gmax, 1),
            "m_sobre_umbral": round(float(dL[g > umbral].sum())),
            "tiempo_pie_min": round(float((dL / vel).sum()) / 60, 1),
        }
        ll = self.lonlat[nodos]
        out = {"coords": [[round(la, 6), round(lo, 6), round(float(h), 1)]
                          for (lo, la), h in zip(ll, z)], "stats": stats}
        if completo:
            out["perfil"] = [[round(float(a), 1), round(float(b), 1)] for a, b in zip(d, z)]
            # tramos en subida sobre el umbral (para pintarlos), unidos cuando son seguidos
            empinados, actual = [], None
            for k in np.flatnonzero(g > umbral):
                if actual and actual["fin"] == k:
                    actual["fin"] = k + 1; actual["g"] = max(actual["g"], g[k])
                else:
                    actual = {"ini": k, "fin": k + 1, "g": g[k]}
                    empinados.append(actual)
            out["empinados"] = [{"coords": [[round(ll[q][1], 6), round(ll[q][0], 6)]
                                            for q in range(e["ini"], e["fin"] + 1)],
                                 "pct": round(100 * float(e["g"]), 1)} for e in empinados]
        return out

    def rutas(self, a_lonlat, b_lonlat, umbral, fuerza, escaleras):
        a, da = self.nodo_cercano(*a_lonlat, escaleras)
        b, db = self.nodo_cercano(*b_lonlat, escaleras)
        if da > 150 or db > 150:
            return {"error": f"Un punto quedó a más de 150 m de la red (A: {da:.0f} m, B: {db:.0f} m)."}
        M = self._matriz(umbral, fuerza, escaleras, False)
        M0 = self._matriz(umbral, fuerza, escaleras, True)
        out = {"snap_m": [round(da), round(db)]}
        for nombre, (o, d) in {"ida": (a, b), "vuelta": (b, a)}.items():
            cam = self._camino(M, o, d)
            corto = self._camino(M0, o, d)
            if cam is None:
                return {"error": "No hay camino entre los dos puntos."}
            out[nombre] = self._describir(cam, umbral)
            out[f"corta_{nombre}"] = self._describir(corto, umbral, completo=False)
        return out

    def calles_empinadas(self, minimo=0.06):
        """Tramos con |pendiente| ≥ 6 %, en tres clases, para la capa de referencia."""
        clases = [(0.06, 0.09, "6–9 %"), (0.09, 0.12, "9–12 %"), (0.12, 9, "> 12 %")]
        feats = []
        ag = np.abs(self.g)
        for lo_, hi, nombre in clases:
            m = (ag >= lo_) & (ag < hi) & (self.L >= 2)
            lineas = [[[round(self.lonlat[u][0], 6), round(self.lonlat[u][1], 6)],
                       [round(self.lonlat[v][0], 6), round(self.lonlat[v][1], 6)]]
                      for u, v in zip(self.pu[m], self.pv[m])]
            feats.append({"type": "Feature", "properties": {"clase": nombre},
                          "geometry": {"type": "MultiLineString", "coordinates": lineas}})
        return {"type": "FeatureCollection", "features": feats}

    def exportar_web(self, carpeta, dem_nombre):
        """Red para la app web (docs/): red.bin con los arreglos y red.json con lo demás.

        red.bin, little-endian, en este orden:
          int32 lat·1e6 [N] | int32 lon·1e6 [N] | float32 z [N] |
          int32 u [E] | int32 v [E] | float32 largo [E] | int32 nombre [E] (−1 sin nombre) |
          uint8 escalera [E] | uint8 nodo sirve sin escaleras [N]
        """
        carpeta.mkdir(parents=True, exist_ok=True)
        nombres, idx_nombre = [], {}
        nom_tramo = np.full(len(self.via), -1, dtype=np.int32)
        for k, v in enumerate(self.via):
            nombre = self.vias[v]["nombre"] if v >= 0 else ""
            if nombre:
                nom_tramo[k] = idx_nombre.setdefault(nombre, len(idx_nombre))
        nombres = sorted(idx_nombre, key=idx_nombre.get)
        sin_esc = np.zeros(len(self.xy), dtype=np.uint8)
        sin_esc[self.arbol[False][1]] = 1
        partes = [np.round(self.lonlat[:, 1] * 1e6).astype("<i4"), np.round(self.lonlat[:, 0] * 1e6).astype("<i4"),
                  self.z.astype("<f4"), self.pu.astype("<i4"), self.pv.astype("<i4"), self.L.astype("<f4"),
                  nom_tramo.astype("<i4"), self.esc.astype(np.uint8), sin_esc]
        datos = b"".join(p.tobytes() for p in partes)
        (carpeta / "red.bin").write_bytes(datos)
        import hashlib
        meta = {"version": hashlib.sha1(datos).hexdigest()[:10], "fecha": time.strftime("%Y-%m-%d"),
                "N": int(len(self.xy)), "E": int(len(self.pu)), "bbox": [float(b) for b in self.bbox],
                "dem": dem_nombre, "resumen": {k: str(v) for k, v in self.resumen.items()},
                "nombres": nombres, "A_naismith": A_NAISMITH}
        (carpeta / "red.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        print(f"Red web en {carpeta}: red.bin {len(datos) / 1e6:.1f} MB, versión {meta['version']}")

    def exportar(self, archivo):
        """Red corregida (tramos de ≤ 10 m con pendiente) y puntos corregidos, para QGIS."""
        import geopandas as gpd
        geom = shapely.linestrings(np.stack([self.xy[self.pu], self.xy[self.pv]], axis=1))
        via = self.via
        tabla = gpd.GeoDataFrame({
            "osm_id": [self.vias[v]["id"] if v >= 0 else -1 for v in via],
            "highway": [self.vias[v]["highway"] if v >= 0 else "conector" for v in via],
            "nombre": [self.vias[v]["nombre"] if v >= 0 else "" for v in via],
            "escalera": self.esc, "puente_tunel": self.elev,
            "largo_m": self.L.round(2), "z_ini": self.z[self.pu].round(2), "z_fin": self.z[self.pv].round(2),
            "pend_pct": (100 * self.g).round(2),
        }, geometry=geom, crs=32718)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        tabla.to_file(archivo, layer="tramos", driver="GPKG")
        if self.correcciones:
            c = np.array([(x, y) for x, y, _ in self.correcciones])
            gpd.GeoDataFrame({"tipo": [t for *_, t in self.correcciones]},
                             geometry=shapely.points(c), crs=32718).to_file(archivo, layer="correcciones", driver="GPKG")
        print(f"Red exportada a {archivo}")


def sellar_version(carpeta=RAIZ / "docs"):
    """Pone en docs/sw.js un hash de todos los archivos de la app: si algo cambió, los teléfonos
    que ya la instalaron bajan la versión nueva (si no, seguirían usando la guardada)."""
    import hashlib
    import re
    h = hashlib.sha1()
    for f in sorted(p for p in carpeta.rglob("*") if p.is_file() and p.name != "sw.js"):
        h.update(f.relative_to(carpeta).as_posix().encode())
        h.update(f.read_bytes())
    sw = carpeta / "sw.js"
    texto = re.sub(r"const VERSION = '[^']*';", f"const VERSION = '{h.hexdigest()[:12]}';",
                   sw.read_text(encoding="utf-8"))
    sw.write_text(texto, encoding="utf-8")
    print(f"sw.js sellado con la versión {h.hexdigest()[:12]}")


# ----------------------------------------------------------------------------------------------
# 5. Mapa interactivo (servidor local + Leaflet)
# ----------------------------------------------------------------------------------------------

PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rutas sin cuestas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root{--bg:#fff;--fg:#1d2329;--muted:#66707a;--line:#d9dee3;--ida:#1f6feb;--vuelta:#e8590c;--corta:#6c757d;--empinado:#d00000}
  html,body{margin:0;height:100%;font:14px/1.4 system-ui,sans-serif;color:var(--fg);background:var(--bg)}
  #mapa{position:absolute;inset:0 360px 0 0}
  #panel{position:absolute;top:0;right:0;bottom:0;width:360px;overflow:auto;padding:14px 16px;box-sizing:border-box;border-left:1px solid var(--line)}
  h1{font-size:17px;margin:0 0 4px} .ayuda{color:var(--muted);font-size:12.5px;margin:0 0 10px}
  label{display:block;margin:8px 0 2px;font-size:13px} input[type=range]{width:100%}
  .fila{display:flex;gap:8px;margin:10px 0} button{flex:1;padding:6px;border:1px solid var(--line);background:#f6f8fa;border-radius:6px;cursor:pointer}
  table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:8px} th,td{padding:3px 4px;border-bottom:1px solid var(--line);text-align:right} th:first-child,td:first-child{text-align:left}
  .chip{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:middle;margin-right:4px}
  svg.perfil{width:100%;height:120px;display:block;margin-top:4px} .tit{font-weight:600;margin-top:12px}
  #estado{margin-top:8px;font-size:12.5px;color:var(--muted)} .error{color:#b00020!important}
  details{margin-top:12px;font-size:12.5px;color:var(--muted)}
  @media (max-width:700px){#mapa{inset:0 0 45% 0}#panel{top:55%;width:auto;left:0;border-left:0;border-top:1px solid var(--line)}}
</style></head><body>
<div id="mapa"></div>
<div id="panel">
  <h1>Rutas sin cuestas · Valdivia</h1>
  <p class="ayuda">Clic 1: inicio (A). Clic 2: destino (B). Arrastra los marcadores para cambiarlos.
  Todas las vías valen en ambos sentidos; solo cuesta subir.</p>
  <label>Pendiente molesta desde: <b id="vu">6</b> %</label>
  <input id="umbral" type="range" min="3" max="12" step="0.5" value="6">
  <label>Rechazo a esas subidas: <b id="vf">2</b></label>
  <input id="fuerza" type="range" min="0" max="10" step="0.5" value="2">
  <label><input id="escaleras" type="checkbox"> permitir escaleras</label>
  <label><input id="capa" type="checkbox"> ver calles empinadas (≥ 6 %)</label>
  <div class="fila"><button id="limpiar">Limpiar</button><button id="gpx">Bajar GPX</button></div>
  <div id="estado">Haz clic en el mapa para poner el inicio.</div>
  <div id="resultado"></div>
  <details><summary>Red y correcciones de topología</summary><div id="info"></div></details>
</div>
<script>
const $ = s => document.querySelector(s);
const mapa = L.map('mapa').setView([-39.8142, -73.2459], 14);
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap'}).addTo(mapa);
const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, attribution: 'Esri'});
L.control.layers({'Calles': osm, 'Satélite': sat}).addTo(mapa);
const capaRutas = L.layerGroup().addTo(mapa);
let capaEmp = null, A = null, B = null, ultimo = null;
const icono = (t, c) => L.divIcon({className: '', iconSize: [26, 26], iconAnchor: [13, 13],
  html: `<div style="width:26px;height:26px;border-radius:50%;background:${c};color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 0 3px #0008">${t}</div>`});

fetch('/info').then(r => r.json()).then(i => {
  $('#info').innerHTML = Object.entries(i.resumen).map(([k, v]) => `${k}: <b>${v}</b>`).join('<br>') + `<br>DEM: ${i.dem}`;
  mapa.fitBounds([[i.bbox[1], i.bbox[0]], [i.bbox[3], i.bbox[2]]]);
  L.rectangle([[i.bbox[1], i.bbox[0]], [i.bbox[3], i.bbox[2]]], {color: '#888', weight: 1, fill: false, dashArray: '4'}).addTo(mapa);
});

mapa.on('click', e => {
  if (!A) { A = L.marker(e.latlng, {draggable: true, icon: icono('A', '#1f6feb')}).addTo(mapa); A.on('dragend', calcular); $('#estado').textContent = 'Ahora el destino (B).'; }
  else if (!B) { B = L.marker(e.latlng, {draggable: true, icon: icono('B', '#e8590c')}).addTo(mapa); B.on('dragend', calcular); calcular(); }
});
for (const id of ['umbral', 'fuerza']) $('#' + id).addEventListener('input', () => { $('#vu').textContent = $('#umbral').value; $('#vf').textContent = $('#fuerza').value; });
for (const id of ['umbral', 'fuerza', 'escaleras']) $('#' + id).addEventListener('change', calcular);
$('#limpiar').onclick = () => { if (A) mapa.removeLayer(A); if (B) mapa.removeLayer(B); A = B = ultimo = null; capaRutas.clearLayers(); $('#resultado').innerHTML = ''; $('#estado').textContent = 'Haz clic en el mapa para poner el inicio.'; };
$('#capa').onchange = async () => {
  if (!$('#capa').checked) { if (capaEmp) mapa.removeLayer(capaEmp); return; }
  if (!capaEmp) {
    const gj = await (await fetch('/empinadas')).json();
    const col = {'6–9 %': '#f4c20d', '9–12 %': '#f08c00', '> 12 %': '#c92a2a'};
    capaEmp = L.geoJSON(gj, {style: f => ({color: col[f.properties.clase], weight: 3, opacity: .85})}).bindTooltip(l => l.feature.properties.clase);
  }
  capaEmp.addTo(mapa); capaRutas.eachLayer(l => l.bringToFront && l.bringToFront());
};

async function calcular() {
  if (!A || !B) return;
  const a = A.getLatLng(), b = B.getLatLng();
  const q = new URLSearchParams({lat1: a.lat, lon1: a.lng, lat2: b.lat, lon2: b.lng,
    umbral: $('#umbral').value, fuerza: $('#fuerza').value, escaleras: $('#escaleras').checked ? 1 : 0});
  $('#estado').className = ''; $('#estado').textContent = 'Calculando…';
  const r = await (await fetch('/ruta?' + q)).json();
  if (r.error) { $('#estado').className = 'error'; $('#estado').textContent = r.error; return; }
  ultimo = r; capaRutas.clearLayers();
  const ll = c => c.map(p => [p[0], p[1]]);
  L.polyline(ll(r.corta_ida.coords), {color: '#6c757d', weight: 3, dashArray: '2 6', opacity: .9}).bindTooltip('más corta ida (sin mirar pendientes)').addTo(capaRutas);
  L.polyline(ll(r.corta_vuelta.coords), {color: '#6c757d', weight: 3, dashArray: '2 6', opacity: .9}).bindTooltip('más corta vuelta (sin mirar pendientes)').addTo(capaRutas);
  L.polyline(ll(r.vuelta.coords), {color: '#e8590c', weight: 7, opacity: .75}).bindTooltip('vuelta B→A').addTo(capaRutas);
  L.polyline(ll(r.ida.coords), {color: '#1f6feb', weight: 4, opacity: .95}).bindTooltip('ida A→B').addTo(capaRutas);
  for (const [k, n] of [['ida', 'ida'], ['vuelta', 'vuelta']])
    for (const e of r[k].empinados) L.polyline(e.coords, {color: '#d00000', weight: 3}).bindTooltip(`subida ${e.pct} % (${n})`).addTo(capaRutas);
  $('#estado').textContent = `Listo. Puntos ajustados a la red: A ${r.snap_m[0]} m, B ${r.snap_m[1]} m.`;
  const fila = (n, c, s, dash) => `<tr><td><span class="chip" style="background:${c};${dash ? 'background:repeating-linear-gradient(90deg,#6c757d 0 2px,transparent 2px 5px)' : ''}"></span>${n}</td><td>${(s.distancia_m / 1000).toFixed(2)}</td><td>${s.subida_m}</td><td>${s.pend_max_pct}</td><td>${s.m_sobre_umbral}</td><td>${s.tiempo_pie_min}</td></tr>`;
  $('#resultado').innerHTML = `<table><tr><th></th><th>km</th><th>sube m</th><th>máx %</th><th>m &gt; umbral</th><th>min a pie</th></tr>
    ${fila('Ida A→B', '#1f6feb', r.ida.stats)}${fila('Vuelta B→A', '#e8590c', r.vuelta.stats)}
    ${fila('Más corta ida', '', r.corta_ida.stats, 1)}${fila('Más corta vuelta', '', r.corta_vuelta.stats, 1)}</table>
    <div class="ayuda" style="margin-top:4px">«máx %»: la subida más empinada medida en 30 m. En rojo, los tramos de la ruta que suben más que el umbral.</div>
    <div class="tit">Perfil de la ida (A→B)</div>${perfil(r.ida.perfil, '#1f6feb')}
    <div class="tit">Perfil de la vuelta (B→A)</div>${perfil(r.vuelta.perfil, '#e8590c')}`;
}

function perfil(p, color) {
  const W = 320, H = 110, m = {l: 32, r: 6, t: 6, b: 18};
  const dmax = p[p.length - 1][0] || 1, zs = p.map(q => q[1]);
  let zmin = Math.min(...zs), zmax = Math.max(...zs); if (zmax - zmin < 10) { const c = (zmax + zmin) / 2; zmin = c - 5; zmax = c + 5; }
  const X = d => m.l + (W - m.l - m.r) * d / dmax, Y = z => m.t + (H - m.t - m.b) * (1 - (z - zmin) / (zmax - zmin));
  const pts = p.map(q => `${X(q[0]).toFixed(1)},${Y(q[1]).toFixed(1)}`).join(' ');
  return `<svg class="perfil" viewBox="0 0 ${W} ${H}"><polyline points="${X(0)},${Y(zmin)} ${pts} ${X(dmax)},${Y(zmin)}" fill="${color}22" stroke="none"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6"/>
    <text x="${m.l - 4}" y="${Y(zmax) + 4}" font-size="10" text-anchor="end" fill="#66707a">${zmax.toFixed(0)} m</text>
    <text x="${m.l - 4}" y="${Y(zmin)}" font-size="10" text-anchor="end" fill="#66707a">${zmin.toFixed(0)} m</text>
    <text x="${W - m.r}" y="${H - 4}" font-size="10" text-anchor="end" fill="#66707a">${(dmax / 1000).toFixed(2)} km</text></svg>`;
}

$('#gpx').onclick = () => {
  if (!ultimo) return;
  const trk = (n, c) => `<trk><name>${n}</name><trkseg>${c.map(p => `<trkpt lat="${p[0]}" lon="${p[1]}"><ele>${p[2]}</ele></trkpt>`).join('')}</trkseg></trk>`;
  const gpx = `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="rutas_pendiente" xmlns="http://www.topografix.com/GPX/1/1">${trk('Ida A-B', ultimo.ida.coords)}${trk('Vuelta B-A', ultimo.vuelta.coords)}</gpx>`;
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([gpx], {type: 'application/gpx+xml'})); a.download = 'ruta_ida_vuelta.gpx'; a.click();
};
</script></body></html>"""


def servidor(red, bbox, dem_nombre, puerto):
    empinadas = json.dumps(red.calles_empinadas()).encode()
    info = json.dumps({"resumen": {k: str(v) for k, v in red.resumen.items()},
                       "bbox": bbox, "dem": dem_nombre}).encode()

    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, cuerpo, tipo="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                return self._enviar(PAGINA.encode(), "text/html")
            if u.path == "/info":
                return self._enviar(info)
            if u.path == "/empinadas":
                return self._enviar(empinadas)
            if u.path == "/ruta":
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                try:
                    r = red.rutas((float(q["lon1"]), float(q["lat1"])), (float(q["lon2"]), float(q["lat2"])),
                                  float(q["umbral"]) / 100, float(q["fuerza"]), q.get("escaleras") == "1")
                except Exception as error:
                    r = {"error": f"Error: {error}"}
                return self._enviar(json.dumps(r).encode())
            self.send_error(404)

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"\nMapa en {url}  (Ctrl+C para cerrar)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        print("Cerrado.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--bbox", type=float, nargs=4, default=BBOX_VALDIVIA,
                    metavar=("OESTE", "SUR", "ESTE", "NORTE"), help="recuadro en grados")
    ap.add_argument("--dem", type=Path, help="DEM propio (GeoTIFF en cualquier CRS) en vez de FABDEM")
    ap.add_argument("--actualizar", action="store_true", help="volver a bajar las calles de OSM")
    ap.add_argument("--exportar", action="store_true", help="guardar la red corregida en salidas/")
    ap.add_argument("--web", action="store_true",
                    help="escribir la red para la app web y el .exe (docs/red.bin y docs/red.json)")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-mapa", action="store_true", help="solo armar la red (para probar)")
    args = ap.parse_args()
    bbox = list(args.bbox)
    osm = bajar_osm(bbox, args.actualizar)
    dem = args.dem or bajar_fabdem(extension_osm(osm, bbox))
    red = Red(osm, dem, bbox)
    dem_nombre = "propio: " + dem.name if args.dem else "FABDEM V1-2 (30 m, sin edificios ni árboles)"
    if args.exportar:
        red.exportar(SALIDAS / "red_corregida.gpkg")
    if args.web:
        red.exportar_web(RAIZ / "docs", dem_nombre)
        sellar_version()
    if not args.sin_mapa:
        servidor(red, bbox, dem_nombre, args.puerto)
    return red


if __name__ == "__main__":
    main()
