"""Trabajo en segundo plano con QThreadPool para que la interfaz nunca se congele.

La función corre en un hilo del pool; el resultado (o el error ya traducido a un
mensaje legible) vuelve al hilo de la interfaz por señales en cola. Si el widget
dueño se destruyó mientras tanto, el resultado se descarta sin error.
"""

from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from alquiler.errors import ReglaNegocioError


class _Senales(QObject):
    terminado = Signal(object)
    fallo = Signal(str)


class _Puente(QObject):
    """Vive en el hilo GUI: las señales del worker llegan aquí en cola."""

    def __init__(self, dueno: QObject, al_terminar: Callable, al_fallar: Callable):
        super().__init__()
        self._dueno, self._al_terminar, self._al_fallar = dueno, al_terminar, al_fallar

    def _vivo(self) -> bool:
        return self._dueno is None or shiboken6.isValid(self._dueno)

    @Slot(object)
    def terminado(self, valor):
        _activas.discard(self)
        if self._vivo():
            self._al_terminar(valor)

    @Slot(str)
    def fallo(self, mensaje):
        _activas.discard(self)
        if self._vivo():
            self._al_fallar(mensaje)


class _Tarea(QRunnable):
    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self._fn = fn
        self.senales = _Senales()

    def run(self):
        try:
            resultado = self._fn()
        except ReglaNegocioError as e:
            self.senales.fallo.emit(str(e))
        except Exception as e:  # nunca un traceback en pantalla
            self.senales.fallo.emit(f"Error inesperado: {type(e).__name__}: {e}")
        else:
            self.senales.terminado.emit(resultado)


_activas: set[_Puente] = set()


def ejecutar_en_segundo_plano(fn: Callable[[], object], al_terminar: Callable[[object], None],
                              al_fallar: Callable[[str], None], dueno: QObject | None) -> None:
    puente = _Puente(dueno, al_terminar, al_fallar)
    tarea = _Tarea(fn)
    tarea.senales.terminado.connect(puente.terminado)
    tarea.senales.fallo.connect(puente.fallo)
    puente._senales = tarea.senales  # mantener vivas las señales hasta el final
    _activas.add(puente)
    QThreadPool.globalInstance().start(tarea)


def esperar_tareas(timeout_ms: int = 5000) -> bool:
    """Espera a que terminen las tareas en curso (p. ej. al cerrar la ventana)."""
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
