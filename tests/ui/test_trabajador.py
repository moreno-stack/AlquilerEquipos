"""Trabajo en segundo plano: la UI no se congela y los resultados vuelven al hilo GUI."""

import threading

from PySide6.QtCore import QThread
from sqlalchemy import text
from PySide6.QtWidgets import QApplication, QWidget

from alquiler.errors import ReglaNegocioError
from alquiler.ui import trabajador


def test_trabajador_entrega_resultado_en_hilo_gui(qtbot):
    dueno = QWidget()
    qtbot.addWidget(dueno)
    hilos = {}
    recibido = []

    def trabajo():
        hilos["trabajo"] = threading.get_ident()
        return 42

    def al_terminar(valor):
        hilos["callback_es_gui"] = QThread.currentThread() is QApplication.instance().thread()
        recibido.append(valor)

    trabajador.ejecutar_en_segundo_plano(trabajo, al_terminar, recibido.append, dueno)
    qtbot.waitUntil(lambda: bool(recibido), timeout=3000)
    assert recibido == [42]
    assert hilos["trabajo"] != threading.get_ident()   # corrió fuera del hilo GUI
    assert hilos["callback_es_gui"] is True             # pero el resultado volvió al GUI


def test_trabajador_traduce_errores(qtbot):
    dueno = QWidget()
    qtbot.addWidget(dueno)
    errores = []

    def regla():
        raise ReglaNegocioError("El equipo no está disponible.")

    def bug():
        raise KeyError("x")

    trabajador.ejecutar_en_segundo_plano(regla, lambda _: None, errores.append, dueno)
    trabajador.ejecutar_en_segundo_plano(bug, lambda _: None, errores.append, dueno)
    qtbot.waitUntil(lambda: len(errores) == 2, timeout=3000)
    assert "El equipo no está disponible." in errores
    assert "Error inesperado: KeyError: 'x'" in errores


def test_trabajador_accede_a_la_base_desde_otro_hilo(qtbot, ctx_factory, datos_base):
    ctx = ctx_factory("admin")
    dueno = QWidget()
    qtbot.addWidget(dueno)
    recibido = []
    trabajador.ejecutar_en_segundo_plano(
        lambda: ctx.ejecutar(lambda s, a: s.execute(text("SELECT count(*) FROM equipo")).scalar()),
        recibido.append, recibido.append, dueno)
    qtbot.waitUntil(lambda: bool(recibido), timeout=3000)
    assert recibido == [2]


def test_dueno_destruido_no_recibe_callback(qtbot):
    dueno = QWidget()
    llamado = []
    evento = threading.Event()

    def trabajo():
        evento.wait(2)
        return 1

    trabajador.ejecutar_en_segundo_plano(trabajo, llamado.append, llamado.append, dueno)
    dueno.deleteLater()
    qtbot.wait(50)
    evento.set()
    trabajador.esperar_tareas()
    qtbot.wait(100)
    assert llamado == []
