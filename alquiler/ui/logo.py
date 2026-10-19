"""Logo "cubo neural": el equipo en alquiler (un cubo de alambre neón) con la red de datos en sus
vértices y un núcleo de IA encendido en el centro.

Se dibuja con código (vector), así que es nítido en la barra de tareas y en la portada. Colores
de ``tema`` (degradado de marca cian → violeta).
"""

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from alquiler.ui import animacion, tema

_GIRO_Y, _GIRO_X = math.radians(38), math.radians(24)  # vista en tres cuartos
_MARGEN = 0.12                                         # aire para el brillo
_TAMANOS_ICONO = (16, 24, 32, 48, 64, 128, 256)


def _proyectar() -> tuple[list[tuple[float, float]], list[float]]:
    puntos, profundidades = [], []
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                # giro en Y y luego en X; proyección ortográfica
                x1 = x * math.cos(_GIRO_Y) + z * math.sin(_GIRO_Y)
                z1 = -x * math.sin(_GIRO_Y) + z * math.cos(_GIRO_Y)
                y1 = y * math.cos(_GIRO_X) - z1 * math.sin(_GIRO_X)
                z2 = y * math.sin(_GIRO_X) + z1 * math.cos(_GIRO_X)
                puntos.append((x1, -y1))
                profundidades.append(z2)
    xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
    escala = (1 - 2 * _MARGEN) / max(max(xs) - min(xs), max(ys) - min(ys))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return ([(0.5 + (px - cx) * escala, 0.5 + (py - cy) * escala) for px, py in puntos],
            profundidades)


_VERTICES, _PROFUNDIDAD = _proyectar()
_TRASERO = min(range(8), key=lambda i: _PROFUNDIDAD[i])  # el vértice más lejano
_ARISTAS = [(i, j) for i in range(8) for j in range(i + 1, 8) if bin(i ^ j).count("1") == 1]


def vertices() -> list[tuple[float, float]]:
    """Los 8 vértices proyectados, en coordenadas relativas (0-1)."""
    return list(_VERTICES)


def aristas() -> list[tuple[int, int, bool]]:
    """Las 12 aristas como (vértice, vértice, oculta)."""
    return [(i, j, _TRASERO in (i, j)) for i, j in _ARISTAS]


def nucleo() -> tuple[float, float]:
    xs, ys = zip(*_VERTICES)
    return sum(xs) / 8, sum(ys) / 8


def pintar_logo(p: QPainter, caja: QRectF, latido: float = 1.0) -> None:
    """Dibuja el logo dentro de ``caja``; ``latido`` (0-1) regula el brillo del núcleo."""
    lado = min(caja.width(), caja.height())
    origen = QPointF(caja.x() + (caja.width() - lado) / 2, caja.y() + (caja.height() - lado) / 2)

    def punto(rel):
        return QPointF(origen.x() + rel[0] * lado, origen.y() + rel[1] * lado)

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    degradado = QLinearGradient(punto((0.1, 0.1)), punto((0.9, 0.9)))
    degradado.setColorAt(0, tema.qcolor("acento"))
    degradado.setColorAt(1, tema.qcolor("secundario"))
    grueso = max(1.2, lado * 0.05)
    centro = punto(nucleo())

    # 1. halo del núcleo (detrás de todo)
    if lado >= 24:
        halo = QRadialGradient(centro, lado * 0.42)
        halo.setColorAt(0, tema.qcolor("acento", int(90 * latido)))
        halo.setColorAt(1, tema.qcolor("acento", 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(centro, lado * 0.42, lado * 0.42)
    # 2. sinapsis: del núcleo a cada vértice (la red)
    if lado >= 32:
        p.setPen(QPen(tema.qcolor("secundario_claro", 70), max(0.8, lado * 0.012)))
        for v in _VERTICES:
            p.drawLine(centro, punto(v))
    # 3. aristas ocultas, tenues; luego las visibles con el degradado
    for i, j, oculta in aristas():
        if oculta:
            p.setPen(QPen(tema.qcolor("acento", 70), max(0.8, grueso * 0.45), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(punto(_VERTICES[i]), punto(_VERTICES[j]))
    p.setPen(QPen(QBrush(degradado), grueso, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    for i, j, oculta in aristas():
        if not oculta:
            p.drawLine(punto(_VERTICES[i]), punto(_VERTICES[j]))
    # 4. nodos en los vértices
    if lado >= 24:
        p.setPen(Qt.PenStyle.NoPen)
        for k, v in enumerate(_VERTICES):
            radio = lado * (0.028 if k == _TRASERO else 0.045)
            p.setBrush(tema.qcolor("acento_hover" if k % 2 else "secundario_claro"))
            p.drawEllipse(punto(v), radio, radio)
    # 5. núcleo de IA
    radio = lado * (0.07 + 0.03 * latido)
    brillo = QRadialGradient(centro, radio)
    brillo.setColorAt(0, tema.qcolor("blanco"))
    brillo.setColorAt(0.45, tema.qcolor("acento_hover"))
    brillo.setColorAt(1, tema.qcolor("acento", 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(brillo))
    p.drawEllipse(centro, radio, radio)
    p.restore()


def pixmap_logo(lado: int, latido: float = 1.0) -> QPixmap:
    imagen = QPixmap(lado, lado)
    imagen.fill(Qt.GlobalColor.transparent)
    p = QPainter(imagen)
    pintar_logo(p, QRectF(0, 0, lado, lado), latido)
    p.end()
    return imagen


def icono_app() -> QIcon:
    icono = QIcon()
    for lado in _TAMANOS_ICONO:
        icono.addPixmap(pixmap_logo(lado))
    return icono


class Logo(QWidget):
    """El logo como widget; con animaciones, el núcleo late suave sin parar."""

    def __init__(self, lado: int = 64, parent=None):
        super().__init__(parent)
        self.setFixedSize(lado, lado)
        self.latido = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(1.0)
        self._anim.setKeyValueAt(0.5, 0.35)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._latir)

    def animado(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    def _latir(self, valor):
        self.latido = float(valor)
        self.update()

    def showEvent(self, evento):
        if animacion.activas() and not self.animado():
            self._anim.setDuration(animacion.duracion("lenta") * 8)  # ~2,5 s por latido
            self._anim.start()
        super().showEvent(evento)

    def hideEvent(self, evento):
        self._anim.stop()
        self.latido = 1.0
        super().hideEvent(evento)

    def paintEvent(self, _evento):
        p = QPainter(self)
        pintar_logo(p, QRectF(self.rect()), self.latido)
        p.end()
