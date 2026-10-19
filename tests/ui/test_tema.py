"""Tema "Pizarra y cian" con degradado de marca: paleta única, contraste legible, Fusion oscuro y sin colores sueltos."""

import re
from pathlib import Path

import pytest

from alquiler.ui import tema, widgets
from alquiler.ui.tema import COLOR_ESTADO, PALETA, TONOS, contraste, hoja_de_estilo

P = PALETA
PARES_FIJOS = [
    (P["texto"], P["fondo"]), (P["texto"], P["superficie"]), (P["texto"], P["superficie_alta"]),
    (P["texto_secundario"], P["fondo"]), (P["texto_secundario"], P["superficie"]),
    (P["texto_lateral"], P["lateral"]), (P["texto"], P["lateral_activo"]),
    (P["sobre_acento"], P["acento"]), (P["sobre_acento"], P["acento_hover"]), (P["secundario"], P["fondo"]),
    (P["acento"], P["lateral_activo"]), (P["acento_texto"], P["acento_suave"]),
    ("#FFFFFF", P["seleccion"]), (P["peligro"], P["superficie"]), ("#FFFFFF", P["peligro_hover"]),
    # texto sobre los DOS extremos del degradado de marca (normal y al pasar el cursor)
    (P["sobre_acento"], P["secundario"]), (P["sobre_acento"], P["secundario_claro"]),
]


def test_degradado_de_marca_en_la_hoja():
    qss = hoja_de_estilo()
    assert tema.DEGRADADOS["degradado"] in qss and tema.DEGRADADOS["degradado_hover"] in qss
    assert P["acento"] in tema.DEGRADADOS["degradado"] and P["secundario"] in tema.DEGRADADOS["degradado"]


def test_es_un_tema_oscuro():
    for fondo in ("fondo", "superficie", "lateral"):
        assert tema._luminancia(P[fondo]) < 0.05, fondo
    assert tema._luminancia(P["texto"]) > 0.6


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


@pytest.mark.parametrize("estado", list(COLOR_ESTADO))
def test_color_fuerte_visible_sobre_superficie(estado):
    """Barras y franjas: contraste de componente gráfico (WCAG 1.4.11, ≥ 3:1)."""
    assert contraste(COLOR_ESTADO[estado][0], P["superficie"]) >= 3


def test_tonos_de_estado_coinciden_con_los_estados():
    assert TONOS["ok"] == COLOR_ESTADO["Disponible"][1:]
    assert TONOS["peligro"] == COLOR_ESTADO["Fuera de servicio"][1:]
    assert set(tema.COLOR_TONO) == set(TONOS)


def test_hoja_usa_tokens_y_no_quedan_marcadores():
    qss = hoja_de_estilo()
    for token in ("fondo", "superficie", "lateral", "acento"):
        assert P[token] in qss
    assert not re.search(r"\{[a-z_]+\}", qss)  # todo {token} fue sustituido
    assert "QComboBox QAbstractItemView" in qss and "QCalendarWidget" in qss  # emergentes oscuros


def test_widgets_estilo_es_el_tema():
    assert widgets.ESTILO == hoja_de_estilo()


def test_aplicar_usa_fusion_y_paleta_oscura():
    from PySide6.QtGui import QPalette

    class AppFalsa:
        def setStyle(self, estilo): self.estilo = estilo
        def setPalette(self, paleta): self.paleta = paleta
        def setStyleSheet(self, qss): self.qss = qss

    app = AppFalsa()
    tema.aplicar(app)
    assert app.estilo == "Fusion" and app.qss == hoja_de_estilo()
    assert app.paleta.color(QPalette.ColorRole.Window).name().upper() == P["fondo"]
    assert app.paleta.color(QPalette.ColorRole.Text).name().upper() == P["texto"]
    assert app.paleta.color(QPalette.ColorRole.Highlight).name().upper() == P["seleccion"]


def test_sin_colores_fuera_del_tema():
    raiz = Path(tema.__file__).parent
    hex_suelto = re.compile(r"#[0-9A-Fa-f]{6}\b|\bwhite\b")
    culpables = [str(p.relative_to(raiz)) for p in raiz.rglob("*.py")
                 if hex_suelto.search(p.read_text(encoding="utf-8"))]  # ni siquiera tema.py
    assert culpables == []
