"""Cinemática de arranque: una línea de tiempo determinista que la vista solo pinta."""

import pytest

from alquiler.ui import cinematica as cine


def test_tramo_va_de_0_a_1_dentro_de_su_intervalo():
    inicio, fin = cine.TRAMOS["rejilla"]
    assert cine.tramo("rejilla", inicio - 50) == 0
    assert 0 < cine.tramo("rejilla", (inicio + fin) / 2) < 1
    assert cine.tramo("rejilla", fin + 50) == 1


def test_los_tramos_caben_en_la_duracion():
    assert all(0 <= a < b <= cine.DURACION for a, b in cine.TRAMOS.values())


def test_rejilla_y_red_se_encienden():
    assert cine.escena(0).rejilla == 0 and cine.escena(0).nodos == 0
    medio = cine.escena(1000)
    assert medio.rejilla == 1 and 0 < medio.nodos < cine.NODOS
    assert cine.escena(1700).nodos == cine.NODOS


def test_cubo_se_traza_arista_por_arista():
    assert cine.escena(1100).cubo == 0
    medio = cine.escena(1950).cubo
    assert 4 < medio < 8 and medio != int(medio)  # una arista a medio trazar
    assert cine.escena(2700).cubo == cine.ARISTAS


def test_orden_de_trazado_empieza_por_el_frente():
    orden = cine.orden_aristas()
    assert sorted(orden) == sorted((i, j) for i, j, _ in __import__(
        "alquiler.ui.logo", fromlist=["aristas"]).aristas())
    ocultas = {(i, j) for i, j, oculta in __import__(
        "alquiler.ui.logo", fromlist=["aristas"]).aristas() if oculta}
    assert set(orden[-3:]) == ocultas  # las ocultas se dibujan al final


def test_nucleo_se_enciende_con_un_destello():
    antes, pico, despues = cine.escena(2400), cine.escena(2900), cine.escena(3300)
    assert antes.nucleo == 0 and antes.destello == 0
    assert pico.nucleo == 1 and pico.destello == pytest.approx(1)
    assert despues.nucleo == 1 and despues.destello == 0


def test_titulo_se_escribe_letra_por_letra():
    assert cine.escena(2700).titulo == ""
    parcial = cine.escena(3300).titulo
    assert parcial and cine.TITULO.startswith(parcial) and parcial != cine.TITULO
    assert cine.escena(3900).titulo == cine.TITULO
    assert cine.escena(3900).subtitulo == cine.SUBTITULO
    assert cine.escena(3000).subtitulo == ""


def test_glitch_solo_mientras_se_escribe_y_es_determinista():
    durante = [cine.glitch(t) for t in range(2800, 3800, 40)]
    assert any(d != 0 for d in durante) and all(abs(d) <= cine.GLITCH_MAX for d in durante)
    assert durante == [cine.glitch(t) for t in range(2800, 3800, 40)]
    assert cine.glitch(2000) == 0 and cine.glitch(4200) == 0


@pytest.mark.parametrize("con_clave, estado", [(True, "CLAVE CONFIGURADA"), (False, "MODO LOCAL")])
def test_lineas_de_arranque_dicen_la_verdad_sobre_la_ia(con_clave, estado):
    lineas = cine.lineas_arranque(ia_configurada=con_clave)
    assert len(lineas) == 4 and lineas[0] == ("Base de datos SQLite", "OK")
    assert ("Asistente Cubi · Groq", estado) in lineas


def test_lineas_y_barra_de_carga_avanzan():
    assert cine.escena(3100).lineas == 0 and cine.escena(3100).progreso == 0
    medio = cine.escena(4000)
    assert 0 < medio.lineas < 4 and 0 < medio.progreso < 1
    assert cine.escena(4900).lineas == 4 and cine.escena(4900).progreso == 1


def test_fundido_final():
    assert cine.escena(4900).fundido == 0
    assert 0 < cine.escena(5300).fundido < 1
    assert cine.escena(cine.DURACION).fundido == 1


# ---------------------------------------------------------------- el widget
def _brillo_centro(widget) -> int:
    imagen = widget.grab().toImage()
    x, y = int(widget.width() * cine.CENTRO_CUBO[0]), int(widget.height() * cine.CENTRO_CUBO[1])
    return imagen.pixelColor(x, y).lightness()


def test_pinta_cada_momento_de_la_secuencia(qtbot):
    c = cine.Cinematica(ia_configurada=False)
    qtbot.addWidget(c)
    c.resize(960, 600)
    for t in (0, 800, 1900, 2900, 3400, 4300, cine.DURACION):
        c.ir_a(t)
        assert c.escena_actual().t == t and not c.grab().isNull()
    c.ir_a(0)
    oscuro = _brillo_centro(c)
    c.ir_a(2900)  # núcleo encendido y destello en su pico
    assert _brillo_centro(c) > oscuro + 60


def test_se_reproduce_sola_y_termina(qtbot, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from alquiler.ui import animacion
    monkeypatch.setattr(animacion, "_forzado", True)
    monkeypatch.setattr(cine, "DURACION", 300)  # versión corta para la prueba
    c = cine.Cinematica(ia_configurada=True)
    qtbot.addWidget(c)
    c.show()
    assert c.reproduciendo()
    qtbot.waitUntil(lambda: c.result() == QDialog.DialogCode.Accepted, timeout=3000)
    assert not c.reproduciendo()


@pytest.mark.parametrize("accion", ["esc", "enter", "espacio", "clic"])
def test_se_puede_saltar(qtbot, monkeypatch, accion):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog
    from alquiler.ui import animacion
    monkeypatch.setattr(animacion, "_forzado", True)
    c = cine.Cinematica(ia_configurada=False)
    qtbot.addWidget(c)
    c.show()
    teclas = {"esc": Qt.Key.Key_Escape, "enter": Qt.Key.Key_Return, "espacio": Qt.Key.Key_Space}
    if accion == "clic":
        qtbot.mouseClick(c, Qt.MouseButton.LeftButton)
    else:
        qtbot.keyClick(c, teclas[accion])
    assert c.result() == QDialog.DialogCode.Accepted and not c.reproduciendo()


def test_pista_para_saltar():
    assert "saltar" in cine.PISTA.lower()
    assert cine.escena(100).pista == 0
    assert cine.escena(2000).pista == 1
    assert cine.escena(cine.DURACION).pista == 0  # se va con el fundido
