"""Piezas visuales del "centro de control": fondo cósmico, paneles de vidrio, brillo neón, gráficos
y título con degradado.

Todos los colores salen de ``tema`` (y este, de ``diseno/tokens.css``). Solo pintan: no leen
datos ni conocen la lógica; la vista les entrega números ya calculados.
"""

import math
import random

from PySide6.QtCharts import (
    QAreaSeries,
    QBarCategoryAxis,
    QChart,
    QChartView,
    QSplineSeries,
    QValueAxis,
)
from PySide6.QtCore import QEasingCurve, QElapsedTimer, QMargins, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from alquiler.ui import animacion, tema

_SEMILLA = 7          # el fondo es siempre el mismo dibujo
_NODOS = 64
_DISTANCIA_ENLACE = 0.16  # fracción de la diagonal
_DERIVA = 0.012            # cuánto flota cada nodo (fracción de la ventana)
_CADA_PULSO = 5           # uno de cada 5 nodos late


def aplicar_brillo(widget: QWidget, clave_color: str = "acento", alfa: int = 70, radio: int = 32) -> None:
    """Resplandor neón suave alrededor del widget (sombra difusa de color, sin desplazamiento)."""
    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(radio)
    efecto.setOffset(0, 0)
    efecto.setColor(tema.qcolor(clave_color, alfa))
    widget.setGraphicsEffect(efecto)


class FondoCosmico(QWidget):
    """Fondo de "red de datos": degradado medianoche, auroras y nodos enlazados por líneas tenues.

    Con animaciones, los nodos flotan despacio y algunos laten; el reloj solo corre mientras el
    fondo está visible (``fps`` cuadros por segundo).
    """

    def __init__(self, parent=None, fps: int = 24):
        super().__init__(parent)
        azar = random.Random(_SEMILLA)
        # posiciones relativas (0-1): el dibujo escala con la ventana sin cambiar de forma
        self._relativos = [(azar.random(), azar.random(), azar.choice((1.2, 1.6, 2.2)))
                           for _ in range(_NODOS)]
        movimiento = random.Random(_SEMILLA + 1)  # aparte: no altera la forma de la red
        self._ritmos = [(movimiento.uniform(0.00025, 0.0006), movimiento.uniform(0, math.tau))
                        for _ in range(_NODOS)]
        self._t = 0
        self._cronometro = QElapsedTimer()
        self._reloj = QTimer(self)
        self._reloj.setInterval(max(1, 1000 // fps))
        self._reloj.timeout.connect(self._avanzar)

    def nodos(self) -> list[tuple[float, float, float]]:
        return list(self._relativos)

    def posiciones(self, t_ms: float) -> list[tuple[float, float]]:
        """Posición relativa de cada nodo a los ``t_ms`` milisegundos (determinista)."""
        return [(x + _DERIVA * math.sin(t_ms * w + fase), y + _DERIVA * math.cos(t_ms * w * 0.8 + fase))
                for (x, y, _), (w, fase) in zip(self._relativos, self._ritmos)]

    def animado(self) -> bool:
        return self._reloj.isActive()

    def _avanzar(self):
        self._t = self._cronometro.elapsed()
        self.update()

    def showEvent(self, evento):
        if animacion.activas() and not self._reloj.isActive():
            if not self._cronometro.isValid():
                self._cronometro.start()
            self._reloj.start()
        super().showEvent(evento)

    def hideEvent(self, evento):
        self._reloj.stop()
        super().hideEvent(evento)

    def paintEvent(self, _evento):
        ancho, alto = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), tema.qcolor("fondo"))
        for (cx, cy, radio, clave, alfa) in ((0.15, -0.1, 0.75, "acento", 46),
                                             (0.95, 0.05, 0.65, "purpura_neon", 42),
                                             (0.55, 1.15, 0.7, "azul_electrico", 30)):
            gradiente = QRadialGradient(QPointF(cx * ancho, cy * alto), radio * max(ancho, alto))
            gradiente.setColorAt(0, tema.qcolor(clave, alfa))
            gradiente.setColorAt(1, tema.qcolor(clave, 0))
            p.fillRect(self.rect(), QBrush(gradiente))
        puntos = [QPointF(x * ancho, y * alto) for x, y in self.posiciones(self._t)]
        limite = _DISTANCIA_ENLACE * math.hypot(ancho, alto)
        for i, a in enumerate(puntos):
            for b in puntos[i + 1:]:
                d = math.hypot(a.x() - b.x(), a.y() - b.y())
                if d < limite:
                    p.setPen(QPen(tema.qcolor("acento", int(38 * (1 - d / limite))), 1))
                    p.drawLine(a, b)
        p.setPen(Qt.PenStyle.NoPen)
        for i, (punto, (_, _, r), (w, fase)) in enumerate(zip(puntos, self._relativos, self._ritmos)):
            latido = max(0.0, math.sin(self._t * w * 4 + fase)) if i % _CADA_PULSO == 0 else 0.0
            if latido:  # halo del nodo que late
                p.setBrush(tema.qcolor("acento", int(40 * latido)))
                p.drawEllipse(punto, r * 4 * latido + r, r * 4 * latido + r)
            p.setBrush(tema.qcolor("acento", 90 + int(120 * latido)))
            p.drawEllipse(punto, r, r)
        p.end()


class Panel(QFrame):
    """Panel de vidrio esmerilado con título y subtítulo; el contenido va en ``capa``."""

    def __init__(self, titulo: str, subtitulo: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("panelVidrio")
        self.capa = QVBoxLayout(self)
        self.capa.setContentsMargins(18, 16, 18, 16)
        self.capa.setSpacing(10)
        self.etiqueta_titulo = QLabel(titulo)
        self.etiqueta_titulo.setObjectName("tituloPanel")
        self.etiqueta_subtitulo = QLabel(subtitulo)
        self.etiqueta_subtitulo.setObjectName("subtituloPanel")
        self.etiqueta_subtitulo.setVisible(bool(subtitulo))
        cabecera = QVBoxLayout()
        cabecera.setSpacing(0)
        cabecera.addWidget(self.etiqueta_titulo)
        cabecera.addWidget(self.etiqueta_subtitulo)
        self.capa.addLayout(cabecera)


class GraficoDona(QWidget):
    """Gráfico circular hueco con un valor grande al centro (p. ej. "40 %" de utilización)."""

    _GROSOR = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conteos: list[tuple[str, int]] = []
        self.texto_centro = self.subtexto_centro = ""
        self.progreso = 1.0  # 0-1: fracción del círculo ya dibujada (anima la entrada)
        self._anim = None
        self.setMinimumSize(180, 180)
        self.setMaximumHeight(230)

    def cargar(self, conteos: list[tuple[str, int]], texto_centro: str, subtexto_centro: str) -> None:
        self._conteos = list(conteos)
        self.texto_centro, self.subtexto_centro = texto_centro, subtexto_centro
        if self._anim is not None:
            self._anim.stop()
        if animacion.activas():
            self.progreso = 0.0
            self._anim = QVariantAnimation(self)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setDuration(animacion.duracion("lenta") * 3)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.valueChanged.connect(self._avanzar)
            self._anim.finished.connect(lambda: self._avanzar(1.0))
            self._anim.start()
        else:
            self.progreso = 1.0
        self.update()

    def _avanzar(self, valor):
        self.progreso = float(valor)
        self.update()

    def segmentos(self) -> list[tuple[str, int, str]]:
        return [(estado, n, tema.COLOR_ESTADO[estado][0]) for estado, n in self._conteos if n]

    def vacia(self) -> bool:
        return not self.segmentos()

    def paintEvent(self, _evento):
        lado = min(self.width(), self.height()) - self._GROSOR - 4
        caja = QRectF((self.width() - lado) / 2, (self.height() - lado) / 2, lado, lado)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tema.qcolor("superficie_alta"), self._GROSOR, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.FlatCap))
        p.drawEllipse(caja)
        segmentos = self.segmentos()
        total = sum(n for _, n, _ in segmentos)
        angulo = int((90 + 120 * (1 - self.progreso)) * 16)  # 1/16 de grado; gira al entrar
        separacion = 2 * 16 if len(segmentos) > 1 else 0
        for _, n, color in segmentos:
            barrido = int(-360 * 16 * n / total * self.progreso)
            p.setPen(QPen(QColor(color), self._GROSOR, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(caja, angulo - separacion // 2, barrido + separacion)
            angulo += barrido
        p.setPen(tema.qcolor("texto"))
        fuente = QFont(self.font())
        fuente.setPointSizeF(max(14.0, lado / 7.5))
        fuente.setBold(True)
        p.setFont(fuente)
        p.drawText(caja.adjusted(0, -lado * 0.12, 0, -lado * 0.12), Qt.AlignmentFlag.AlignCenter,
                   self.texto_centro)
        fuente.setPointSizeF(8.5)
        fuente.setBold(False)
        p.setFont(fuente)
        p.setPen(tema.qcolor("texto_secundario"))
        p.drawText(caja.adjusted(0, lado * 0.18, 0, lado * 0.18), Qt.AlignmentFlag.AlignCenter,
                   self.subtexto_centro)
        p.end()


class GraficoTendencia(QChartView):
    """Líneas suaves con área luminosa bajo la primera serie, sobre fondo transparente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categorias: list[str] = []
        self._series: list[tuple[str, list[int]]] = []
        # QAreaSeries guarda punteros a sus líneas base pero no se adueña de ellas: hay que
        # mantenerlas vivas mientras el gráfico exista (si no, Qt lee memoria liberada).
        self._vivos: list = []
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedHeight(260)

    def categorias(self) -> list[str]:
        return list(self._categorias)

    def series_datos(self) -> list[tuple[str, list[int]]]:
        return [(nombre, list(valores)) for nombre, valores in self._series]

    def cargar(self, categorias: list[str], series: list[tuple[str, list[int], str]]) -> None:
        self._categorias = list(categorias)
        self._series = [(nombre, list(valores)) for nombre, valores, _ in series]
        vivos: list = []
        grafico = QChart()
        grafico.setBackgroundVisible(False)
        grafico.setPlotAreaBackgroundVisible(False)
        grafico.setMargins(QMargins(0, 0, 0, 0))
        if animacion.activas():  # las líneas crecen desde el eje
            grafico.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
            grafico.setAnimationDuration(animacion.duracion("lenta") * 3)
        else:
            grafico.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        leyenda = grafico.legend()
        leyenda.setAlignment(Qt.AlignmentFlag.AlignTop)
        leyenda.setLabelColor(tema.qcolor("texto_secundario"))
        eje_x = QBarCategoryAxis()
        eje_x.append(self._categorias)
        maximo = max([1] + [max(v) for _, v, _ in series if v])
        eje_y = QValueAxis()
        eje_y.setRange(0, math.ceil(maximo * 1.25))
        eje_y.setLabelFormat("%d")
        eje_y.setTickCount(5)
        for eje in (eje_x, eje_y):
            eje.setLabelsColor(tema.qcolor("texto_secundario"))
            eje.setGridLineColor(tema.qcolor("rejilla"))
            eje.setLinePen(QPen(tema.qcolor("rejilla")))
        grafico.addAxis(eje_x, Qt.AlignmentFlag.AlignBottom)
        grafico.addAxis(eje_y, Qt.AlignmentFlag.AlignLeft)
        for i, (nombre, valores, clave) in enumerate(series):
            linea = QSplineSeries()
            linea.setName(nombre)
            for x, v in enumerate(valores):
                linea.append(x + 0.5, v)  # centrado en cada categoría
            linea.setPen(QPen(tema.qcolor(clave), 3))
            if i == 0:  # área luminosa bajo la serie principal
                base = QSplineSeries()
                for x in range(len(valores)):
                    base.append(x + 0.5, 0)
                vivos += [linea, base]
                area = QAreaSeries(linea, base)
                area.setName(nombre)
                brillo = QLinearGradient(0, 0, 0, 1)
                brillo.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                brillo.setColorAt(0, tema.qcolor(clave, 90))
                brillo.setColorAt(1, tema.qcolor(clave, 0))
                area.setBrush(QBrush(brillo))
                area.setPen(QPen(tema.qcolor(clave), 3))
                serie_visible = area
            else:
                serie_visible = linea
            grafico.addSeries(serie_visible)
            for marcador in leyenda.markers(serie_visible):  # leyenda con el color de la línea
                marcador.setBrush(QBrush(tema.qcolor(clave)))
                marcador.setPen(QPen(tema.qcolor(clave)))
            serie_visible.attachAxis(eje_y)
            # el eje X de categorías va de 0 a n; un eje numérico oculto alinea los puntos
            eje_num = QValueAxis()
            eje_num.setRange(0, max(1, len(valores)))
            eje_num.setVisible(False)
            grafico.addAxis(eje_num, Qt.AlignmentFlag.AlignBottom)
            serie_visible.attachAxis(eje_num)
        anterior = self.chart()
        self.setChart(grafico)
        self._vivos = [grafico, *vivos]
        if anterior is not None:
            anterior.deleteLater()


class TextoDegradado(QLabel):
    """Etiqueta cuyo texto se pinta con el degradado de marca (cian → violeta)."""

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        degradado = QLinearGradient(0, 0, max(1, self.width()), 0)
        degradado.setColorAt(0, tema.qcolor("acento"))
        degradado.setColorAt(1, tema.qcolor("secundario"))
        p.setPen(QPen(QBrush(degradado), 1))
        p.setFont(self.font())
        p.drawText(self.contentsRect(), self.alignment(), self.text())
        p.end()
