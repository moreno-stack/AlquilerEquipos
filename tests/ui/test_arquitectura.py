"""Separación vista-lógica: las vistas Qt no tocan el backend directamente."""

import ast
from pathlib import Path

import alquiler.ui

RAIZ_UI = Path(alquiler.ui.__file__).parent
PROHIBIDOS = ("alquiler.services", "alquiler.ai", "alquiler.models", "alquiler.auth",
              "alquiler.db", "alquiler.seed", "sqlalchemy")
EXENTOS = {"app.py"}  # raíz de composición: arma la base y la ventana


def _modulos_vista():
    for ruta in RAIZ_UI.rglob("*.py"):
        relativa = ruta.relative_to(RAIZ_UI)
        if relativa.parts[0] == "logica" or relativa.name in EXENTOS:
            continue
        yield relativa, ruta


def _importados(ruta: Path) -> list[str]:
    nombres = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.append(nodo.module)
    return nombres


def test_vistas_no_importan_backend():
    violaciones = [
        f"{relativa}: {nombre}"
        for relativa, ruta in _modulos_vista()
        for nombre in _importados(ruta)
        if nombre.startswith(PROHIBIDOS)
    ]
    assert violaciones == []


def test_la_prueba_detecta_una_violacion(tmp_path):
    archivo = tmp_path / "vista_mala.py"
    archivo.write_text("from alquiler.services import equipos\nimport sqlalchemy\n")
    assert [n for n in _importados(archivo) if n.startswith(PROHIBIDOS)] == [
        "alquiler.services", "sqlalchemy"]
