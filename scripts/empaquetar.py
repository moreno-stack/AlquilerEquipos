"""Construye el ejecutable con PyInstaller y lo verifica con --autoprueba en un entorno limpio.

Uso (desde la raíz del proyecto, con el entorno virtual activado):
    pip install pyinstaller
    python scripts/empaquetar.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "AlquilerEquipos" + (".exe" if sys.platform == "win32" else "")


def construir() -> Path:
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    str(RAIZ / "AlquilerEquipos.spec")], cwd=RAIZ, check=True)
    return RAIZ / "dist" / "AlquilerEquipos"


def verificar(carpeta: Path) -> int:
    """Copia el ejecutable fuera del repo y lo arranca sin Python en el PATH."""
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "app"
        shutil.copytree(carpeta, copia)
        sin_python = Path(tmp) / "path-vacio"  # PATH sin ningún intérprete de Python
        sin_python.mkdir()
        entorno = {"HOME": tmp, "USERPROFILE": tmp, "TEMP": tmp, "TMP": tmp,
                   "ALQUILER_DB_PATH": str(Path(tmp) / "Nueva carpeta ñ" / "alquiler.db"),
                   "PATH": str(sin_python) if os.name != "nt"
                   else os.environ.get("SystemRoot", r"C:\Windows")}
        if sys.platform.startswith("linux"):
            entorno["QT_QPA_PLATFORM"] = "offscreen"
        if os.name == "nt":
            entorno["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
        if not (copia / "alquiler.env.ejemplo").is_file():
            print("FALTA alquiler.env.ejemplo junto al ejecutable")
            return 1
        resultado = subprocess.run([str(copia / NOMBRE), "--autoprueba"], env=entorno,
                                   capture_output=True, text=True, timeout=300)
        print(resultado.stdout.strip() or "(sin salida: en Windows la app no tiene consola)")
        print(f"Código de salida: {resultado.returncode}")
        if resultado.returncode != 0 or os.name == "nt":  # en Windows --probar-ia abre un diálogo
            return resultado.returncode
        # Sin clave, --probar-ia debe explicar cómo configurarla y salir con código 2.
        prueba_ia = subprocess.run([str(copia / NOMBRE), "--probar-ia"], env=entorno,
                                   capture_output=True, text=True, timeout=60)
        print(prueba_ia.stdout.strip().splitlines()[0] if prueba_ia.stdout.strip() else "(sin salida)")
        print(f"--probar-ia sin clave: código {prueba_ia.returncode} (se espera 2)")
        return 0 if prueba_ia.returncode == 2 else 1


if __name__ == "__main__":
    carpeta = construir()
    tamano = sum(f.stat().st_size for f in carpeta.rglob("*")
                 if f.is_file() and not f.is_symlink()) / 1_048_576
    print(f"Ejecutable en {carpeta} ({tamano:.0f} MB)")
    raise SystemExit(verificar(carpeta))
