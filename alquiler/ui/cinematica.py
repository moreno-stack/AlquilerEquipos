"""Cinemática de arranque "encendido del sistema" (≈5,6 s, se puede saltar).

La secuencia es una línea de tiempo determinista: ``escena(t)`` dice qué se ve en el
milisegundo ``t`` y el widget solo lo pinta. Así cada fotograma se puede probar sin reloj.
"""

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QAbstractAnimation, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QDialog

from alquiler.ui import logo, tema

DURACION = 5600  # ms
TRAMOS: dict[str, tuple[int, int]] = {
    "rejilla": (0, 700),        # la rejilla en perspectiva aparece
    "red": (400, 1600),         # los nodos de la red de datos se encienden
    "cubo": (1200, 2600),       # el cubo del logo se traza arista por arista
    "nucleo": (2500, 2900),     # el núcleo de IA se enciende
    "destello": (2600, 3200),   # destello de luz (sube y baja)
    "titulo": (2800, 3800),     # el título se escribe letra por letra
    "arranque": (3200, 4800),   # líneas de arranque y barra de carga
    "fundido": (5000, 5600),    # fundido final hacia la portada
}


def tramo(nombre: str, t: float) -> float:
    """Avance (0-1) del tramo ``nombre`` en el milisegundo ``t``."""
    inicio, fin = TRAMOS[nombre]
    return min(1.0, max(0.0, (t - inicio) / (fin - inicio)))


NODOS = 48  # nodos de la red de datos
ARISTAS = 12  # aristas del cubo del logo
TITULO = "ALQUILER DE EQUIPOS"
SUBTITULO = "SISTEMA INTELIGENTE · CENTRO DE CONTROL"
PISTA = "Clic o Esc para saltar"


def orden_aristas() -> list[tuple[int, int]]:
    """Orden de trazado: primero las aristas del frente, al final las tres ocultas."""
    return [(i, j) for i, j, oculta in sorted(logo.aristas(), key=lambda a: a[2])]


@dataclass(frozen=True)
class Escena:
    """Lo que se ve en un instante de la cinemática."""

    t: float
    rejilla: float          # opacidad de la rejilla (0-1)
    nodos: int              # nodos de la red ya encendidos
    cubo: float             # aristas trazadas (0-12; la parte decimal es la que va a medias)
    nucleo: float           # brillo del núcleo de IA (0-1)
    destello: float         # destello de luz: sube y baja (0-1-0)
    titulo: str             # parte del título ya escrita
    subtitulo: str          # aparece entero cuando el título termina
    lineas: int             # líneas de arranque visibles (0-4)
    progreso: float         # barra de carga (0-1)
    fundido: float          # velo final hacia la portada (0-1)
    pista: float            # opacidad del aviso para saltar (0-1)


def escena(t: float) -> Escena:
    return Escena(
        t=t,
        rejilla=tramo("rejilla", t),
        nodos=round(NODOS * tramo("red", t)),
        cubo=ARISTAS * tramo("cubo", t),
        nucleo=tramo("nucleo", t),
        titulo=TITULO[:int(len(TITULO) * tramo("titulo", t))],
        subtitulo=SUBTITULO if tramo("titulo", t) >= 1 else "",
        lineas=min(LINEAS, int(LINEAS * tramo("arranque", t) * 1.25)),
        progreso=tramo("arranque", t),
        fundido=tramo("fundido", t),
        pista=min(1.0, max(0.0, (t - 400) / 600)) * (1 - tramo("fundido", t)),
        destello=1 - abs(2 * tramo("destello", t) - 1) if 0 < tramo("destello", t) < 1 else 0.0,
    )


LINEAS = 4


def lineas_arranque(ia_configurada: bool) -> list[tuple[str, str]]:
    """Lo que muestra el arranque; el estado de la IA es el real (no finge conexión)."""
    return [
        ("Base de datos SQLite", "OK"),
        ("Motor de IA explicable", "LISTO"),
        ("Asistente Cubi · Groq", "CLAVE CONFIGURADA" if ia_configurada else "MODO LOCAL"),
        ("Interfaz centro de control", "OK"),
    ]


GLITCH_MAX = 6  # px de separación entre las copias cian y púrpura del título


def glitch(t: float) -> int:
    """Desplazamiento del efecto glitch: a saltos mientras el título se escribe; 0 fuera."""
    if not 0 < tramo("titulo", t) < 1:
        return 0
    cuadro = int(t // 60)                       # cambia cada 60 ms, siempre igual
    ruido = (cuadro * 2654435761) % 1000 / 1000  # hash entero: sin azar entre ejecuciones
    return 0 if ruido < 0.35 else round((ruido - 0.675) / 0.325 * GLITCH_MAX)


# ---------------------------------------------------------------- el widget
CENTRO_CUBO = (0.5, 0.34)   # posición relativa del cubo
LADO_CUBO = 0.36            # fracción del lado menor de la ventana


class Cinematica(QDialog):
    """Ventana sin bordes que pinta ``escena(t)``; ``ir_a(t)`` salta a cualquier instante."""

    def __init__(self, ia_configurada: bool, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Alquiler de Equipos")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.resize(1100, 680)
        self._lineas = lineas_arranque(ia_configurada)
        azar = random.Random(11)
        self._nodos = [(azar.random(), azar.random()) for _ in range(NODOS)]
        self._escena = escena(0)
        self._reloj = QVariantAnimation(self)
        self._reloj.valueChanged.connect(self.ir_a)
        self._reloj.finished.connect(self.accept)

    def reproducir(self) -> None:
        """Avanza la línea de tiempo en tiempo real y cierra sola al terminar."""
        self._reloj.setStartValue(0.0)
        self._reloj.setEndValue(float(DURACION))
        self._reloj.setDuration(DURACION)
        self._reloj.start()

    def reproduciendo(self) -> bool:
        return self._reloj.state() == QAbstractAnimation.State.Running

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self.reproduciendo() and self.result() == 0:
            self.reproducir()

    def saltar(self) -> None:
        """Termina ya: la portada aparece sin esperar."""
        self._reloj.stop()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                            Qt.Key.Key_Space):
            self.saltar()  # Esc también continúa: nunca cancela el arranque
        else:
            super().keyPressEvent(evento)

    def mousePressEvent(self, evento):
        self.saltar()

    def ir_a(self, t: float) -> None:
        t = float(t)
        self._escena = escena(t)
        self.update()

    def escena_actual(self) -> Escena:
        return self._escena

    # ------------------------------------------------------------ pintura
    def paintEvent(self, _evento):
        e, ancho, alto = self._escena, self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), tema.qcolor("lateral"))
        self._pintar_rejilla(p, e, ancho, alto)
        self._pintar_red(p, e, ancho, alto)
        self._pintar_cubo(p, e, ancho, alto)
        self._pintar_titulo(p, e, ancho, alto)
        self._pintar_arranque(p, e, ancho, alto)
        if e.pista:
            p.setPen(tema.qcolor("deshabilitado", int(255 * e.pista)))
            p.drawText(QRectF(0, alto - 36, ancho - 24, 24),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, PISTA)
        if e.destello:
            centro = QPointF(ancho * CENTRO_CUBO[0], alto * CENTRO_CUBO[1])
            luz = QRadialGradient(centro, max(ancho, alto) * 0.8)
            luz.setColorAt(0, tema.qcolor("blanco", int(230 * e.destello)))
            luz.setColorAt(0.4, tema.qcolor("acento", int(120 * e.destello)))
            luz.setColorAt(1, tema.qcolor("acento", 0))
            p.fillRect(self.rect(), QBrush(luz))
        if e.fundido:
            p.fillRect(self.rect(), tema.qcolor("fondo", int(255 * e.fundido)))
        p.end()

    def _pintar_rejilla(self, p, e, ancho, alto):
        if not e.rejilla:
            return
        horizonte, fuga = alto * 0.55, QPointF(ancho / 2, alto * 0.55)
        p.setPen(QPen(tema.qcolor("acento", int(28 * e.rejilla)), 1))
        for k in range(-12, 13):  # líneas que convergen al punto de fuga
            p.drawLine(fuga, QPointF(ancho / 2 + k * ancho / 8, alto))
        for k in range(1, 11):    # horizontales cada vez más separadas
            y = horizonte + (alto - horizonte) * (k / 10) ** 2
            p.drawLine(QPointF(0, y), QPointF(ancho, y))
        barrido = (e.t / 900 % 1) * alto  # línea de escaneo que baja
        p.setPen(QPen(tema.qcolor("acento", int(50 * e.rejilla)), 2))
        p.drawLine(QPointF(0, barrido), QPointF(ancho, barrido))

    def _pintar_red(self, p, e, ancho, alto):
        puntos = [QPointF(x * ancho, y * alto) for x, y in self._nodos[:e.nodos]]
        limite = 0.18 * math.hypot(ancho, alto)
        for i, a in enumerate(puntos):
            for b in puntos[i + 1:]:
                d = math.hypot(a.x() - b.x(), a.y() - b.y())
                if d < limite:
                    p.setPen(QPen(tema.qcolor("acento", int(45 * (1 - d / limite))), 1))
                    p.drawLine(a, b)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tema.qcolor("acento", 150))
        for punto in puntos:
            p.drawEllipse(punto, 1.8, 1.8)

    def _pintar_cubo(self, p, e, ancho, alto):
        if not e.cubo:
            return
        lado = min(ancho, alto) * LADO_CUBO
        origen = QPointF(ancho * CENTRO_CUBO[0] - lado / 2, alto * CENTRO_CUBO[1] - lado / 2)
        vertices = [QPointF(origen.x() + x * lado, origen.y() + y * lado) for x, y in logo.vertices()]
        degradado = QLinearGradient(origen, origen + QPointF(lado, lado))
        degradado.setColorAt(0, tema.qcolor("acento"))
        degradado.setColorAt(1, tema.qcolor("secundario"))
        tocados = set()
        for k, (i, j) in enumerate(orden_aristas()):
            parte = min(1.0, e.cubo - k)
            if parte <= 0:
                break
            a, b = vertices[i], vertices[j]
            fin = a + (b - a) * parte
            for grosor, pincel in ((lado * 0.06, QBrush(tema.qcolor("acento", 50))),
                                   (lado * 0.022, QBrush(degradado))):  # halo y trazo
                p.setPen(QPen(pincel, grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(a, fin)
            tocados.add(i)
            if parte >= 1:
                tocados.add(j)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tema.qcolor("acento_hover"))
        for i in tocados:
            p.drawEllipse(vertices[i], lado * 0.03, lado * 0.03)
        if e.nucleo:
            cx, cy = logo.nucleo()
            centro = QPointF(origen.x() + cx * lado, origen.y() + cy * lado)
            radio = lado * (0.08 + 0.5 * e.destello)
            brillo = QRadialGradient(centro, radio * 2.5)
            brillo.setColorAt(0, tema.qcolor("blanco", int(255 * e.nucleo)))
            brillo.setColorAt(0.25, tema.qcolor("acento_hover", int(230 * e.nucleo)))
            brillo.setColorAt(1, tema.qcolor("acento", 0))
            p.setBrush(QBrush(brillo))
            p.drawEllipse(centro, radio * 2.5, radio * 2.5)

    def _pintar_titulo(self, p, e, ancho, alto):
        if not e.titulo:
            return
        fuente = QFont(self.font())
        fuente.setPixelSize(max(18, int(alto * 0.07)))
        fuente.setBold(True)
        fuente.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        p.setFont(fuente)
        caja = QRectF(0, alto * 0.58, ancho, alto * 0.1)
        alineacion = Qt.AlignmentFlag.AlignCenter
        desvio = glitch(e.t)
        if desvio:  # copias desplazadas cian y púrpura
            p.setPen(tema.qcolor("acento", 170))
            p.drawText(caja.translated(-desvio, 0), alineacion, e.titulo)
            p.setPen(tema.qcolor("purpura_neon", 170))
            p.drawText(caja.translated(desvio, 0), alineacion, e.titulo)
        degradado = QLinearGradient(ancho * 0.25, 0, ancho * 0.75, 0)
        degradado.setColorAt(0, tema.qcolor("acento"))
        degradado.setColorAt(1, tema.qcolor("secundario"))
        p.setPen(QPen(QBrush(degradado), 1))
        p.drawText(caja, alineacion, e.titulo)
        if e.subtitulo:
            fuente.setPixelSize(max(10, int(alto * 0.022)))
            fuente.setBold(False)
            fuente.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 140)
            p.setFont(fuente)
            p.setPen(tema.qcolor("texto_secundario"))
            p.drawText(QRectF(0, alto * 0.68, ancho, alto * 0.05), alineacion, e.subtitulo)

    def _pintar_arranque(self, p, e, ancho, alto):
        if not e.lineas and not e.progreso:
            return
        fuente = QFont("Consolas")
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        fuente.setPixelSize(max(10, int(alto * 0.02)))
        p.setFont(fuente)
        x, y, paso = ancho * 0.3, alto * 0.76, alto * 0.032
        for k, (texto, estado) in enumerate(self._lineas[:e.lineas]):
            fila = QRectF(x, y + k * paso, ancho * 0.4, paso)
            p.setPen(tema.qcolor("texto_secundario"))
            p.drawText(fila, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"> {texto}")
            p.setPen(QColor(tema.COLOR_ESTADO["En mantenimiento"][0]) if estado == "MODO LOCAL"
                     else tema.qcolor("acento"))
            p.drawText(fila, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"[ {estado} ]")
        barra = QRectF(ancho * 0.3, alto * 0.92, ancho * 0.4, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tema.qcolor("superficie_alta"))
        p.drawRoundedRect(barra, 2, 2)
        relleno = QLinearGradient(barra.topLeft(), barra.topRight())
        relleno.setColorAt(0, tema.qcolor("acento"))
        relleno.setColorAt(1, tema.qcolor("secundario"))
        p.setBrush(QBrush(relleno))
        p.drawRoundedRect(QRectF(barra.x(), barra.y(), barra.width() * e.progreso, 4), 2, 2)
