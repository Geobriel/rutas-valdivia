"""
lanzador_exe.py — Lo que corre dentro de RutasSinCuestas.exe.

Sirve la app web (la carpeta docs/, que va empaquetada dentro del .exe) en http://127.0.0.1 y la abre
en el navegador. Solo usa la biblioteca estándar de Python; todo el cálculo de rutas lo hace la app en
el navegador. Para cerrarla, cerrar la ventana negra.
"""
import socket
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# dentro del .exe, PyInstaller descomprime los archivos en sys._MEIPASS
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB = BASE / "docs"


class Manejador(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".webmanifest": "application/manifest+json",
                      ".bin": "application/octet-stream"}

    def log_message(self, *args):
        pass


def puerto_libre(preferido=8766):
    """El mismo puerto siempre (así el navegador recuerda la app); si está ocupado, otro."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferido))
            return preferido
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main():
    puerto = puerto_libre()
    http = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=str(WEB)))
    url = f"http://127.0.0.1:{puerto}/"
    print("Rutas sin cuestas · Valdivia")
    print(f"La app está abierta en {url}")
    print("Para cerrarla, cierra esta ventana.")
    if "--sin-navegador" not in sys.argv:          # para probarlo sin abrir pestañas
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
