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


@pytest.mark.parametrize("tecla", ["Escape", "Return", "Space"])
def test_se_salta_con_teclas(qtbot, tecla):
    from PySide6.QtCore import Qt
    v = _ventana(qtbot)
    v.reproducir()
    qtbot.keyClick(v, getattr(Qt.Key, f"Key_{tecla}"))
    assert v.result() == tr.QDialog.DialogCode.Accepted and not v.reproduciendo()


def test_se_salta_con_clic(qtbot):
    from PySide6.QtCore import Qt
    v = _ventana(qtbot)
    v.reproducir()
    qtbot.mouseClick(v, Qt.MouseButton.LeftButton)
    assert v.result() == tr.QDialog.DialogCode.Accepted


def test_aviso_para_saltar():
    assert tr.escena(0, "Ana").pista == 0
    assert tr.escena(1000, "Ana").pista == 1
    assert tr.escena(tr.DURACION, "Ana").pista == 0  # se va con el fundido


# ---------------------------------------------------------------- dentro de la aplicación
def test_sin_animaciones_no_hay_transicion(ctx_factory):
    from alquiler.ui import app
    assert app.mostrar_transicion(ctx_factory("admin")) is False


def test_transicion_con_los_datos_de_la_sesion(ctx_factory, monkeypatch, qapp):
    from alquiler.ui import animacion, app
    monkeypatch.setattr(animacion, "_forzado", True)
    vistas = []
    monkeypatch.setattr(tr.TransicionSesion, "exec", lambda self: vistas.append(self._pasos) or 1)
    assert app.mostrar_transicion(ctx_factory("empleado")) is True
    assert vistas[0][0] == ("Identidad verificada", "EMPLEADO")
    assert vistas[0][2] == ("Asistente Cubi", "MODO LOCAL")


def test_main_muestra_la_transicion_entre_portada_y_tablero(monkeypatch, qapp, ctx_factory):
    from alquiler.ui import app
    orden = []
    ctx = ctx_factory("admin")

    class PortadaFalsa:
        def __init__(self, *args): self.contexto = ctx
        def exec(self): orden.append("portada"); return tr.QDialog.DialogCode.Accepted

    class VentanaFalsa:
        cerro_sesion = False
        def __init__(self, *args): orden.append("tablero")
        def show(self): pass

    monkeypatch.setattr(app, "mostrar_cinematica", lambda config: None)
    monkeypatch.setattr(app, "mostrar_transicion", lambda c: orden.append("transicion"))
    monkeypatch.setattr(app, "LoginDialog", PortadaFalsa)
    monkeypatch.setattr(app, "VentanaPrincipal", VentanaFalsa)
    monkeypatch.setattr(app, "ofrecer_demo", lambda *a, **k: None)
    monkeypatch.setattr(app, "preparar_base", lambda config: None)
    monkeypatch.setattr(app.tema, "aplicar", lambda aplicacion: None)
    monkeypatch.setattr(app.QApplication, "exec", lambda self=None: 0)
    assert app.main([]) == 0
    assert orden == ["portada", "transicion", "tablero"]
