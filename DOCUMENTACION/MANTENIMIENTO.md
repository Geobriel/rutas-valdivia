# Mantenimiento · Rutas sin cuestas

Cómo actualizar, cambiar y publicar el proyecto. El [informe](INFORME.md) explica el método; aquí está el
«cómo se hace».

## 0. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Copia de trabajo (con git) | `Dropbox/RUTAS_VALDIVIA/` (notebook Windows; Dropbox la sincroniza al Kubuntu) |
| Repositorio | https://github.com/Geobriel/rutas-valdivia (**público**, rama `main`) |
| App publicada | https://geobriel.github.io/rutas-valdivia/ (GitHub Pages, desde `main` → carpeta `/docs`) |
| `.exe` publicado | [Releases](https://github.com/Geobriel/rutas-valdivia/releases): v1.0 y siguientes |
| Python para el script | `.venv` de SiSCoSu (`Dropbox/SiSCoSu/.venv`), Python 3.14; o uno nuevo con `requirements.txt` |
| Entorno de PyInstaller | `~/rutas_valdivia_build/venv` (fuera de Dropbox, ~50 MB; `crear_exe.py` lo crea si no está) |
| Caché de descargas | `cache/osm_<bbox>.json` (~6 MB) y `cache/fabdem_<extensión>.tif` (~0,7 MB) |
| Red para QGIS | `salidas/red_corregida.gpkg` (~27 MB): capas `tramos` y `correcciones` |
| Datos de git | Commits con el correo **noreply** `10342107+Geobriel@users.noreply.github.com` (configurado solo en este repositorio, para no publicar el correo personal) |

Todos los comandos se corren **desde `Dropbox/RUTAS_VALDIVIA/`**. En Windows, `python` es
`..\SiSCoSu\.venv\Scripts\python.exe`.

---

## 1. Actualizar las calles

Cuando OSM cambia: calles nuevas, correcciones propias en OSM o accesos privados marcados.

```
python rutas_pendiente.py --actualizar --sin-mapa --web --exportar
```

1. `--actualizar` vuelve a bajar las vías de Overpass. Si un servidor da error (502, 504 o tiempo agotado),
   prueba solo los otros tres espejos. Si fallan todos, esperar unos minutos y repetir: pasó el 10-11.
2. Arma y corrige la red. Revisar el resumen que imprime: las cifras deberían parecerse a las del
   [informe](INFORME.md#3-construcción-de-la-red-y-corrección-de-topología). Un salto grande en pedazos
   aislados o en conectores indica un problema en los datos.
3. `--web` reescribe `docs/red.bin` y `docs/red.json` y **sella** `docs/sw.js` con un hash nuevo.
4. `--exportar` deja `salidas/red_corregida.gpkg` para revisar en QGIS las correcciones (capa
   `correcciones`) y las pendientes (campo `pend_pct` de `tramos`).

Para probar antes de publicar, sin opciones abre el mapa de Python en `http://127.0.0.1:8765/`. Para probar
la app web exactamente como quedará:
```
python -m http.server 8767 --directory docs
```
y abrir `http://127.0.0.1:8767/`.

Después, [publicar](#4-publicar).

## 2. Cambiar el DEM o el área

- **Otro DEM**, por ejemplo un LiDAR: `python rutas_pendiente.py --dem ruta/al/dem.tif --sin-mapa --web`.
  Sirve cualquier GeoTIFF de una banda, en cualquier sistema de coordenadas (se transforma solo). Debe
  cubrir toda la red. Si no la cubre, los nodos de afuera toman la altura del vecino más cercano y el
  resumen dice cuántos fueron («nodos fuera del DEM»). Hay que anotar el cambio en el
  [informe](INFORME.md) y en el [historial](HISTORIAL.md).
- **Otra área:** `--bbox OESTE SUR ESTE NORTE`, en grados.
  - Con FABDEM, el área debe caer dentro de una sola tesela de 1° (la de Valdivia va de −74 a −73 de
    longitud y de −40 a −39 de latitud); si no, el script avisa y hay que usar `--dem`.
  - Además hay que cambiar el centro inicial del mapa en `docs/app.js` (`setView([-39.8142, -73.2459], 14)`)
    y los textos que dicen «Valdivia».
  - Un área mucho mayor hace crecer `red.bin`, unos 3,6 MB por cada 1.000 km de vías.
- **Parámetros del modelo:** las constantes están al inicio de `rutas_pendiente.py`: `A_NAISMITH`,
  `PASO`, `EPS_NODO`, `TOL_CONECTOR` y `EXCLUIR_HIGHWAY`.
  - El costo está escrito **dos veces**: `Red._matriz` en Python y `Red.costos` en `docs/ruteo.js`. Si se
    cambia, hay que cambiarlo en los dos y repetir la [verificación](#5-verificar).
  - A la app web, `A` le llega desde `red.json`.

## 3. Rehacer el `.exe`

```
python crear_exe.py
```

Sella `docs/sw.js`, usa PyInstaller del entorno `~/rutas_valdivia_build/venv` y deja
`dist/RutasSinCuestas.exe` (~11,6 MB). Los avisos «Acceso denegado… Retrying» aparecen porque Dropbox o el
antivirus bloquean el archivo un momento; PyInstaller reintenta solo.

Para probarlo sin abrir el navegador: `dist\RutasSinCuestas.exe --sin-navegador` y abrir
`http://127.0.0.1:8766/`. Se cierra con `taskkill /IM RutasSinCuestas.exe /F`.

## 4. Publicar

```
git add -A
git commit -m "Red de calles al 2026-12-01"        # mensaje en español: qué cambió y por qué
git push
gh release create v1.2 dist/RutasSinCuestas.exe --title "Rutas sin cuestas 1.2" --notes "Red de calles al 2026-12-01"
```

- Con el `push`, GitHub Pages publica `docs/` sola en 1–2 minutos (se puede ver en la pestaña *Actions* del
  repositorio).
- Los teléfonos con la app instalada bajan la versión nueva la próxima vez que la abren con internet, porque
  cambió el hash de `sw.js`. Para verla de inmediato: abrir, cerrar del todo y volver a abrir.
- **Siempre sellar antes del commit:** `--web` y `crear_exe.py` lo hacen solos. Si se edita a mano un
  archivo de `docs/` (por ejemplo `app.js`), sellar con:
  ```
  python -c "import rutas_pendiente as r; r.sellar_version()"
  ```
  Si no se sella, los teléfonos siguen usando la versión vieja guardada.
- Como `.git` vive en Dropbox, hacer commit y push desde un solo computador a la vez, con Dropbox en
  «Actualizado».

## 5. Verificar

Después de cambiar el modelo, la red o `ruteo.js`, comparar Python con JavaScript en la misma ruta.

1. En Python:
   ```
   python -c "import rutas_pendiente as r, json; red=r.Red(r.bajar_osm(r.BBOX_VALDIVIA), r.bajar_fabdem(r.extension_osm(r.bajar_osm(r.BBOX_VALDIVIA), r.BBOX_VALDIVIA)), r.BBOX_VALDIVIA); x=red.rutas((-73.2520,-39.8075),(-73.2105,-39.8205),0.06,2,False); print({k: x[k]['stats'] for k in ('ida','vuelta')})"
   ```
2. En JavaScript (Node), con un archivo `prueba.js` fuera de `docs/`:
   ```js
   const fs = require('fs'); const { Red } = require('./docs/ruteo.js');
   const meta = JSON.parse(fs.readFileSync('docs/red.json', 'utf8')); const b = fs.readFileSync('docs/red.bin');
   const red = new Red(meta, b.buffer.slice(b.byteOffset, b.byteOffset + b.length));
   const r = red.rutas([-39.8075, -73.2520], [-39.8205, -73.2105], { umbral: 0.06, fuerza: 2 });
   console.log(r.ida.stats, r.vuelta.stats);
   ```
3. Los dos deben dar lo mismo. Con la red del 10-11-2026: ida 4.930 m, subida 36,0 m, máx 8,1 %; vuelta
   5.132 m, máx 5,1 %.

---

## Arquitectura

Python arma la red; el navegador calcula las rutas. Ver el diagrama en el
[informe, §6](INFORME.md#6-implementación).

| Archivo | Contenido |
|---|---|
| `rutas_pendiente.py` | `bajar_osm`, `extension_osm`, `bajar_fabdem`, `interpolador_dem`; clase `Red`: `_armar` (segmentos de OSM), `_corregir` (topología a–d), `_densificar_y_componentes` (tramos ≤ 10 m y red conectada), `_alturas` (DEM y puentes), `_matriz`/`rutas` (costo y Dijkstra con scipy), `calles_empinadas`, `exportar` (gpkg), `exportar_web`; `sellar_version`; `servidor` (mapa de Python, HTML en `PAGINA`). |
| `docs/ruteo.js` | Clase `Red` en JavaScript: lee `red.bin`; `nodoCercano`, `costos`, `camino` (Dijkstra con `Monticulo`), `describir` (estadísticas, perfil, tramos empinados, calles), `rutas`, `callesEmpinadas`. Funciona en el navegador y en Node. |
| `docs/app.js` | Interfaz: Leaflet, puntos A y B, GPS, controles, tabla, perfiles SVG, GPX, compartir (enlace con `#a=…&b=…&u=…&f=…&e=…`), instalación y registro de `sw.js`. |
| `docs/sw.js` | Service worker: precarga la app y la red (`ARCHIVOS`); teselas OSM y Esri con caché de hasta 3.000. |
| `docs/index.html`, `app.css`, `manifest.webmanifest`, `iconos/` | Página, estilos (diseño de celular bajo 700 px y modo oscuro), manifiesto de la PWA e íconos (192, 512, maskable, apple-touch e `.ico` para el `.exe`). |
| `docs/vendor/leaflet/` | Leaflet 1.9.4, copiado para que funcione sin conexión. |
| `lanzador_exe.py` | Servidor de `docs/` en `127.0.0.1:8766` (u otro puerto libre); abre el navegador salvo con `--sin-navegador`. |
| `crear_exe.py` | Sella y arma el `.exe` con PyInstaller (`--onefile --console`, ícono `docs/iconos/icono.ico`). |

## Formato de la red (`docs/red.bin` + `docs/red.json`)

`red.json`:

| Campo | Contenido |
|---|---|
| `N`, `E` | Nodos y tramos. |
| `bbox` | Recuadro pedido. |
| `version` | Hash de `red.bin`. |
| `fecha` | Fecha en que se armó la red. |
| `dem` | DEM usado. |
| `resumen` | Las correcciones de topología. |
| `nombres` | Nombres de calle únicos. |
| `A_naismith` | Equivalencia de subida. |

`red.bin` (little-endian, sin cabecera), en este orden:

| # | Tipo | Largo | Contenido |
|---|---|---|---|
| 1 | int32 | N | latitud × 10⁶ |
| 2 | int32 | N | longitud × 10⁶ (precisión ~0,1 m) |
| 3 | float32 | N | altura (m) |
| 4 | int32 | E | nodo inicial del tramo |
| 5 | int32 | E | nodo final del tramo |
| 6 | float32 | E | largo horizontal (m) |
| 7 | int32 | E | índice en `nombres` (−1 = sin nombre) |
| 8 | uint8 | E | 1 = escalera |
| 9 | uint8 | N | 1 = el nodo está en la red que queda conectada sin escaleras |

La pendiente no se guarda: `ruteo.js` la calcula al cargar con alturas y largos.

---

## Cosas a saber

- **Licencias:**
  - FABDEM es CC BY-NC-SA 4.0: no comercial, y lo que se derive de él va con la misma licencia.
  - La red derivada de OSM va bajo ODbL, con atribución a «© OpenStreetMap».
  - Las teselas de OSM son para uso moderado; para mucho tráfico habría que usar otro proveedor.
  - Las atribuciones están en la app (panel y esquina del mapa) y en el README.
- **Repositorio público:** el GitHub Pages gratis lo exige. Para hacerlo privado habría que mover la app a
  otro alojamiento (Netlify o Cloudflare Pages, con cuenta propia) o pagar GitHub Pro.
- **Saltos de línea:** `core.autocrlf` está activo en Windows. Git avisa «LF will be replaced by CRLF», lo
  que es normal. `.gitattributes` marca `red.bin` y las imágenes como binarios para que git no los toque.
- **`Error in sys.excepthook`** al terminar `rutas_pendiente.py`: es un aviso de GDAL o rasterio al cerrar
  Python; no afecta los resultados.
- **Puertos:** 8765 es el mapa de Python, 8766 el `.exe` y 8767 el de las pruebas con `http.server`.
- **Mantener el ruteo en un solo modelo:** si se cambian la lógica de las estadísticas o el costo, hay que
  hacerlo en `rutas_pendiente.py` y en `ruteo.js`. Los dos deben dar lo mismo.
