# Historial · Rutas sin cuestas

## Versiones

| Versión | Fecha | Cambios |
|---|---|---|
| **1.1** | 10-11-2026 (tarde) | **Corrección:** 2.861 nodos (22 km de vías de las afueras) no tenían altura y sus tramos funcionaban como cerrados. El DEM ahora se recorta a la extensión de todos los nodos (`extension_osm`) y, como resguardo, un nodo sin altura toma la del vecino más cercano. Las rutas dentro de la ciudad no cambian. Documentación completa (`DOCUMENTACION/`, `CLAUDE.md`, `requirements.txt`). |
| 1.0 | 10-11-2026 (mañana) | Primera versión: script de Python con mapa propio, app web instalable (PWA) en GitHub Pages y `RutasSinCuestas.exe`. |

---

## Bitácora del 10-11-2026

Todo se hizo en una sesión con Claude Code, en el notebook de Windows.

### 1. Pedido inicial
El usuario pidió un script con estas características:
- elegir inicio y fin en un mapa interactivo;
- calcular la ruta más corta con las calles de OSM y un DEM, el de mejor resolución disponible, evitando
  subidas pronunciadas;
- dio como ejemplos Aníbal Pinto llegando a Beauchef, Vicente Pérez Rosales llegando a Yerbas Buenas y
  Baquedano entre Clemente Escobar y Aníbal Pinto;
- calcular la ruta de ida y la de vuelta, con todas las calles válidas en todas las direcciones;
- corregir bien la topología.

### 2. Elección del DEM
- Se buscó un LiDAR público de Valdivia (IDE Chile, repositorios académicos): **no se encontró**. Durante
  la sesión el usuario creyó que se había bajado un LiDAR; se aclaró que **no**: el DEM es FABDEM, un
  modelo global derivado de radar.
- Se eligió **FABDEM V1-2** en vez del Copernicus GLO-30 que usa SiSCoSu (en `DATOS/estaticos/`), porque
  FABDEM no tiene edificios ni árboles.
- El repositorio de Bristol entrega zips de 10° × 10°; el de Valdivia pesa 668 MB. Se comprobó que GDAL
  lee la tesela `S40W074` dentro del zip remoto (`/vsizip//vsicurl/`) sin bajarlo entero: el recorte pesa
  0,7 MB.

### 3. Script y red
- No se usó OSMnx (no estaba instalado); la red se arma desde los datos crudos de Overpass, lo que da
  control total sobre la topología.
- El primer intento de bajar OSM falló: los dos servidores Overpass configurados dieron **502 Bad Gateway**
  durante unos 4 minutos. Se agregaron dos espejos más (`overpass.private.coffee`, `maps.mail.ru`); al
  reintentar respondían todos.
- Red: 7.102 vías usadas y 915 descartadas (acceso privado y otras); 6 nodos duplicados, 2 cruces sin
  nodo, 59 conectores y 43 pedazos aislados (7,9 km). La red se arma en 1 s.
- **Validación con los ejemplos del usuario:** Aníbal Pinto llegando a Beauchef da 11,8 %, Vicente Pérez
  Rosales llegando a Yerbas Buenas 12,4 % y Baquedano 7,9 %. Las tres superan el umbral por defecto de 6 %.
  - Con «Bouchef» no se encontró ninguna calle: en OSM se llama **Beauchef**.

### 4. «No veo la ruta»
En el mapa de Python las rutas se calculaban (salían la tabla y los perfiles) pero no se dibujaban.
- **Causa:** la regla CSS `svg { height: 120px }`, pensada para los perfiles, también se aplicaba al SVG
  donde Leaflet dibuja las líneas y lo recortaba.
- **Solución:** limitarla a `svg.perfil`.

### 5. `.exe` y apps
El usuario preguntó si se podían hacer un `.exe` y apps para Android e iOS. Se propuso:
- pasar el ruteo a JavaScript (la red pesa 3,6 MB y Dijkstra tarda menos de 100 ms);
- una **PWA** para Android e iOS;
- un `.exe` con PyInstaller.

Se descartaron el APK (no lo quiso el usuario) e iOS nativo (pide un Mac y la cuenta de desarrollador de
Apple). El usuario dio «libertad total» y salió. Se hizo lo siguiente:
- `rutas_pendiente.py --web` → `docs/red.bin` + `red.json`;
- `docs/ruteo.js`: el mismo modelo en JavaScript; en Node dio **exactamente** los mismos números que
  Python;
- `docs/app.js` + `index.html` + `app.css`: la interfaz, con GPS (📍 y 🧭), calles recorridas, GPX, enlace
  para compartir, instalación y diseño de celular;
- `docs/sw.js` + `manifest.webmanifest` + íconos (dibujados con PIL: un cerro y una ruta que lo rodea): el
  modo sin conexión. Leaflet se copió a `docs/vendor/`. Se comprobó que los servidores de teselas de OSM y
  Esri permiten CORS, necesario para guardarlas;
- capturas con Edge sin ventana para revisar el diseño. Hubo que corregir la tabla, que se salía del panel,
  y el encuadre inicial en el celular. Edge sin ventana no baja de unos 500 px de ancho: para el diseño de
  celular se probó con 520 px;
- `.exe`: PyInstaller 6.22.3 en un entorno aparte (`~/rutas_valdivia_build/venv`), 11,6 MB, probado con
  `--sin-navegador`;
- publicación: repositorio **público** `Geobriel/rutas-valdivia` (commits con el correo noreply de
  GitHub), GitHub Pages desde `main:/docs` y el release v1.0 con el `.exe`. Se verificó la app publicada.

### 6. Documentación y corrección 1.1
Al juntar las cifras para el informe, la distribución de pendientes sumaba 973 km y no 995 km.
- **Causa:** Overpass entrega las vías completas aunque se salgan del recuadro, pero el DEM se había
  recortado al recuadro más 0,01°. 2.861 nodos quedaron sin altura (NaN). En la app, un costo NaN equivale
  a un tramo cerrado. Estaban todos en las afueras, así que las rutas de prueba no cambiaron.
- **Solución:** recortar el DEM a la extensión de todos los nodos (`extension_osm`) y rellenar con el vecino
  más cercano como resguardo. Resultado: 0 nodos sin altura y la red completa con pendiente.
- En la misma revisión se corrigió el informe en dos puntos:
  - el 7,92 m por metro subido es lo que da la propia regla de Naismith, no una estimación de Scarf (2007);
  - la nota original de Naismith (1892) no se consultó.
- Se escribieron README, guía de uso, informe, mantenimiento, este historial, `CLAUDE.md` y
  `requirements.txt`, y se publicó la versión 1.1.

---

## Pendientes e ideas

- Calibrar el umbral con pendientes medidas en terreno en 5–10 cuestas conocidas.
- Buscar un LiDAR de Valdivia (MINVU, SERVIU, GORE Los Ríos, UACh) y usarlo con `--dem`.
- Modo bicicleta: tiempo según potencia, castigo a bajadas muy fuertes y opción de respetar los sentidos
  únicos.
- Actualización mensual de OSM con una GitHub Action.
- Revisar en QGIS las 59 uniones con conector (`salidas/red_corregida.gpkg`, capa `correcciones`).
