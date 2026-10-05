"""Tema "Taller industrial": paleta única, contraste legible y sin colores sueltos."""

import re
from pathlib import Path

import pytest

from alquiler.ui import tema, widgets
from alquiler.ui.tema import COLOR_ESTADO, PALETA, TONOS, contraste, hoja_de_estilo

P = PALETA
PARES_FIJOS = [
    (P["texto"], P["superficie"]), (P["texto"], P["arena"]),
    (P["texto_secundario"], P["superficie"]), (P["texto_secundario"], P["arena"]),
    (P["grafito"], P["ambar"]), (P["grafito"], P["ambar_hover"]),
    ("#FFFFFF", P["acero"]), ("#FFFFFF", P["peligro"]),
    (P["texto_lateral"], P["grafito"]), (P["texto_lateral"], P["grafito_claro"]),
    (P["ambar_texto"], P["ambar_suave"]), (P["peligro"], P["superficie"]),
]


def test_cinco_estados_con_color():
    assert set(COLOR_ESTADO) == {"Disponible", "Alquilado", "Reservado", "En mantenimiento",
                                 "Fuera de servicio"}


def test_contraste_referencia():
    assert round(contraste("#000000", "#FFFFFF"), 1) == 21.0
    assert contraste("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)


@pytest.mark.parametrize("texto, fondo", PARES_FIJOS
                         + [(t, f) for f, t in TONOS.values()]
                         + [(t, f) for _, f, t in COLOR_ESTADO.values()])
def test_contraste_minimo_aa(texto, fondo):
    assert contraste(texto, fondo) >= 4.5, (texto, fondo)


def test_tonos_de_estado_coinciden_con_los_estados():
    assert TONOS["ok"] == COLOR_ESTADO["Disponible"][1:]
    assert TONOS["peligro"] == COLOR_ESTADO["Fuera de servicio"][1:]
    assert set(tema.COLOR_TONO) == set(TONOS)


def test_hoja_usa_tokens():
    qss = hoja_de_estilo()
    for token in ("ambar", "grafito", "arena", "acero"):
        assert P[token] in qss
    assert "#2563EB" not in qss  # el azul genérico anterior


def test_widgets_estilo_es_el_tema():
    assert widgets.ESTILO == hoja_de_estilo()


def test_sin_colores_fuera_del_tema():
    raiz = Path(tema.__file__).parent
    hex_suelto = re.compile(r"#[0-9A-Fa-f]{6}\b")
    culpables = [str(p.relative_to(raiz)) for p in raiz.rglob("*.py")
                 if p.name != "tema.py" and hex_suelto.search(p.read_text(encoding="utf-8"))]
    assert culpables == []
