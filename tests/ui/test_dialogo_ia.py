"""Diálogo y botón para conectar la IA desde la aplicación (solo administrador)."""

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit

from alquiler.ui import dialogo_ia
from alquiler.ui.logica import ia
from alquiler.ui.ventana import VentanaPrincipal


def test_dialogo_conecta_y_se_cierra(qtbot, ctx_factory, monkeypatch):
    llamadas = []
    monkeypatch.setattr(ia, "conectar_ia", lambda ctx, clave: llamadas.append(clave) or "IA OK")
    d = dialogo_ia.DialogoConectarIA(ctx_factory("admin"))
    qtbot.addWidget(d)
    assert d.campo_clave.echoMode() == QLineEdit.EchoMode.Password  # la clave no se ve
    d.campo_clave.setText("gsk_prueba")
    d.boton_conectar.click()
    qtbot.waitUntil(lambda: d.result() == QDialog.DialogCode.Accepted, timeout=5000)
    assert llamadas == ["gsk_prueba"]


def test_dialogo_explica_el_error(qtbot, ctx_factory, monkeypatch):
    from alquiler.errors import ReglaNegocioError

    def falla(ctx, clave):
        raise ReglaNegocioError("La clave de Groq no es válida o no tiene permisos.")
    monkeypatch.setattr(ia, "conectar_ia", falla)
    d = dialogo_ia.DialogoConectarIA(ctx_factory("admin"))
    qtbot.addWidget(d)
    d.campo_clave.setText("gsk_mala")
    d.boton_conectar.click()
    qtbot.waitUntil(lambda: "no es válida" in d.etiqueta_error.text(), timeout=5000)
    assert d.result() != QDialog.DialogCode.Accepted and d.boton_conectar.isEnabled()


@pytest.mark.parametrize("rol, visible", [("admin", True), ("empleado", False), ("cliente", False)])
def test_boton_conectar_ia_solo_para_admin_sin_clave(qtbot, ctx_factory, rol, visible):
    v = VentanaPrincipal(ctx_factory(rol), {})
    qtbot.addWidget(v)
    assert v.boton_conectar_ia.isVisibleTo(v) is visible


def test_al_conectar_la_ventana_muestra_la_ia_activa(qtbot, ctx_factory, monkeypatch):
    v = VentanaPrincipal(ctx_factory("admin"), {})
    qtbot.addWidget(v)

    def conectar(_self):
        v.ctx.cliente_llm = object()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(dialogo_ia.DialogoConectarIA, "exec", conectar)
    v.boton_conectar_ia.click()
    assert v.etiqueta_estado_ia.text() == "Conectada" and "conectada" in v.etiqueta_ia.text()
    assert not v.boton_conectar_ia.isVisibleTo(v)
