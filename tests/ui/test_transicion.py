"""Transición de inicio de sesión: línea de tiempo determinista con datos reales de la cuenta."""

from alquiler.ui import transicion as tr


def test_tramos_caben_en_la_duracion():
    assert all(0 <= a < b <= tr.DURACION for a, b in tr.TRAMOS.values())


def test_tramo_limites():
    inicio, fin = tr.TRAMOS["anillo"]
    assert tr.tramo("anillo", inicio - 1) == 0 and tr.tramo("anillo", fin + 1) == 1
    assert 0 < tr.tramo("anillo", (inicio + fin) / 2) < 1


def test_escena_inicial_y_final():
    assert tr.escena(0, "Ana").anillo == 0 and tr.escena(0, "Ana").saludo == ""
    final = tr.escena(tr.DURACION, "Ana")
    assert final.saludo == "Hola, Ana"  # sin suponer el género de nadie
    assert final.pasos == tr.PASOS and final.progreso == 1 and final.fundido == 1


def test_pasos_con_datos_reales_de_la_cuenta():
    pasos = tr.pasos_sesion("admin", 11, ia_configurada=False)
    assert pasos == [("Identidad verificada", "ADMINISTRADOR"),
                     ("Permisos del rol", "11 SECCIONES"),
                     ("Asistente Cubi", "MODO LOCAL"),
                     ("Tablero de control", "LISTO")]
    assert tr.pasos_sesion("cliente", 2, ia_configurada=True)[1:3] == [
        ("Permisos del rol", "2 SECCIONES"), ("Asistente Cubi", "GROQ")]
    assert tr.pasos_sesion("cliente", 1, True)[1][1] == "1 SECCIÓN"


def _ventana(qtbot, **kw):
    datos = dict(nombre="Ana", rol="cliente", secciones=2, ia_configurada=False)
    datos.update(kw)
    v = tr.TransicionSesion(**datos)
    qtbot.addWidget(v)
    v.resize(1280, 800)
    return v


import pytest  # noqa: E402


@pytest.mark.parametrize("t", [0, 400, 1200, 2000, 2600, tr.DURACION])
def test_cada_momento_se_pinta(qtbot, t):
    v = _ventana(qtbot)
    v.ir_a(t)
    assert v.escena_actual().t == t
    assert not v.grab().isNull()


def test_reproduce_en_tiempo_real_y_cierra_sola(qtbot, monkeypatch):
    monkeypatch.setattr(tr, "DURACION", 300)
    v = _ventana(qtbot)
    v.reproducir()
    assert v.reproduciendo()
    qtbot.waitUntil(lambda: v.result() == tr.QDialog.DialogCode.Accepted, timeout=3000)
