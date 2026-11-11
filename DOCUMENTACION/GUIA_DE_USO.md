# Guía de uso · Rutas sin cuestas

Hay tres formas de usarla. Las tres calculan lo mismo, con la misma red de calles y el mismo modelo.

| Forma | Dónde | Necesita |
|---|---|---|
| **App web** | https://geobriel.github.io/rutas-valdivia/ | Un navegador. Internet la primera vez; después funciona sin conexión. |
| **`RutasSinCuestas.exe`** | [Releases](https://github.com/Geobriel/rutas-valdivia/releases) o `dist/` | Windows. No necesita Python ni internet (salvo el mapa de fondo). |
| **Script de Python** | `rutas_pendiente.py` | Python con las librerías de `requirements.txt` (el `.venv` de SiSCoSu ya las tiene). |

---

## Instalar en el teléfono

La app es una **PWA** (aplicación web instalable): se instala desde el navegador, sin tienda de
aplicaciones, y después se abre desde un ícono como cualquier app, a pantalla completa.

**Android (Chrome)**
1. Abrir https://geobriel.github.io/rutas-valdivia/
2. Menú ⋮ → **Instalar app** (o **Agregar a pantalla principal**). En el panel puede aparecer también un
   botón «Instalar app».

**iPhone o iPad (Safari; en iOS no sirve otro navegador para instalar)**
1. Abrir el enlace en **Safari**.
2. Botón **Compartir** (cuadrado con flecha) → **Agregar a inicio**.

Después de abrirla una vez con internet, la red de calles y la app quedan guardadas en el teléfono: el
cálculo de rutas funciona **sin conexión**. El mapa de fondo solo se ve sin conexión en las zonas que ya
se miraron con internet (se guardan hasta unas 3.000 teselas).

---

## Usar la app

### Poner los puntos
- **Primer toque en el mapa:** inicio (**A**, azul).
- **Segundo toque:** destino (**B**, naranja). La ruta se calcula sola.
- **Toques siguientes:** mueven el destino B.
- Los marcadores se pueden **arrastrar**; al soltarlos se recalcula.
- **📍 Desde aquí:** pone A en tu ubicación (el navegador pide permiso la primera vez).
- **🧭 Seguirme:** muestra tu posición (punto azul con su círculo de precisión) y la va siguiendo. Se
  apaga con el mismo botón.
- **Limpiar:** borra los puntos y las rutas.

Cada punto se ajusta a la calle más cercana; el panel dice a cuántos metros quedó («Puntos ajustados a la
calle: A 3 m, B 23 m»). Si un punto queda a más de 150 m de una calle (por ejemplo, fuera de la ciudad), la
app avisa y no calcula.

### Qué se dibuja
| Línea | Qué es |
|---|---|
| **Azul** | Ida A→B: la ruta óptima. |
| **Naranja** (más ancha, debajo) | Vuelta B→A. Si coincide con la ida, se ve como un borde naranja alrededor de la azul. |
| **Gris punteado** | La ruta más corta sin mirar pendientes, de ida y de vuelta, para comparar. |
| **Rojo** | Tramos de la ida o de la vuelta que, en el sentido de avance, suben más que el umbral. Al pasar el dedo o el mouse dice cuánto. |

Con **«ver calles empinadas (≥ 6 %)»** se pintan todas las calles con pendiente: amarillo 6–9 %, naranjo
9–12 %, rojo más de 12 %. Sirve para revisar si el modelo coincide con lo que uno conoce de la ciudad.
Esta capa no tiene sentido de avance: muestra la pendiente sin importar si se sube o se baja.

### La tabla
| Columna | Significado |
|---|---|
| **km** | Largo de la ruta. |
| **sube m** | Metros de subida acumulada en la ruta. |
| **máx %** | La subida más empinada de la ruta, medida en tramos de 30 m. Medirla en tramos más cortos daría números inflados por el ruido del DEM. |
| **m > umbral** | Metros de la ruta que suben más que la «pendiente molesta». |
| **min a pie** | Tiempo caminando según la función de Tobler: unos 5 km/h en plano, más lento en subida y en bajadas fuertes. |

Filas: **Ida**, **Vuelta**, **Corta ida** y **Corta vuelta** (las grises). Comparar la ida con la corta ida
muestra cuánto se alarga la ruta para evitar cuestas.

Debajo de la tabla, abriendo **Detalles** en el celular, están las calles por las que pasa cada ruta y su
**perfil de altura**. En el perfil, el eje horizontal es la distancia y el vertical la altura sobre el mar.

### Los controles
- **Pendiente molesta desde (3–12 %, por defecto 6 %).** Desde esta pendiente las subidas se castigan
  fuerte. Si una cuesta que te molesta no aparece en rojo, bájala.
- **Rechazo a esas subidas (0–10, por defecto 2).** Cuánto se castiga cada punto de pendiente sobre el
  umbral. Con 0 solo cuenta la subida acumulada, que igual se paga: cada metro subido vale 8 m planos. Con
  10, la ruta da vueltas largas con tal de no subir.
- **Permitir escaleras.** Apagado por defecto. Las escaleras quedan fuera de la red. Si se activan, se
  tratan como cualquier tramo, con la pendiente del DEM.

Los ajustes se recuerdan en ese navegador.

> **Guía rápida de valores.** A pie, el 6 % con rechazo 2 evita las cuestas claras (Aníbal Pinto llegando a
> Beauchef, Vicente Pérez Rosales llegando a Yerbas Buenas) sin alargar demasiado. En bicicleta, o para
> evitar todo lo que se pueda, conviene 4–5 % con rechazo 4–6.

### Guardar y compartir
- **Bajar GPX:** un archivo `ruta_ida_vuelta.gpx` con dos trazas, «Ida A-B» y «Vuelta B-A», con altura.
  Se abre en OsmAnd, Organic Maps, Komoot, Strava, Google Earth o QGIS, para seguirlo con navegación.
- **Compartir ruta:** comparte (o copia) un enlace que abre la app con los mismos puntos y ajustes. La
  dirección del navegador también se actualiza sola con cada ruta, así que se puede guardar como favorito.
  Formato: `…/rutas-valdivia/#a=lat,lon&b=lat,lon&u=6&f=2&e=0`.

---

## Usar el `.exe` (Windows)

1. Bajar `RutasSinCuestas.exe` de [Releases](https://github.com/Geobriel/rutas-valdivia/releases) (o usar
   la copia de `Dropbox/RUTAS_VALDIVIA/dist/`).
2. Doble clic. Se abre una **ventana negra**, que es el servidor local, y la app en el navegador, en
   `http://127.0.0.1:8766/`.
3. Para cerrarla, cerrar la ventana negra.

Windows puede avisar que es un programa no firmado: **Más información → Ejecutar de todas formas**. Si el
puerto 8766 está ocupado, usa otro libre; la dirección aparece en la ventana negra.

---

## Usar el script de Python

Desde `Dropbox/RUTAS_VALDIVIA/`, con el `.venv` de SiSCoSu (Windows):

```
..\SiSCoSu\.venv\Scripts\python.exe rutas_pendiente.py
```

Arma la red (≈ 1 s con la caché) y abre su propio mapa en `http://127.0.0.1:8765/`. Funciona igual que la
app, con menos botones: no tiene GPS ni modo sin conexión. Ctrl+C en la terminal lo cierra.

| Opción | Qué hace |
|---|---|
| *(ninguna)* | Arma la red y abre el mapa. |
| `--actualizar` | Vuelve a bajar las calles de OSM (si no, usa `cache/`). |
| `--exportar` | Guarda `salidas/red_corregida.gpkg` (capas `tramos` y `correcciones`) para QGIS. |
| `--web` | Escribe la red para la app y el `.exe` (`docs/red.bin`, `docs/red.json`) y sella la versión. |
| `--sin-mapa` | No abre el mapa (para solo exportar). |
| `--dem archivo.tif` | Usa otro DEM (cualquier sistema de coordenadas) en vez de FABDEM. |
| `--bbox O S E N` | Otro recuadro, en grados (por defecto −73.31 −39.875 −73.16 −39.765). |
| `--puerto N` | Puerto del mapa (por defecto 8765). |

---

## Problemas frecuentes

| Problema | Causa y solución |
|---|---|
| «Un punto quedó a más de 150 m de la red» | El punto está fuera de la ciudad o lejos de toda calle. La red cubre solo el recuadro punteado gris (Valdivia urbana, Isla Teja, Las Ánimas, Collico, Torobayo). |
| «No hay camino entre los dos puntos» | Con las escaleras desactivadas, algún punto quedó en un sector al que solo se llega por escaleras. Activar «permitir escaleras» o mover el punto. |
| La ruta usa una calle que en la realidad es muy empinada | El DEM de 30 m suaviza las cuestas cortas. Bajar el umbral o subir el rechazo, o mover un punto para forzar otro camino. Ver [limitaciones](INFORME.md#9-limitaciones). |
| La ruta pasa por un lugar privado o cerrado | En OSM no está marcado como privado. Se corrige editando OSM y [actualizando la red](MANTENIMIENTO.md#1-actualizar-las-calles). |
| 📍 no funciona | Falta el permiso de ubicación (en el navegador y, en el teléfono, también en Ajustes → Ubicación). Solo funciona en https o en `127.0.0.1`. |
| No aparece la versión nueva en el teléfono | Abrir la app con internet, cerrarla del todo y volver a abrirla: la primera apertura baja la versión nueva y la segunda la usa. |
| No se ve el mapa de fondo sin conexión | Solo se guardan las zonas ya vistas con internet. Las rutas se calculan igual. |
| En el mapa de Python no se ven las líneas | Pasó el 10-11 por un estilo CSS; está corregido. Si vuelve a pasar, recargar con Ctrl+F5. |
| `Error in sys.excepthook` al terminar el script | Es un aviso de GDAL al cerrar Python; no afecta los resultados (el script termina con código 0). |
