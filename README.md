# Rutas sin cuestas · Valdivia

Ruta de ida y de vuelta entre dos puntos de Valdivia que evita las subidas empinadas. Todas las calles
valen en los dos sentidos, pero subir cuesta y bajar no, así que la ida y la vuelta pueden ir por calles
distintas. Las calles salen de OpenStreetMap, con la topología corregida, y las alturas de FABDEM.

- **App (celular y computador):** https://geobriel.github.io/rutas-valdivia/
  - Android (Chrome): abrir el enlace → menú ⋮ → «Instalar app» (o el botón «Instalar app» del panel).
  - iPhone (Safari): abrir el enlace → Compartir → «Agregar a inicio».
  - Una vez abierta con internet funciona sin conexión: la red y la app quedan guardadas. El mapa de fondo
    guarda solo las zonas que ya se vieron.
- **Windows sin internet ni Python:** `RutasSinCuestas.exe` (en *Releases* del repositorio). Abre la misma
  app en el navegador; para cerrarla, cerrar la ventana negra.

## Uso

Tocar el mapa: primero el inicio (A), después el destino (B); un toque más cambia el destino. 📍 pone A en
tu ubicación y 🧭 muestra dónde estás mientras caminas. «Pendiente molesta desde» y «Rechazo» regulan cuánto
se desvía la ruta para no subir. «Bajar GPX» guarda la ida y la vuelta para otras apps (OsmAnd, Organic Maps).
«Compartir ruta» da un enlace que abre esa misma ruta.

## Archivos

| Archivo | Qué hace |
|---|---|
| `rutas_pendiente.py` | Baja las calles de OSM (Overpass) y FABDEM, corrige la topología, pone las alturas y calcula las rutas. Con `--web` escribe la red para la app; sin opciones abre su propio mapa (servidor local en Python). |
| `docs/` | La app web que publica GitHub Pages: `index.html`, `app.js` (interfaz), `ruteo.js` (el mismo cálculo de rutas, en JavaScript), `red.bin` + `red.json` (la red), `sw.js` (modo sin conexión). |
| `lanzador_exe.py` | Lo que corre dentro del `.exe`: sirve `docs/` en `127.0.0.1` y la abre en el navegador. |
| `crear_exe.py` | Arma `dist/RutasSinCuestas.exe` con PyInstaller (en un entorno aparte, `~/rutas_valdivia_build`). |

`cache/` (OSM y DEM bajados), `salidas/` (`red_corregida.gpkg` para revisar en QGIS, con `--exportar`) y
`dist/` (el `.exe`) no van en git.

## Actualizar las calles

```
python rutas_pendiente.py --actualizar --sin-mapa --web --exportar
python crear_exe.py
```

Después: commit + push de `docs/` (GitHub Pages se actualiza solo en uno o dos minutos y los teléfonos
bajan la versión nueva al abrir la app con internet) y subir el `.exe` nuevo a *Releases*.

## Método

1. **Calles:** todas las vías `highway=*` del recuadro, salvo las que no se pueden recorrer (en
   construcción o proyectadas, autopistas, acceso privado sin permiso a pie o en bicicleta). Las
   escaleras son opcionales.
2. **Topología:**
   - se funden los nodos duplicados;
   - se agrega un nodo donde dos vías del mismo nivel se cruzan o se tocan sin nodo común;
   - se unen con un conector las vías que terminan a menos de 3 m de otra;
   - se quitan los lazos;
   - se deja solo la red conectada más grande.

   Los puentes y túneles no se conectan con lo que pasa por debajo o por encima.
3. **Alturas:** FABDEM V1-2, 30 m, interpolado en nodos cada ≤ 10 m. En puentes y túneles la altura se
   interpola entre sus extremos.
4. **Costo de un tramo** de largo *L* con pendiente *g* en el sentido de avance:
   `L · (1 + 8·max(g,0) + F·0,1·(100·max(g − umbral, 0))²)`. Cada metro subido equivale a 8 m planos
   (regla de Naismith). Las subidas sobre el umbral se castigan además con fuerza *F*. Ruta de menor costo
   con Dijkstra; tiempo a pie con Tobler.

Con 30 m de resolución, las cuestas muy cortas pueden salir algo más suaves de lo que son. Con un DEM mejor
(p. ej., un LiDAR): `python rutas_pendiente.py --dem archivo.tif --web`.

## Referencias y licencias de los datos

- Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022). A 30 m global map of
  elevation with forests and buildings removed. *Environmental Research Letters, 17*(2), 024016.
  https://doi.org/10.1088/1748-9326/ac4d4f. Licencia CC BY-NC-SA 4.0: uso no comercial.
- Scarf, P. (2007). Route choice in mountain navigation, Naismith's rule, and the equivalence of distance
  and climb. *Journal of Sports Sciences, 25*(6), 719–726. https://doi.org/10.1080/02640410600874906
- Tobler, W. (1993). *Three presentations on geographical analysis and modeling* (Technical Report 93-1).
  NCGIA, University of California, Santa Barbara.
- Calles © colaboradores de OpenStreetMap. La red derivada (`docs/red.bin`) se ofrece bajo la
  [ODbL](https://opendatacommons.org/licenses/odbl/).
- Mapas de fondo: OpenStreetMap y Esri World Imagery. Mapa interactivo:
  [Leaflet](https://leafletjs.com) 1.9.4 (BSD-2).
