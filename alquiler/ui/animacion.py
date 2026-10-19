"""Animaciones de la interfaz: fundidos, entradas escalonadas, cifras que cuentan, barras que se
llenan, temblor de error y brillo neón al pasar el cursor.

Las duraciones salen de ``diseno/tokens.css`` (``--duracion-*``). Sin pantalla (pruebas,
``offscreen``) o con ``ALQUILER_ANIMACIONES=0`` no se anima nada: cada función deja el widget
en su estado final al instante y devuelve ``None``. Cuando anima, devuelve la animación (ya
iniciada), cuyo dueño es el widget: muere con él.
"""

import math
import os
import re

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QLabel, QWidget

from alquiler.ui import tema

_forzado: bool | None = None   # las pruebas lo ponen en True para ver las animaciones
_APAGADO = {"0", "no", "false", "off"}
_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+|\d+")
_CURVA = QEasingCurve.Type.OutCubic  # equivalente a --curva-salida
_RECORRIDO_CIFRAS = 3  # las cifras y barras tardan 3 × duración lenta (~1 s): se alcanzan a ver


def _sin_pantalla() -> bool:
    # sin aplicación creada, Qt informa la plataforma por defecto: manda la variable de entorno
    plataforma = (QGuiApplication.platformName() if QGuiApplication.instance()
                  else os.environ.get("QT_QPA_PLATFORM", ""))
    return plataforma.split(":")[0] in ("offscreen", "minimal")


def activas() -> bool:
    if _forzado is not None:
        return _forzado
    if os.environ.get("ALQUILER_ANIMACIONES", "").strip().lower() in _APAGADO:
        return False
    return not _sin_pantalla()


def duracion(nombre: str) -> int:
    """Milisegundos de ``--duracion-<nombre>`` (rapida, base, lenta); 0 si no hay animaciones."""
    if not activas():
        return 0
    return int(tema.TOKENS[f"--duracion-{nombre}"].strip().removesuffix("ms"))


def _iniciar(widget: QWidget, nombre: str, anim: QAbstractAnimation) -> QAbstractAnimation:
    """Una sola animación de cada tipo por widget: la nueva reemplaza a la anterior."""
    anterior = getattr(widget, nombre, None)
    if anterior is not None:
        try:
            anterior.stop()
            anterior.deleteLater()
        except RuntimeError:  # ya destruida por Qt
            pass
    setattr(widget, nombre, anim)
    anim.start()
    return anim


# ---------------------------------------------------------------- fundidos
def _copia_de_brillo(efecto):
    if not isinstance(efecto, QGraphicsDropShadowEffect):
        return None
    radio, color, desplazamiento = efecto.blurRadius(), QColor(efecto.color()), efecto.offset()

    def restaurar(widget: QWidget):
        nuevo = QGraphicsDropShadowEffect(widget)
        nuevo.setBlurRadius(radio)
        nuevo.setColor(color)
        nuevo.setOffset(desplazamiento)
        widget.setGraphicsEffect(nuevo)
    return restaurar


def fundido_entrada(widget: QWidget, retraso: int = 0, ms: int | None = None):
    """El widget aparece de transparente a opaco; al final recupera su brillo neón, si tenía."""
    if not activas():
        return None
    restaurar = _copia_de_brillo(widget.graphicsEffect())
    efecto = QGraphicsOpacityEffect(widget)
    efecto.setOpacity(0.0)
    widget.setGraphicsEffect(efecto)  # Qt admite un solo efecto: el brillo se repone al final
    grupo = QSequentialAnimationGroup(widget)
    if retraso:
        grupo.addPause(retraso)
    opacidad = QPropertyAnimation(efecto, b"opacity", grupo)
    opacidad.setDuration(ms if ms is not None else duracion("lenta"))
    opacidad.setStartValue(0.0)
    opacidad.setEndValue(1.0)
    opacidad.setEasingCurve(_CURVA)
    grupo.addAnimation(opacidad)

    def al_terminar():
        if widget.graphicsEffect() is efecto:
            if restaurar:
                restaurar(widget)
            else:
                widget.setGraphicsEffect(None)
    grupo.finished.connect(al_terminar)
    return _iniciar(widget, "_anim_fundido", grupo)


def escalonar(widgets: list[QWidget], paso: int = 70) -> list:
    """Fundido de entrada uno tras otro (cascada)."""
    grupos = [fundido_entrada(w, retraso=i * paso) for i, w in enumerate(widgets)]
    return [g for g in grupos if g is not None]


# ---------------------------------------------------------------- cifras y barras
def texto_intermedio(final: str, fraccion: float) -> str:
    """``final`` con su primera cifra al ``fraccion`` (0-1) de su valor, conservando el formato."""
    coincidencia = _NUMERO.search(final)
    if not coincidencia:
        return final
    cifra = coincidencia.group()
    valor = int(int(cifra.replace(".", "")) * fraccion + 0.5)
    texto = f"{valor:,}".replace(",", ".") if "." in cifra else str(valor)
    return final[:coincidencia.start()] + texto + final[coincidencia.end():]


def contar(etiqueta: QLabel, final: str, ms: int | None = None):
    """La cifra de la etiqueta cuenta desde 0 hasta ``final`` (que siempre queda exacto)."""
    if not activas() or not _NUMERO.search(final):
        etiqueta.setText(final)
        return None
    anim = QVariantAnimation(etiqueta)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(ms if ms is not None else duracion("lenta") * _RECORRIDO_CIFRAS)
    anim.setEasingCurve(_CURVA)
    anim.valueChanged.connect(lambda f: etiqueta.setText(texto_intermedio(final, f)))
    anim.finished.connect(lambda: etiqueta.setText(final))
    etiqueta.setText(texto_intermedio(final, 0))
    return _iniciar(etiqueta, "_anim_contar", anim)


def llenar(barra, valor: int, ms: int | None = None):
    """Una ``QProgressBar`` se llena desde su mínimo hasta ``valor``."""
    if not activas():
        barra.setValue(valor)
        return None
    anim = QPropertyAnimation(barra, b"value", barra)
    anim.setStartValue(barra.minimum())
    anim.setEndValue(valor)
    anim.setDuration(ms if ms is not None else duracion("lenta") * _RECORRIDO_CIFRAS)
    anim.setEasingCurve(_CURVA)
    barra.setValue(barra.minimum())
    return _iniciar(barra, "_anim_llenar", anim)


def temblor(widget: QWidget, amplitud: int = 9):
    """Sacudida horizontal breve (p. ej. contraseña incorrecta); vuelve a su sitio."""
    if not activas():
        return None
    x0, y0 = widget.x(), widget.y()
    anim = QVariantAnimation(widget)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(duracion("lenta") + duracion("rapida"))

    def mover(f):
        widget.move(x0 + int(amplitud * math.sin(f * math.pi * 6) * (1 - f)), y0)
    anim.valueChanged.connect(mover)
    anim.finished.connect(lambda: widget.move(x0, y0))
    return _iniciar(widget, "_anim_temblor", anim)


# ---------------------------------------------------------------- brillo al pasar el cursor
class _BrilloAlPasar(QObject):
    def __init__(self, widget: QWidget, factor: float):
        super().__init__(widget)
        self._widget = widget
        efecto = widget.graphicsEffect()
        self._radio = efecto.blurRadius() if isinstance(efecto, QGraphicsDropShadowEffect) else 24.0
        self._alfa = efecto.color().alpha() if isinstance(efecto, QGraphicsDropShadowEffect) else 40
        self._factor = factor
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._aplicar)
        widget.installEventFilter(self)

    def _aplicar(self, f):
        efecto = self._widget.graphicsEffect()
        if not isinstance(efecto, QGraphicsDropShadowEffect):
            return  # p. ej. a mitad de un fundido de entrada
        efecto.setBlurRadius(self._radio + self._radio * (self._factor - 1) * f)
        color = QColor(efecto.color())
        color.setAlpha(min(255, int(self._alfa + self._alfa * (self._factor - 1) * f)))
        efecto.setColor(color)

    def eventFilter(self, _objeto, evento):
        tipo = evento.type()
        if tipo in (QEvent.Type.Enter, QEvent.Type.Leave):
            hacia = (QAbstractAnimation.Direction.Forward if tipo == QEvent.Type.Enter
                     else QAbstractAnimation.Direction.Backward)
            if not activas():
                self._aplicar(1.0 if tipo == QEvent.Type.Enter else 0.0)
                return False
            detenida = self._anim.state() != QAbstractAnimation.State.Running
            if detenida and tipo == QEvent.Type.Leave and self._anim.currentTime() == 0:
                return False  # nunca se encendió: nada que apagar
            self._anim.setDuration(duracion("base"))
            self._anim.setDirection(hacia)
            if detenida:
                self._anim.start()
        return False


def brillo_al_pasar(widget: QWidget, factor: float = 1.9) -> None:
    """El resplandor neón del widget se intensifica mientras el cursor está encima."""
    widget._brillo_al_pasar = _BrilloAlPasar(widget, factor)
