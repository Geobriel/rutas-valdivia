# Informe técnico · Rutas sin cuestas · Valdivia

**Versión 1.1 · 10-11-2026 · red de calles OSM del 10-11-2026**
Autor del proyecto: Gabriel (cuenta de GitHub `Geobriel`). Código y documentación escritos con Claude Code.

---

## Resumen

Se construyó una herramienta que calcula, para dos puntos de Valdivia, la ruta óptima de **ida** y la de
**vuelta** evitando las subidas empinadas. La red de calles sale de OpenStreetMap: 995 km de vías de todo
tipo, con la topología revisada y corregida. Las alturas salen de FABDEM, un modelo de terreno de 30 m sin
edificios ni árboles.

Cada tramo tiene un costo que depende del sentido de avance:
- cada metro subido vale 8 m planos (regla de Naismith);
- las subidas sobre un umbral elegido por el usuario (6 % por defecto) se castigan además en forma
  cuadrática;
- bajar no se castiga.

Como todas las vías se pueden recorrer en los dos sentidos pero el costo es asimétrico, la ida y la vuelta
pueden ir por calles distintas.

La herramienta existe en tres formas con resultados idénticos (verificados):
- un script de Python, que además arma la red;
- una app web instalable (PWA) que calcula en el teléfono, sin servidor y sin conexión;
- un `.exe` para Windows.

Las tres calles que el usuario dio como ejemplo de cuestas molestas aparecen en la red con pendientes de
8 a 12 %, y la ruta las evita con los valores por defecto.

---

## 1. Objetivo

Lo que pidió el usuario el 10-11-2026:
- elegir inicio y fin en un mapa interactivo;
- calcular la ruta más corta sobre las calles de OSM considerando la pendiente de un DEM, el de mejor
  resolución disponible, sin pasar por subidas pronunciadas;
- calcular la ruta de ida y la de vuelta, con todas las calles válidas en todas las direcciones;
- corregir la topología para que la red quede bien.

Ejemplos de cuestas a evitar que dio el usuario:
- Aníbal Pinto llegando a Beauchef;
- Vicente Pérez Rosales llegando a Yerbas Buenas;
- Baquedano entre Clemente Escobar y Aníbal Pinto.

Después pidió un `.exe` y apps para Android e iOS, sin APK.

---

## 2. Área y datos

### 2.1 Área
Recuadro de −73,31 a −73,16 de longitud y de −39,875 a −39,765 de latitud (unos 13 × 12 km). Cubre la
ciudad de Valdivia, Isla Teja, Las Ánimas, Collico, Guacamayo y Torobayo. Las vías que salen del recuadro se
conservan completas.

### 2.2 Calles: OpenStreetMap
Se usan todas las vías `highway=*` del recuadro, bajadas de la API Overpass (consulta
`way["highway"](bbox); (._;>;); out body;`) el 10-11-2026: **8.017 vías**.

Se descartan **915** que no se pueden recorrer:

| Motivo | Vías |
|---|---|
| `access=private` o `no`, sin `foot` ni `bicycle` = yes/designated/permissive/destination | 874 (524 `service`, 101 `living_street`, 86 `track`, 59 `residential`, 57 `footway`, 19 `path` y otras) |
| `highway=construction` / `proposed` | 23 |
| `highway=corridor` (pasillos interiores) | 16 |
| `raceway`, `area=yes` (salvo `pedestrian`) | 2 |

Las autopistas (`motorway`) también se excluyen, pero no hay en el área. Las **escaleras**
(`highway=steps`, 0,7 km) quedan en la red y se pueden activar o desactivar.

Red resultante, ya corregida: **995 km**. Por tipo de vía:

| Tipo | km | Tipo | km |
|---|---|---|---|
| residential | 276,0 | service | 60,5 |
| footway | 149,8 | unclassified | 45,0 |
| living_street | 93,4 | cycleway | 35,6 |
| tertiary | 88,6 | path | 32,6 |
| secondary | 71,6 | primary | 32,5 |
| track | 70,1 | trunk | 26,0 |

### 2.3 Alturas: FABDEM
Se buscó el DEM de mejor resolución disponible para Valdivia. **No se encontró un LiDAR público** de la
ciudad: no apareció en IDE Chile ni en repositorios académicos (búsqueda del 10-11-2026). Entre los DEM
globales se eligió **FABDEM V1-2** (Hawker et al., 2022), por estas razones:
- Es el Copernicus GLO-30 (resolución de 1″, unos 30 × 24 m en Valdivia) **con los edificios y los árboles
  quitados**. Para pendientes de calles importa: un modelo de superficie, como el Copernicus original que
  usa SiSCoSu, pone los techos y las copas de los árboles en el perfil de la calle.
- Está validado a escala global y publicado en *Environmental Research Letters*.

Cómo se lee: se baja solo la tesela `S40W074` desde el zip de 668 MB del repositorio de la Universidad de
Bristol, sin bajar el zip entero, gracias a la lectura remota de GDAL (`/vsizip//vsicurl/…`). Se recorta a
la extensión de todos los nodos de la red y se guarda en `cache/`, en unos 0,7 MB. Licencia: CC BY-NC-SA
4.0, no comercial.

---

## 3. Construcción de la red y corrección de topología

La red se arma **sin simplificar**: cada nodo de OSM es un nodo del grafo y cada par de nodos consecutivos
de una vía es un segmento recto. Todo se calcula en UTM 18 Sur (EPSG:32718).

Cada vía tiene un **nivel** vertical: (`layer`, es puente, es túnel). `tunnel=building_passage` cuenta como
nivel del suelo. **Solo se conectan vías del mismo nivel**, para no unir un puente con la calle que pasa
por debajo.

| Paso | Regla | Correcciones |
|---|---|---|
| a. Nodos duplicados | Dos nodos a menos de 0,2 m, usados por vías del mismo nivel, se funden. | 6 |
| b. Cruces sin nodo | Dos segmentos del mismo nivel que se cruzan sin nodo común (árbol espacial STRtree de shapely): se agrega el nodo de cruce a los dos. | 2 |
| b. Toques sin nodo | Un extremo que cae sobre otro segmento sin ser nodo suyo: se corta ese segmento en ese punto. Si las dos vías se superponen, se cortan en los extremos de la superposición. | 0 |
| c. Vías cortadas antes de llegar | Un extremo suelto (nodo de grado 1) a menos de **3 m** de otra vía del mismo nivel, sin tocarla: se proyecta sobre el segmento más cercano, se corta ahí y se agrega un **conector**. Es el error de dibujo más común en OSM. | 59 |
| d. Lazos y tramos de largo cero | Se eliminan. | 6 |
| e. Pedazos aislados | Se conserva solo la red conectada más grande; el resto no se puede alcanzar desde la ciudad. | 43 pedazos, 7,9 km de 1.003 km |

Los puntos corregidos quedan en la capa `correcciones` de `salidas/red_corregida.gpkg`, con su tipo, para
revisarlos en QGIS.

**Lo que no se hace, y por qué:**
- No se consolidan intersecciones complejas (como `consolidate_intersections` de OSMnx): para caminar
  importan las veredas y cruces tal como están dibujados, y fundirlos deforma la red.
- No se cierran huecos de más de 3 m: podrían ser reales, como una reja o un cerco.

Por último, cada segmento se divide en **tramos de 10 m como máximo**, agregando nodos intermedios. Así la
pendiente es local y no un promedio de toda la cuadra, y los puntos tocados en el mapa se ajustan a menos
de unos 5 m de la calle.

**Red final: 117.409 nodos y 122.342 tramos.**

---

## 4. Alturas de la red

- **Interpolación bilineal** del DEM en cada nodo, sobre la grilla original de FABDEM en grados, sin
  reproyectar el raster.
- **Puentes y túneles:** el DEM da la altura del agua o del cerro, no la del tablero. Para cada grupo
  conectado de tramos de puente o túnel, la altura de sus nodos interiores se interpola desde sus extremos.
  Se usa un promedio ponderado por la inversa de la distancia medida por la red: con dos extremos, eso es
  exactamente una interpolación lineal. Se corrigieron **28** grupos de puente o túnel (4,4 km), entre
  ellos los puentes Calle Calle, Pedro de Valdivia, Cau Cau, Santa Elvira y Río Cruces, el embarcadero
  Matta y las pasarelas de un sendero interpretativo.
- **Resguardo:** un nodo fuera del DEM recibe la altura del nodo con altura más cercano. Con el recorte
  actual no hay ninguno; en la versión 1.0 había 2.861, ver [HISTORIAL](HISTORIAL.md).
- **Pendiente** de cada tramo: g = (z_fin − z_ini) / largo, en el sentido ini→fin, acotada a ±50 %.

Pendiente de la red (en valor absoluto, por largo):

| Pendiente | km | % de la red |
|---|---|---|
| 0–3 % | 794,7 | 79,8 |
| 3–6 % | 78,9 | 7,9 |
| 6–9 % | 39,5 | 4,0 |
| 9–12 % | 24,9 | 2,5 |
| > 12 % | 57,4 | 5,8 |

Casi todo lo que pasa de 12 % son senderos y huellas de los cerros de las afueras. La altura de la red va
de 0 a 343 m.

---

## 5. Modelo de costo

Costo de recorrer un tramo de largo *L* (metros) con pendiente *g* en el sentido de avance (*g* > 0 =
subida):

```
costo = L · ( 1 + A·max(g, 0) + F · 0,1 · (100 · max(g − u, 0))² )
```

- **A = 8: equivalencia de subida.** Cada metro subido cuesta como 8 m planos. Es la regla de Naismith
  (1892): 1 h por cada 3 millas más 1 h por cada 2.000 pies de subida, es decir 15.840 / 2.000 = 7,92 m
  planos por metro subido. Scarf (2007) analiza esta regla como equivalencia entre distancia y subida para
  elegir rutas.
- **u: umbral de pendiente molesta.** Por defecto 6 %, ajustable de 3 a 12 %.
- **F: rechazo.** Por defecto 2, ajustable de 0 a 10. Castiga en forma cuadrática cada punto de pendiente
  sobre el umbral. Este término es una **elección de diseño propia**, no sale de la literatura: está hecho
  para que las cuestas sobre el umbral se eviten salvo que el desvío sea muy largo.
- **Bajar no se castiga.**

Multiplicador del largo con los valores por defecto (u = 6 %, F = 2):

| Pendiente en subida | 0 % | 3 % | 6 % | 8 % | 10 % | 12 % | 15 % |
|---|---|---|---|---|---|---|---|
| costo / largo | 1,00 | 1,24 | 1,48 | 2,44 | 5,00 | 9,16 | 18,4 |

Ejemplo: 100 m subiendo al 10 % «cuestan» como 500 m planos. La ruta prefiere un desvío de hasta 400 m
antes que tomarlos.

**Ruta óptima:** algoritmo de Dijkstra sobre el grafo dirigido. Cada tramo genera dos aristas, ida y
vuelta, cada una con su costo. Si hay aristas paralelas, se usa la más barata. La ruta de comparación
(«más corta») usa costo = largo.

**Puntos A y B:** se ajustan al nodo de la red más cercano, como máximo a 150 m. Sin escaleras, se ajustan
solo a nodos de la parte de la red que queda conectada sin ellas.

**Estadísticas de cada ruta:**
- largo, subida y bajada acumuladas;
- pendiente máxima de subida, medida en ventanas de 30 m de recorrido para no reportar el ruido del DEM;
- metros que suben más que el umbral;
- tiempo a pie con la función de Tobler (1993): v = 6·exp(−3,5·|g + 0,05|) km/h.

---

## 6. Implementación

```
                       ┌────────────────────────── rutas_pendiente.py (Python) ──────────────────────────┐
 Overpass (OSM) ──────►│ red sin simplificar → corrección de topología → tramos ≤ 10 m → red conectada    │
 FABDEM (zip remoto) ─►│ alturas (bilineal; puentes interpolados) → pendientes                           │
                       │   ├─ mapa propio: servidor local + Leaflet (rutas calculadas en Python, scipy)    │
                       │   ├─ --exportar → salidas/red_corregida.gpkg (QGIS)                              │
                       │   └─ --web → docs/red.bin + red.json (3,6 MB) y sella docs/sw.js                 │
                       └──────────────────────────────────────────────────────────────────────────────────┘
                                                          │
                     docs/ (app web): ruteo.js (mismo modelo en JavaScript) + app.js (interfaz, GPS) + Leaflet
                         ├─ GitHub Pages → https://geobriel.github.io/rutas-valdivia/  (PWA, sin conexión)
                         └─ crear_exe.py → RutasSinCuestas.exe (lanzador_exe.py sirve docs/ en 127.0.0.1)
```

- **Python:** numpy, scipy (árbol KD, grafos dispersos `csgraph` con Dijkstra y componentes conexas),
  shapely 2 (STRtree, intersecciones), pyproj, rioxarray (lectura y recorte del DEM) y requests.
- **JavaScript:** `ruteo.js` lee `red.bin` en arreglos tipados y arma la lista de vecinos de cada nodo.
  Usa una grilla de 50 m para encontrar el nodo más cercano y un montículo binario para Dijkstra, y deja
  de buscar al llegar al destino. Repite exactamente el modelo de costo y las estadísticas de Python.
- **Verificación:** para Isla Teja → Collico, Python y JavaScript dan los **mismos** números en las 4 rutas.
  Ida: 4.930 m, 36,0 m de subida, 8,1 % de máximo, 61 m sobre el umbral y 59,2 min. Vuelta: 5.132 m y
  5,1 % de máximo.
- **Rendimiento:**
  - armar la red en Python, con la caché: unos 1 s;
  - cargar la red en la app: unos 60 ms;
  - una consulta (4 Dijkstra: ida, vuelta y las dos más cortas): 30–60 ms en el notebook.
- **PWA:**
  - `manifest.webmanifest` e íconos propios.
  - `sw.js` guarda la app y la red (primero lo guardado, después internet) y las teselas vistas (hasta
    3.000).
  - Las teselas se piden con CORS (`crossOrigin`) para poder guardarlas; OSM y Esri lo permiten.
  - La versión de la caché es un hash de los archivos de `docs/`: si algo cambia, los teléfonos bajan la
    versión nueva.
- **`.exe`:** PyInstaller 6.22.3, `--onefile`, 11,6 MB. Lleva solo Python estándar y `docs/`.

---

## 7. Validación con los ejemplos del usuario

Pendiente máxima del modelo (tramos de 10 m, en valor absoluto) en las cuestas que el usuario conoce:

| Cuesta | Pendiente máx. | Altura (m) |
|---|---|---|
| Aníbal Pinto llegando a Beauchef (tramo a menos de 120 m de Beauchef) | 11,8 % | 2,6 → 7,8 |
| Vicente Pérez Rosales llegando a Yerbas Buenas | 12,4 % | 2,3 → 9,6 |
| General Baquedano (máximo de la calle) | 7,9 % | — |

Las tres superan el umbral de 6 % y la ruta las castiga. El resto de Aníbal Pinto sale casi plano (de 12 a
3 m en 1,3 km): la cuesta está concentrada al final, como describió el usuario.

**Rutas de prueba** (u = 6 %, F = 2, sin escaleras):

| Ruta | Óptima | Más corta | Qué evita |
|---|---|---|---|
| Isla Teja → Collico (ida) | 4,93 km · máx 8,1 % | 4,92 km · máx 8,0 % | Casi igual (la subida inevitable está en el destino). |
| Collico → Isla Teja (vuelta) | 5,13 km · máx **5,1 %** | 4,92 km · máx **11,7 %** | Una cuesta de 11,7 %, a cambio de 214 m más. |
| Aníbal Pinto (sur) → UACh (ida) | 2,88 km · máx **5,5 %** | 2,69 km · máx **16,5 %** | La subida de Aníbal Pinto a Beauchef y un sendero empinado del campus: va por Lord Cochrane → Camilo Henríquez → O'Higgins. |
| UACh → Aníbal Pinto (vuelta) | 2,69 km · máx 6,5 % | 2,69 km · máx 6,5 % | Es la misma ruta. |

Los dos casos muestran la asimetría: la ida y la vuelta entre los mismos puntos salen distintas.

**No validado aún:** contraste con pendientes medidas en terreno, por ejemplo con GPS barométrico o
inclinómetro, en las cuestas conocidas. Es la mejor forma de calibrar el umbral (ver §10).

---

## 8. Decisiones

| Decisión | Razón |
|---|---|
| FABDEM y no Copernicus GLO-30 (el que usa SiSCoSu) | Copernicus es un modelo de superficie: con techos y árboles, las pendientes de las calles salen falsas. FABDEM los quita. |
| Red sin simplificar y tramos ≤ 10 m | Pendientes locales, ajuste preciso de los clics y corrección de topología sobre segmentos rectos. |
| Ignorar el sentido del tránsito (`oneway`) | Pedido del usuario: a pie todo vale en los dos sentidos. En bicicleta es responsabilidad de quien la usa. |
| Escaleras desactivadas por defecto | El usuario pidió «todas las calles» y las escaleras no lo son; además el DEM subestima su pendiente. Se pueden activar. |
| Excluir el acceso privado | Condominios, accesos de servicio privados y predios: no son transitables para el público. |
| Conectar solo dentro del mismo nivel | Evita unir puentes con lo que pasa por debajo. |
| Tolerancia de conexión de 3 m | Cubre los errores de dibujo típicos sin cerrar huecos reales. |
| Bajar sin costo | El usuario solo pidió evitar subidas. |
| Ruteo en el navegador (JavaScript) | Permite una app sin servidor, sin conexión y gratis, la misma en Android, iOS y Windows. |
| PWA y no apps nativas | iOS nativo pide un Mac con Xcode y la cuenta de desarrollador de Apple (US$ 99 al año). El usuario descartó el APK: la PWA hace lo mismo en Android. |
| GitHub Pages en repositorio público | Gratis con la cuenta existente. El repositorio no contiene datos privados y los commits usan el correo noreply de GitHub. |

---

## 9. Limitaciones

1. **Resolución del DEM (30 m).** Una cuesta de 20–40 m de largo se suaviza: su pendiente real puede ser
   bastante mayor que la del modelo. Las tres cuestas del usuario aparecen, pero probablemente con un
   número menor que el real. Por eso conviene un umbral más bajo de lo que uno pensaría.
2. **Errores de FABDEM.** Puede quedar ruido de 1–2 m y restos de edificios o árboles grandes, sobre todo
   en bordes de quebradas y riberas.
3. **Extremos de puentes y terraplenes.** En los accesos a los puentes la grilla de 30 m mezcla el río con
   la ribera. Los terraplenes y viaductos fuera de los puentes no se corrigen.
4. **OSM.** La ruta es tan buena como el mapa: faltan o sobran senderos, hay accesos privados sin marcar y
   veredas sin dibujar.
5. **El modelo solo mira la pendiente.** No considera tráfico, seguridad, calidad de la vereda, semáforos,
   iluminación ni cruces peligrosos.
6. **Tiempo.** Tobler es para caminar; no hay tiempo en bicicleta.
7. **Escaleras.** Cuando se permiten, su costo usa la pendiente del DEM, que no refleja la dificultad real.
8. **Licencia de FABDEM.** No permite uso comercial.

---

## 10. Mejoras posibles

- **Un DEM mejor.** Si aparece un LiDAR de Valdivia (MINVU, SERVIU, GORE Los Ríos, UACh), basta con
  `--dem archivo.tif`; con 1–5 m las cuestas cortas saldrían bien.
- **Calibración en terreno.** Medir con un celular las pendientes de 5–10 cuestas conocidas, comparar con el
  modelo y ajustar el umbral, o corregir la pendiente con un factor.
- **Modo bicicleta.** Velocidad según potencia, castigo a las bajadas muy fuertes y opción de respetar los
  sentidos únicos.
- **Navegación paso a paso** y aviso de la próxima cuesta durante el recorrido.
- **Elegir entre varias rutas alternativas** (por ejemplo, la más plana, la equilibrada y la más corta).
- **Actualización automática de OSM** con una GitHub Action mensual.

---

## Referencias

Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022). A 30 m global map of
elevation with forests and buildings removed. *Environmental Research Letters, 17*(2), 024016.
https://doi.org/10.1088/1748-9326/ac4d4f

OpenStreetMap contributors. (2026). *OpenStreetMap* [Base de datos, extracto vía Overpass API del
10-11-2026]. https://www.openstreetmap.org

Scarf, P. (2007). Route choice in mountain navigation, Naismith's rule, and the equivalence of distance and
climb. *Journal of Sports Sciences, 25*(6), 719–726. https://doi.org/10.1080/02640410600874906

Tobler, W. (1993). *Three presentations on geographical analysis and modeling* (Technical Report 93-1).
National Center for Geographic Information and Analysis, University of California, Santa Barbara.

*Hawker et al. (2022) y Scarf (2007) se verificaron en Crossref el 10-11-2026: autores, revista, volumen,
páginas y DOI. Tobler (1993) es un informe técnico sin DOI. La regla de Naismith (1892) se cita a través de
Scarf (2007): la nota original no se consultó.*
