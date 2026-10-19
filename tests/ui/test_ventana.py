"""Login, ventana principal con navegación por rol y arranque de la aplicación."""

import pytest
from PySide6.QtWidgets import QDialog, QLabel

from alquiler.auth import autenticar, crear_usuario
from alquiler.models import Rol
from alquiler.ui import app
from alquiler.ui.logica.navegacion import secciones_para
from alquiler.ui.login import LoginDialog
from alquiler.ui.ventana import VentanaPrincipal
from tests.ui.conftest import HOY


def test_login_correcto_y_fallido(qtbot, fabrica, config):
    with fabrica() as s:
        crear_usuario(s, "luis", "clave-segura", Rol.EMPLEADO, "Luis Gómez")
    dlg = LoginDialog(fabrica, config, None, lambda: HOY)
    qtbot.addWidget(dlg)
    dlg.campo_usuario.setText("luis")
    dlg.campo_password.setText("mala-clave")
    dlg.boton_ingresar.click()
    assert "incorrectos" in dlg.etiqueta_error.text()
    assert dlg.result() != QDialog.DialogCode.Accepted and dlg.contexto is None
    dlg.campo_password.setText("clave-segura")
    dlg.boton_ingresar.click()
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.contexto.usuario.username == "luis"


@pytest.mark.parametrize("rol", ["admin", "empleado", "cliente"])
def test_barra_lateral_por_rol(qtbot, ctx_factory, rol):
    ctx = ctx_factory(rol)
    v = VentanaPrincipal(ctx, {})
    qtbot.addWidget(v)
    assert v.claves_visibles() == [s.clave for s in secciones_para(ctx)]


def test_vistas_se_crean_al_visitarlas(qtbot, ctx_factory):
    creadas = []

    def fabrica_de(clave):
        def crear(ctx):
            creadas.append(clave)
            return QLabel(clave)
        return crear

    v = VentanaPrincipal(ctx_factory("admin"), {"inicio": fabrica_de("inicio"),
                                                "equipos": fabrica_de("equipos"),
                                                "perfil": fabrica_de("perfil")})
    qtbot.addWidget(v)
    assert creadas == ["inicio"]           # solo la primera sección (Inicio) al abrir
    v.ir_a("perfil")
    v.ir_a("equipos")
    v.ir_a("perfil")
    assert creadas == ["inicio", "perfil", "equipos"]  # cada vista se crea una sola vez
    assert v.vista_actual().text() == "perfil"
    v.ir_a("reportes")                       # sin fábrica: marcador, sin error
    assert v.clave_actual() == "reportes"


def test_barra_estado_muestra_usuario_y_modo_ia(qtbot, ctx_factory):
    sin_ia = VentanaPrincipal(ctx_factory("empleado"), {})
    con_ia = VentanaPrincipal(ctx_factory("admin", cliente_llm=object()), {})
    qtbot.addWidget(sin_ia)
    qtbot.addWidget(con_ia)
    assert "Empleado" in sin_ia.etiqueta_usuario.text()
    assert "sin clave" in sin_ia.etiqueta_ia.text()
    assert con_ia.etiqueta_ia.text() == "IA: Groq conectada" and con_ia.etiqueta_ia.tono == "marca"
    assert sin_ia.etiqueta_ia.tono == "neutro"


def test_cerrar_sesion_emite_senal(qtbot, ctx_factory):
    v = VentanaPrincipal(ctx_factory("admin"), {})
    qtbot.addWidget(v)
    with qtbot.waitSignal(v.sesion_cerrada, timeout=1000):
        v.boton_cerrar_sesion.click()


def test_preparar_base_vacia_ofrece_demo(config):
    fabrica = app.preparar_base(config)
    assert app.base_vacia(fabrica)
    with fabrica() as s:
        assert autenticar(s, "admin", "admin1234").rol is Rol.ADMIN
    preguntas, cargas = [], []
    assert app.ofrecer_demo(config, fabrica, preguntar=lambda: preguntas.append(1) or False,
                            cargar=lambda *a: cargas.append(a)) is False
    assert preguntas == [1] and cargas == [] and app.base_vacia(fabrica)
    assert app.ofrecer_demo(config, fabrica, preguntar=lambda: True,
                            cargar=lambda *a: cargas.append(a), hoy=lambda: HOY) is True
    assert cargas == [(config.db_path, HOY, config.admin_password)]
    fabrica.kw["bind"].dispose()


def test_no_ofrece_demo_si_ya_hay_datos(config, datos_base, fabrica):
    preguntas = []
    assert app.ofrecer_demo(config, fabrica, preguntar=lambda: preguntas.append(1)) is False
    assert preguntas == []


# ---------------------------------------------------------------- centro de control
def test_estado_del_sistema_en_la_barra_lateral(qtbot, ctx_factory):
    sin_ia = VentanaPrincipal(ctx_factory("empleado"), {})
    con_ia = VentanaPrincipal(ctx_factory("admin", cliente_llm=object()), {})
    for v in (sin_ia, con_ia):
        qtbot.addWidget(v)
    assert sin_ia.barra_ia.value() == 0 and sin_ia.etiqueta_estado_ia.text() == "Sin clave"
    assert con_ia.barra_ia.value() == 100 and con_ia.etiqueta_estado_ia.text() == "Conectada"
    assert con_ia.barra_base.value() == 100
    assert ":" in con_ia.etiqueta_actualizacion.text()  # hora de la última actualización


def test_contenido_sobre_fondo_cosmico(qtbot, ctx_factory):
    from alquiler.ui.widgets import FondoCosmico
    v = VentanaPrincipal(ctx_factory("admin"), {})
    qtbot.addWidget(v)
    assert isinstance(v.fondo, FondoCosmico) and v.fondo.isAncestorOf(v.pila)


def test_buscador_global_abre_equipos_con_el_texto(qtbot, ctx_factory, datos_base):
    v = VentanaPrincipal(ctx_factory("admin"), app.fabricas_de_vistas())
    qtbot.addWidget(v)
    v.buscador.setText("TAL-002")
    v.buscador.returnPressed.emit()
    assert v.clave_actual() == "equipos"
    assert v.vista_actual().campo_buscar.text() == "TAL-002"


def test_ejecutar_diagnostico_abre_y_lanza_el_analisis(qtbot, ctx_factory, datos_base, monkeypatch):
    from alquiler.ui.vistas.ia import VistaAnalisisIA
    lanzados = []
    monkeypatch.setattr(VistaAnalisisIA, "analizar", lambda self: lanzados.append(True))
    v = VentanaPrincipal(ctx_factory("admin"), app.fabricas_de_vistas())
    qtbot.addWidget(v)
    v.boton_diagnostico.click()
    assert v.clave_actual() == "analisis_ia" and lanzados == [True]


def test_cliente_no_ve_diagnostico(qtbot, ctx_factory):
    v = VentanaPrincipal(ctx_factory("cliente"), {})
    qtbot.addWidget(v)
    assert v.boton_diagnostico.isHidden()


def test_cambio_de_seccion_con_fundido(qtbot, ctx_factory, monkeypatch):
    from PySide6.QtCore import QAbstractAnimation
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    from alquiler.ui import animacion
    monkeypatch.setattr(animacion, "_forzado", True)
    v = VentanaPrincipal(ctx_factory("admin"), {"perfil": lambda ctx: QLabel("perfil")})
    qtbot.addWidget(v)
    v.ir_a("perfil")
    assert isinstance(v.vista_actual().graphicsEffect(), QGraphicsOpacityEffect)
    anim = v.animacion_seccion
    qtbot.waitUntil(lambda: anim.state() == QAbstractAnimation.State.Stopped, timeout=3000)
    assert v.vista_actual().graphicsEffect() is None
