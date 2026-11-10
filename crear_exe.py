"""
crear_exe.py — Arma dist/RutasSinCuestas.exe (Windows) con la app web de docs/ adentro.

Correr con el .venv de SiSCoSu después de `python rutas_pendiente.py --web`:

    python crear_exe.py

PyInstaller vive en un entorno aparte, fuera de Dropbox (~/rutas_valdivia_build/venv), para no
tocar el .venv de SiSCoSu; si no existe, se crea solo. El .exe solo lleva Python estándar (lanzador_exe.py)
y los archivos de docs/: todo el cálculo de rutas lo hace la app en el navegador.
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
TALLER = Path.home() / "rutas_valdivia_build"
PY = TALLER / "venv" / "Scripts" / "python.exe"


def main():
    from rutas_pendiente import sellar_version
    sellar_version(RAIZ / "docs")
    if not PY.exists():
        print("Creando el entorno con PyInstaller en", TALLER)
        subprocess.run([sys.executable, "-m", "venv", str(TALLER / "venv")], check=True)
        subprocess.run([str(PY), "-m", "pip", "install", "-q", "pyinstaller"], check=True)
    subprocess.run([
        str(PY), "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", "RutasSinCuestas",
        "--icon", str(RAIZ / "docs" / "iconos" / "icono.ico"),
        "--add-data", f"{RAIZ / 'docs'};docs",
        "--distpath", str(RAIZ / "dist"),
        "--workpath", str(TALLER / "work"),
        "--specpath", str(TALLER),
        str(RAIZ / "lanzador_exe.py"),
    ], check=True)
    exe = RAIZ / "dist" / "RutasSinCuestas.exe"
    print(f"Listo: {exe} ({exe.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
