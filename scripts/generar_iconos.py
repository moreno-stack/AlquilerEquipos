"""Genera los íconos de la aplicación a partir del logo "cubo neural" (alquiler/ui/logo.py).

Uso:  python scripts/generar_iconos.py [carpeta]     (por defecto: build/iconos)
Crea  AlquilerEquipos.ico (Windows), AlquilerEquipos.icns (macOS) y AlquilerEquipos.png.
Necesita Pillow (solo para empaquetar: pip install pillow).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no abre ventanas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TAMANOS_ICO = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def generar(carpeta: Path) -> tuple[Path, Path, Path]:
    from PIL import Image
    from PySide6.QtGui import QGuiApplication

    from alquiler.ui import logo

    QGuiApplication.instance() or QGuiApplication([])
    carpeta.mkdir(parents=True, exist_ok=True)
    png = carpeta / "AlquilerEquipos.png"
    logo.pixmap_logo(1024).save(str(png))  # vector → 1024 px con fondo transparente
    with Image.open(png) as imagen:
        base = imagen.convert("RGBA")
    ico, icns = carpeta / "AlquilerEquipos.ico", carpeta / "AlquilerEquipos.icns"
    base.save(ico, sizes=TAMANOS_ICO)
    base.save(icns)
    return ico, icns, png


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build") / "iconos"
    for ruta in generar(destino):
        print(ruta)
