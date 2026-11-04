"""Íconos de la aplicación (.ico para Windows, .icns para macOS) generados desde el logo."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

PIL = pytest.importorskip("PIL.Image")


def test_genera_ico_e_icns(tmp_path, qapp):
    import importlib.util
    from pathlib import Path
    ruta = Path(__file__).resolve().parent.parent / "scripts" / "generar_iconos.py"
    spec = importlib.util.spec_from_file_location("generar_iconos", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    ico, icns, png = modulo.generar(tmp_path)
    assert ico.suffix == ".ico" and icns.suffix == ".icns" and png.suffix == ".png"
    with PIL.open(ico) as imagen:
        assert (256, 256) in imagen.info["sizes"] and (16, 16) in imagen.info["sizes"]
    with PIL.open(icns) as imagen:
        assert imagen.size[0] >= 512
    with PIL.open(png) as imagen:
        assert imagen.size == (1024, 1024) and imagen.mode == "RGBA"
