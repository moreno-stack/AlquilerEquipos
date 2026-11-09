"""Conectar la IA desde la aplicación: probar la clave, guardarla y activarla sin reiniciar."""

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.ui.logica import ia


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    destino = tmp_path / "usuario"
    monkeypatch.setattr(ia, "CARPETA_CLAVE", destino)
    return destino


def _probar(codigo, mensaje="IA OK"):
    def probar(config, imprimir=print):
        probar.clave = config.groq_api_key
        imprimir(mensaje)
        return codigo
    return probar


def test_clave_valida_se_guarda_y_activa(ctx_factory, carpeta, monkeypatch):
    monkeypatch.setattr(ia, "probar_ia", _probar(0))
    ctx = ctx_factory("admin")
    assert ctx.cliente_llm is None
    ia.conectar_ia(ctx, " gsk_valida ")
    assert ia.probar_ia.clave == "gsk_valida"
    assert (carpeta / "alquiler.env").read_text(encoding="utf-8").strip() == "GROQ_API_KEY=gsk_valida"
    assert ctx.cliente_llm is not None and ctx.config.groq_api_key == "gsk_valida"
    assert ia.ia_disponible(ctx)


def test_clave_que_no_funciona_no_se_guarda(ctx_factory, carpeta, monkeypatch):
    monkeypatch.setattr(ia, "probar_ia", _probar(1, "IA NO DISPONIBLE: La clave de Groq no es válida"))
    ctx = ctx_factory("admin")
    with pytest.raises(ReglaNegocioError, match="no es válida"):
        ia.conectar_ia(ctx, "gsk_mala")
    assert not (carpeta / "alquiler.env").exists() and ctx.cliente_llm is None


def test_clave_vacia(ctx_factory, carpeta):
    with pytest.raises(ReglaNegocioError):
        ia.conectar_ia(ctx_factory("admin"), "   ")


@pytest.mark.parametrize("rol", ["empleado", "cliente"])
def test_solo_el_administrador_conecta_la_ia(ctx_factory, carpeta, rol):
    with pytest.raises(PermisoDenegado):
        ia.conectar_ia(ctx_factory(rol), "gsk_x")
    assert not ia.puede_conectar_ia(ctx_factory(rol)) and ia.puede_conectar_ia(ctx_factory("admin"))
