"""Transición de inicio de sesión: de la portada al tablero (≈2,8 s, se puede saltar).

Igual que la cinemática de arranque, es una línea de tiempo determinista: ``escena(t)`` dice
qué se ve en el milisegundo ``t`` y la ventana solo lo pinta.
"""

import math
from dataclasses import dataclass

from PySide6.QtCore import QAbstractAnimation, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QDialog

from alquiler.ui import logo, tema

DURACION = 2800  # ms
TRAMOS: dict[str, tuple[int, int]] = {
    "anillo": (0, 700),         # un anillo de escaneo recorre el logo
    "saludo": (250, 900),       # "Hola, <nombre>" se escribe letra por letra
    "pasos": (800, 2000),       # las verificaciones aparecen una tras otra
    "progreso": (800, 2200),    # barra de carga
    "fundido": (2300, 2800),    # el logo se acerca y todo se funde hacia el tablero
}
PASOS = 4


def tramo(nombre: str, t: float) -> float:
    """Avance (0-1) del tramo ``nombre`` en el milisegundo ``t``."""
    inicio, fin = TRAMOS[nombre]
    return min(1.0, max(0.0, (t - inicio) / (fin - inicio)))


@dataclass(frozen=True)
class Escena:
    t: float
    anillo: float     # vuelta del anillo de escaneo (0-1)
    saludo: str       # parte del saludo ya escrita
    pasos: int        # verificaciones visibles
    progreso: float   # barra de carga (0-1)
    fundido: float    # acercamiento y velo final (0-1)


def escena(t: float, nombre: str) -> Escena:
    saludo = f"Hola, {nombre}"
    return Escena(
        t=t,
        anillo=tramo("anillo", t),
        saludo=saludo[:round(len(saludo) * tramo("saludo", t))],
        pasos=min(PASOS, int(PASOS * tramo("pasos", t) * 1.2)),
        progreso=tramo("progreso", t),
        fundido=tramo("fundido", t),
    )


_ROLES = {"admin": "ADMINISTRADOR", "empleado": "EMPLEADO", "cliente": "CLIENTE"}


def pasos_sesion(rol: str, secciones: int, ia_configurada: bool) -> list[tuple[str, str]]:
    """Verificaciones que se muestran; todas describen el estado real (nada se finge)."""
    return [
        ("Identidad verificada", _ROLES.get(rol, rol.upper())),
        ("Permisos del rol", f"{secciones} {'SECCIÓN' if secciones == 1 else 'SECCIONES'}"),
        ("Asistente Cubi", "GROQ" if ia_configurada else "MODO LOCAL"),
        ("Tablero de control", "LISTO"),
    ]


# ---------------------------------------------------------------- la ventana
class TransicionSesion(QDialog):
    """Ventana sin bordes que pinta ``escena(t)`` con los datos de quien inició sesión."""

    def __init__(self, nombre: str, rol: str, secciones: int, ia_configurada: bool, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Alquiler de Equipos")
        self.resize(1280, 800)
        self._nombre = nombre.split()[0] if nombre.strip() else nombre
        self._pasos = pasos_sesion(rol, secciones, ia_configurada)
        self._escena = escena(0, self._nombre)
        self._reloj = QVariantAnimation(self)
        self._reloj.valueChanged.connect(self.ir_a)
        self._reloj.finished.connect(self.accept)

    def reproducir(self) -> None:
        """Avanza la línea de tiempo en tiempo real y cierra sola al terminar."""
        self._reloj.setStartValue(0.0)
        self._reloj.setEndValue(float(DURACION))
        self._reloj.setDuration(int(DURACION))
        self._reloj.start()

    def reproduciendo(self) -> bool:
        return self._reloj.state() == QAbstractAnimation.State.Running

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self.reproduciendo() and self.result() == 0:
            self.reproducir()

    def ir_a(self, t: float) -> None:
        self._escena = escena(min(float(t), DURACION), self._nombre)
        self.update()

    def escena_actual(self) -> Escena:
        return self._escena

    def paintEvent(self, _evento):
        e, ancho, alto = self._escena, self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), tema.qcolor("fondo"))
        aurora = QRadialGradient(QPointF(ancho / 2, alto * 0.38), max(ancho, alto) * 0.6)
        aurora.setColorAt(0, tema.qcolor("acento", 40))
        aurora.setColorAt(1, tema.qcolor("acento", 0))
        p.fillRect(self.rect(), QBrush(aurora))
        self._pintar_logo(p, e, ancho, alto)
        self._pintar_saludo(p, e, ancho, alto)
        self._pintar_pasos(p, e, ancho, alto)
        if e.fundido:
            p.fillRect(self.rect(), tema.qcolor("fondo", int(255 * e.fundido)))
        p.end()

    def _pintar_logo(self, p, e, ancho, alto):
        lado = min(ancho, alto) * 0.2 * (1 + 1.5 * e.fundido)  # se acerca al final
        centro = QPointF(ancho / 2, alto * 0.32)
        caja = QRectF(centro.x() - lado / 2, centro.y() - lado / 2, lado, lado)
        logo.pintar_logo(p, caja, latido=0.6 + 0.4 * math.sin(e.t / 160) ** 2)
        if e.anillo > 0:
            radio = lado * 0.72
            arco = QRectF(centro.x() - radio, centro.y() - radio, 2 * radio, 2 * radio)
            for grosor, alfa in ((10, 50), (3, 220)):
                p.setPen(QPen(tema.qcolor("acento", int(alfa * (1 - e.fundido))), grosor,
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(arco, 90 * 16, -int(360 * 16 * e.anillo))

    def _pintar_saludo(self, p, e, ancho, alto):
        if not e.saludo:
            return
        fuente = QFont(self.font())
        fuente.setPixelSize(max(18, int(alto * 0.055)))
        fuente.setBold(True)
        p.setFont(fuente)
        degradado = QLinearGradient(ancho * 0.3, 0, ancho * 0.7, 0)
        degradado.setColorAt(0, tema.qcolor("acento"))
        degradado.setColorAt(1, tema.qcolor("secundario"))
        p.setPen(QPen(QBrush(degradado), 1))
        p.drawText(QRectF(0, alto * 0.5, ancho, alto * 0.09), Qt.AlignmentFlag.AlignCenter, e.saludo)

    def _pintar_pasos(self, p, e, ancho, alto):
        fuente = QFont("Consolas")
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        fuente.setPixelSize(max(11, int(alto * 0.02)))
        p.setFont(fuente)
        x, y, paso = ancho * 0.32, alto * 0.63, alto * 0.04
        for k, (texto, estado) in enumerate(self._pasos[:e.pasos]):
            fila = QRectF(x, y + k * paso, ancho * 0.36, paso)
            p.setPen(tema.qcolor("texto_secundario"))
            p.drawText(fila, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"✓ {texto}")
            p.setPen(tema.qcolor("acento"))
            p.drawText(fila, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, estado)
        barra = QRectF(ancho * 0.32, alto * 0.82, ancho * 0.36, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tema.qcolor("superficie_alta"))
        p.drawRoundedRect(barra, 2, 2)
        relleno = QLinearGradient(barra.topLeft(), barra.topRight())
        relleno.setColorAt(0, tema.qcolor("acento"))
        relleno.setColorAt(1, tema.qcolor("secundario"))
        p.setBrush(QBrush(relleno))
        p.drawRoundedRect(QRectF(barra.x(), barra.y(), barra.width() * e.progreso, 4), 2, 2)
