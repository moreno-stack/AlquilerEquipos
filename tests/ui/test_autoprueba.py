"""Modo --autoprueba: verifica una instalación (o el ejecutable) sin intervención."""

from datetime import date

from alquiler import __version__
from alquiler.config import cargar_config
from alquiler.ui import app


def test_autoprueba_no_toca_la_base_del_usuario(tmp_path, capsys):
    """Verificar la instalación no debe sembrar datos demo en la base real."""
    base_real = tmp_path / "datos" / "alquiler.db"
    config = cargar_config({"ALQUILER_DB_PATH": str(base_real)})
    assert app.autoprueba(config, hoy=lambda: date(2026, 3, 10)) == 0
    salida = capsys.readouterr().out
    assert "AUTOPRUEBA OK: 11 secciones" in salida
    assert "Autoprueba ñ" in salida      # base temporal con espacio y tilde en la ruta
    assert not base_real.exists()        # la base del usuario ni siquiera se crea


def test_autoprueba_ignora_una_base_existente_con_otra_clave(tmp_path, capsys):
    base_real = tmp_path / "alquiler.db"
    config = cargar_config({"ALQUILER_DB_PATH": str(base_real)})
    fabrica = app.preparar_base(config)        # base real con datos y su propio admin
    fabrica.kw["bind"].dispose()
    tamano = base_real.stat().st_size
    assert app.autoprueba(config, hoy=lambda: date(2026, 3, 10)) == 0
    assert base_real.stat().st_size == tamano


def test_autoprueba_informa_error(tmp_path, capsys):
    config = cargar_config({"ALQUILER_DB_PATH": str(tmp_path / "a.db")})

    def vista_rota(ctx):
        raise RuntimeError("vista rota")

    codigo = app.autoprueba(config, hoy=lambda: date(2026, 3, 10),
                            fabricas={**app.fabricas_de_vistas(), "reportes": vista_rota})
    assert codigo == 1
    assert "AUTOPRUEBA FALLÓ" in capsys.readouterr().out


def test_version(capsys):
    assert app.main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out
