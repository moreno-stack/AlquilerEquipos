"""Vista de reportes: KPIs, ingresos por mes, uso de flota y morosidad.

Gráficos según la guía de visualización: una sola serie por gráfico (un tono, sin
leyenda; el título la nombra), rejilla tenue, tooltip al pasar el cursor y una
tabla con los mismos datos al lado.
"""

from datetime import date, timedelta

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QLocale, QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import tema, trabajador, widgets
from alquiler.ui.logica import reportes
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import pesos

SERIE = QColor(tema.PALETA["acento"])  # cian de la marca sobre la superficie oscura
TINTA_SECUNDARIA = QColor(tema.PALETA["texto_secundario"])
REJILLA = QColor(tema.PALETA["rejilla"])

COLUMNAS_USO = [("codigo", "Código"), ("nombre", "Equipo"), ("categoria", "Categoría"),
                ("dias", "Días alquilado"), ("porcentaje", "% del período")]
COLUMNAS_VENCIDOS = [("cliente", "Cliente"), ("equipo", "Equipo"), ("dias", "Días vencido"),
                     ("mora", "Mora estimada")]


def _grafico(titulo: str) -> QChartView:
    chart = QChart()
    chart.setTitle(titulo)
    chart.setTitleFont(QFont("", 11, QFont.Weight.DemiBold))
    chart.legend().hide()  # una sola serie: el título la nombra
    chart.setBackgroundRoundness(10)
    chart.setBackgroundBrush(QColor(tema.PALETA["superficie"]))
    chart.setBackgroundPen(QPen(QColor(tema.PALETA["borde"])))
    chart.setTitleBrush(QColor(tema.PALETA["texto"]))
    chart.setMargins(QMargins(6, 6, 6, 6))
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    chart.setLocalizeNumbers(True)  # coma decimal, como el resto de la aplicación
    chart.setLocale(QLocale(QLocale.Language.Spanish, QLocale.Country.Colombia))
    vista = QChartView(chart)
    vista.setStyleSheet("background: transparent; border: none;")
    vista.setRenderHint(QPainter.RenderHint.Antialiasing)
    vista.setMinimumHeight(260)
    return vista


def _eje_recesivo(eje) -> None:
    eje.setLabelsColor(TINTA_SECUNDARIA)
    eje.setGridLineColor(REJILLA)
    eje.setLinePen(REJILLA)


class VistaReportes(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        hoy = ctx.hoy()
        inicio = hoy.replace(day=1)
        for _ in range(5):
            inicio = (inicio - timedelta(days=1)).replace(day=1)
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado("Reportes", "Ingresos, uso de la flota y morosidad."))

        filtros = QHBoxLayout()
        self.campo_desde = self._fecha(inicio)
        self.campo_hasta = self._fecha(hoy)
        self.boton_generar = widgets.boton("Generar", "primario", self.generar)
        self.etiqueta_estado = QLabel()
        self.etiqueta_estado.setObjectName("subtituloVista")
        for w in (QLabel("Desde"), self.campo_desde, QLabel("Hasta"), self.campo_hasta,
                  self.boton_generar, self.etiqueta_estado):
            filtros.addWidget(w)
        filtros.addStretch()
        capa.addLayout(filtros)

        fila_kpis = QGridLayout()
        self.kpis: dict[str, QLabel] = {}
        for i, titulo in enumerate(["Ingresos del período", "Por alquiler", "Por mora", "Por daños",
                                    "Devoluciones tardías", "Alquileres vencidos hoy"]):
            tarjeta = QFrame()
            tarjeta.setObjectName("kpi")
            caja = QVBoxLayout(tarjeta)
            etiqueta = QLabel(titulo.upper())
            etiqueta.setObjectName("kpiTitulo")
            valor = QLabel("—")
            valor.setObjectName("kpiValor")
            caja.addWidget(etiqueta)
            caja.addWidget(valor)
            self.kpis[titulo] = valor
            fila_kpis.addWidget(tarjeta, 0, i)
        capa.addLayout(fila_kpis)

        graficos = QHBoxLayout()
        self.grafico_ingresos = _grafico("Ingresos por mes (COP)")
        self.grafico_categorias = _grafico("Uso de la flota por categoría")
        graficos.addWidget(self.grafico_ingresos, 3)
        graficos.addWidget(self.grafico_categorias, 2)
        capa.addLayout(graficos, 2)

        pestanas = QTabWidget()
        self.tabla_uso = widgets.Tabla()
        self.tabla_vencidos = widgets.Tabla()
        pestanas.addTab(self.tabla_uso, "Uso por equipo")
        pestanas.addTab(self.tabla_vencidos, "Alquileres vencidos")
        capa.addWidget(pestanas, 2)
        self.generar()

    def _fecha(self, valor: date) -> QDateEdit:
        campo = QDateEdit(QDate(valor))
        campo.setCalendarPopup(True)
        campo.setDisplayFormat("dd/MM/yyyy")
        return campo

    # ---------------------------------------------------------------- generación
    def generar(self):
        desde, hasta = self.campo_desde.date().toPython(), self.campo_hasta.date().toPython()
        self.boton_generar.setEnabled(False)
        self.etiqueta_estado.setText("Generando…")
        trabajador.ejecutar_en_segundo_plano(
            lambda: reportes.generar(self.ctx, desde, hasta), self._mostrar, self._fallo, self)

    def _fallo(self, mensaje: str):
        self.boton_generar.setEnabled(True)
        self.etiqueta_estado.setText("")
        widgets.mostrar_error(self, mensaje)

    def _mostrar(self, datos: dict):
        for titulo, valor in datos["kpis"]:
            self.kpis[titulo].setText(valor)
        self._dibujar_ingresos(datos["ingresos_mes"])
        self._dibujar_categorias(datos["uso_categorias"])
        self.tabla_uso.cargar(COLUMNAS_USO, datos["uso_equipos"])
        self.tabla_vencidos.cargar(COLUMNAS_VENCIDOS, datos["vencidos"])
        self.boton_generar.setEnabled(True)
        self.etiqueta_estado.setText("")

    def _dibujar_ingresos(self, meses: list[tuple[str, int]]):
        chart = self.grafico_ingresos.chart()
        chart.removeAllSeries()
        for eje in chart.axes():
            chart.removeAxis(eje)
        barras = QBarSet("Ingresos")
        barras.setColor(SERIE)
        barras.setBorderColor(SERIE)
        for _, monto in meses:
            barras.append(monto / 1_000_000)
        etiquetas = [m for m, _ in meses]
        parcial = any(m.endswith("*") for m in etiquetas)
        chart.setTitle("Ingresos por mes (COP)" + ("  ·  * mes parcial" if parcial else ""))
        barras.hovered.connect(lambda dentro, i: QToolTip.showText(
            QCursor.pos(), f"{etiquetas[i]}: {pesos(meses[i][1])}") if dentro else QToolTip.hideText())
        serie = QBarSeries()
        serie.setBarWidth(0.6)
        serie.append(barras)
        chart.addSeries(serie)
        eje_x = QBarCategoryAxis()
        eje_x.append(etiquetas)
        eje_y = QValueAxis()
        eje_y.setLabelFormat("%.1f M")
        eje_y.setMin(0)
        eje_y.setMax(max([m / 1_000_000 for _, m in meses] + [0.1]) * 1.15)
        eje_y.applyNiceNumbers()
        for eje, lado in ((eje_x, Qt.AlignmentFlag.AlignBottom), (eje_y, Qt.AlignmentFlag.AlignLeft)):
            _eje_recesivo(eje)
            chart.addAxis(eje, lado)
            serie.attachAxis(eje)
        eje_x.setGridLineVisible(False)

    def _dibujar_categorias(self, categorias: list[tuple[str, float]]):
        chart = self.grafico_categorias.chart()
        chart.removeAllSeries()
        for eje in chart.axes():
            chart.removeAxis(eje)
        orden = list(reversed(categorias))  # el mayor queda arriba
        barras = QBarSet("Uso")
        barras.setColor(SERIE)
        barras.setBorderColor(SERIE)
        for _, pct in orden:
            barras.append(pct)
        barras.hovered.connect(lambda dentro, i: QToolTip.showText(
            QCursor.pos(), f"{orden[i][0]}: {orden[i][1]:.1f} %".replace(".", ","))
            if dentro else QToolTip.hideText())
        serie = QHorizontalBarSeries()
        serie.setBarWidth(0.6)
        serie.append(barras)
        serie.setLabelsVisible(True)
        serie.setLabelsFormat("@value %")
        serie.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsOutsideEnd)
        barras.setLabelColor(TINTA_SECUNDARIA)
        chart.addSeries(serie)
        eje_y = QBarCategoryAxis()
        eje_y.append([c for c, _ in orden])
        eje_x = QValueAxis()
        eje_x.setRange(0, max([p for _, p in categorias] + [10]) * 1.25)
        eje_x.setLabelFormat("%.0f")
        eje_x.setTitleText("% de días alquilados")
        eje_x.setTitleBrush(TINTA_SECUNDARIA)
        for eje, lado in ((eje_y, Qt.AlignmentFlag.AlignLeft), (eje_x, Qt.AlignmentFlag.AlignBottom)):
            _eje_recesivo(eje)
            chart.addAxis(eje, lado)
            serie.attachAxis(eje)
        eje_y.setGridLineVisible(False)
