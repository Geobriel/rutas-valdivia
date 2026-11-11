# Rutas sin cuestas · Valdivia

Calcula la ruta de **ida y de vuelta** entre dos puntos de Valdivia evitando las **subidas empinadas**.
Todas las calles y caminos valen en los dos sentidos (se ignora el sentido del tránsito), pero subir cuesta
y bajar no, así que la ida y la vuelta pueden ir por calles distintas. Las calles salen de OpenStreetMap,
con la topología corregida, y las alturas de FABDEM, un modelo de terreno de 30 m sin edificios ni árboles.

| | |
|---|---|
| **App (celular y computador)** | https://geobriel.github.io/rutas-valdivia/ |
| **Programa para Windows** | `RutasSinCuestas.exe` en [Releases](https://github.com/Geobriel/rutas-valdivia/releases) |
| **Código** | https://github.com/Geobriel/rutas-valdivia (copia de trabajo en `Dropbox/RUTAS_VALDIVIA/`) |
| **Versión** | 1.1 · red de calles del 2026-11-10 ([historial](DOCUMENTACION/HISTORIAL.md)) |

## En 30 segundos

1. Abrir la app (en el teléfono: instalarla, ver la [guía](DOCUMENTACION/GUIA_DE_USO.md#instalar-en-el-teléfono)).
2. Tocar el mapa: primero el inicio **A**, después el destino **B**. 📍 pone A en tu ubicación.
3. Azul: ida A→B. Naranja: vuelta B→A. Gris punteado: la más corta sin mirar pendientes. Rojo: tramos de la
   ruta que suben más que el umbral.
4. «Pendiente molesta desde» y «Rechazo» regulan cuánto se desvía la ruta para no subir.

## Documentación

| Documento | Para qué |
|---|---|
| [GUIA_DE_USO.md](DOCUMENTACION/GUIA_DE_USO.md) | Usar la app, el `.exe` y el script; qué significa cada número; problemas frecuentes. |
| [INFORME.md](DOCUMENTACION/INFORME.md) | Informe técnico: datos, corrección de topología, alturas, modelo de costo, validación, resultados y limitaciones. |
| [MANTENIMIENTO.md](DOCUMENTACION/MANTENIMIENTO.md) | Actualizar las calles, cambiar el DEM o el área, rehacer el `.exe`, publicar; arquitectura y formato de la red. |
| [HISTORIAL.md](DOCUMENTACION/HISTORIAL.md) | Cómo se construyó (10-11-2026), problemas encontrados, decisiones y versiones. |
| [CLAUDE.md](CLAUDE.md) | Contexto para retomar el proyecto con Claude Code. |

## Archivos

```
RUTAS_VALDIVIA/
├── rutas_pendiente.py     calles OSM + DEM → red corregida con alturas; rutas; mapa propio (Python)
├── lanzador_exe.py        lo que corre dentro del .exe (sirve docs/ en 127.0.0.1)
├── crear_exe.py           arma dist/RutasSinCuestas.exe con PyInstaller
├── requirements.txt       librerías de Python (versiones probadas)
├── docs/                  la app web que publica GitHub Pages (index.html, app.js, ruteo.js, red.bin…)
├── DOCUMENTACION/         guía de uso, informe, mantenimiento e historial
├── cache/                 OSM y DEM bajados                      (no va en git)
├── salidas/               red_corregida.gpkg para QGIS           (no va en git)
└── dist/                  RutasSinCuestas.exe                     (no va en git; va en Releases)
```

## Actualizar (resumen)

```
python rutas_pendiente.py --actualizar --sin-mapa --web --exportar
python crear_exe.py
git add -A && git commit -m "Red de calles al <fecha>" && git push
gh release create v<n> dist/RutasSinCuestas.exe --title "Rutas sin cuestas <n>" --notes "Red de calles al <fecha>"
```

Detalle en [MANTENIMIENTO.md](DOCUMENTACION/MANTENIMIENTO.md).

## Datos y licencias

Calles © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright). La red derivada
(`docs/red.bin`) se ofrece bajo la [ODbL](https://opendatacommons.org/licenses/odbl/). Alturas: FABDEM V1-2
(Hawker et al., 2022), licencia **CC BY-NC-SA 4.0**, que **no permite uso comercial**. Mapas de fondo:
OpenStreetMap y Esri World Imagery. Mapa interactivo: [Leaflet](https://leafletjs.com) 1.9.4 (BSD-2).
Las referencias completas están en el [informe](DOCUMENTACION/INFORME.md#referencias).
