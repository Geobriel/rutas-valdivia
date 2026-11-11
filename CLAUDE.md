# Rutas sin cuestas · Valdivia

Proyecto personal de Gabriel, **aparte de SiSCoSu**: no aplican aquí las reglas de carpetas, bitácora ni
decisiones metodológicas de SiSCoSu. Ruta de ida y vuelta en Valdivia evitando subidas empinadas: calles
de OSM con topología corregida, alturas de FABDEM y costo asimétrico.

## Leer primero

- `README.md`: qué es, enlaces e índice.
- `DOCUMENTACION/INFORME.md`: método, cifras, validación, decisiones y limitaciones.
- `DOCUMENTACION/MANTENIMIENTO.md`: cómo actualizar, rehacer el `.exe`, publicar y verificar; arquitectura y
  formato de `red.bin`.
- `DOCUMENTACION/HISTORIAL.md`: versiones y bitácora; sumarle una entrada a cada cambio.
- `DOCUMENTACION/GUIA_DE_USO.md`: uso y problemas frecuentes.

## Reglas

- **El modelo vive dos veces:** el costo y las estadísticas están en `rutas_pendiente.py` (`Red._matriz`,
  `Red._describir`) y en `docs/ruteo.js` (`costos`, `describir`). Un cambio en uno va en el otro, y después
  se verifica que Python y Node den lo mismo (MANTENIMIENTO §5).
- **Sellar antes de publicar:** todo cambio en `docs/` necesita `sellar_version()`, porque si no, los
  teléfonos siguen con la versión guardada. `--web` y `crear_exe.py` sellan solos.
- Python: el `.venv` de SiSCoSu (`..\SiSCoSu\.venv\Scripts\python.exe`) o `requirements.txt`. PyInstaller
  va solo en `~/rutas_valdivia_build/venv`, nunca en el `.venv` de SiSCoSu.
- **Repositorio público** `Geobriel/rutas-valdivia`:
  - commits con el correo noreply (ya configurado en el repositorio), nunca con el correo personal;
  - mensajes en español;
  - no subir `cache/`, `salidas/` ni `dist/`;
  - el `.exe` va en Releases.
- Mantener al día README, INFORME, HISTORIAL y GUIA cuando cambien el método, las cifras o el uso.
- Licencias: FABDEM CC BY-NC-SA (no comercial) y OSM ODbL; las atribuciones deben seguir visibles en la app.
