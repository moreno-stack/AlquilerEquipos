# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller: ejecutable *onedir* del Sistema de Alquiler de Equipos.

Construir:  python scripts/empaquetar.py       (o: pyinstaller --noconfirm --clean AlquilerEquipos.spec)
Resultado:  dist/AlquilerEquipos/AlquilerEquipos[.exe]

PyInstaller no compila de forma cruzada: el .exe de Windows se genera ejecutando este mismo
archivo en Windows (ver scripts/empaquetar_windows.bat).
"""

import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

RAIZ = Path(SPECPATH)

# Alembic carga env.py y versions/*.py como archivos desde disco: van como datos, con
# la misma ruta relativa que usa alquiler/db.py (Path(__file__).parent / "migrations").
MIGRACIONES = [
    (str(ruta), str(ruta.parent.relative_to(RAIZ)))
    for ruta in (RAIZ / "alquiler" / "migrations").rglob("*")
    if ruta.is_file() and "__pycache__" not in ruta.parts
]

# Módulos de Qt que la aplicación no usa (reducen mucho el tamaño).
QT_NO_USADOS = [f"PySide6.{m}" for m in (
    "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel", "QtWebSockets",
    "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DLogic", "Qt3DExtras", "Qt3DAnimation",
    "QtQuick", "QtQuick3D", "QtQuickWidgets", "QtQml", "QtMultimedia", "QtMultimediaWidgets",
    "QtPdf", "QtPdfWidgets", "QtDataVisualization", "QtGraphs", "QtLocation", "QtPositioning",
    "QtBluetooth", "QtNfc", "QtSensors", "QtSerialPort", "QtTextToSpeech", "QtSql", "QtTest",
    "QtDesigner", "QtHelp", "QtSpatialAudio", "QtRemoteObjects", "QtScxml", "QtStateMachine",
)]

# Paquetes que la aplicación no usa pero que pueden estar instalados en el entorno de compilación.
AJENOS = ["numpy", "PIL", "cryptography", "matplotlib", "pandas", "scipy", "IPython", "jedi",
          "notebook", "setuptools", "pkg_resources", "lxml", "gi"]

a = Analysis(
    [str(RAIZ / "scripts" / "lanzador.py")],
    pathex=[str(RAIZ)],
    datas=[*MIGRACIONES, (str(RAIZ / "diseno" / "tokens.css"), "diseno")],  # colores del tema
    hiddenimports=[
        *collect_submodules("alquiler"),       # vistas importadas de forma perezosa, seed
        *collect_submodules("alembic"),        # comandos y operaciones usados por init_db
        "sqlalchemy.dialects.sqlite",
        "logging.config",
    ],
    excludes=["tkinter", "pytest", "pytestqt", "PyInstaller", *QT_NO_USADOS, *AJENOS],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AlquilerEquipos",
    console=sys.platform != "win32",  # en Windows: aplicación de ventana, sin consola
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AlquilerEquipos", upx=False)

# Plantilla de configuración JUNTO al ejecutable (no dentro de _internal): config.py busca
# alquiler.env en la carpeta del programa, y el usuario copia ahí la plantilla con su clave.
shutil.copy2(RAIZ / "alquiler.env.ejemplo", Path(DISTPATH) / "AlquilerEquipos" / "alquiler.env.ejemplo")
