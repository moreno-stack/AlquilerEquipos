"""Análisis IA: demanda, mantenimiento preventivo y retrasos como tarjetas explicables."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import trabajador, widgets
from alquiler.ui.logica import ia
from alquiler.ui.logica.contexto import Contexto

PESTANAS = [
    ("demanda", "Demanda", ia.demanda,
     "Pronóstico mensual por categoría: índice estacional × media de los últimos 3 meses."),
    ("mantenimiento", "Mantenimiento preventivo", ia.mantenimiento,
     "Puntaje 0–100 por equipo: usos y días desde el último servicio, uso reciente y fallas."),
    ("retrasos", "Retrasos", ia.retrasos,
     "Clientes y categorías con más devoluciones tardías, con tasa suavizada para no "
     "señalar a nadie por un caso aislado."),
]


class PestanaAnalisis(QWidget):
    def __init__(self, ctx: Contexto, analizar: Callable[[Contexto], dict], descripcion: str,
                 parent=None):
        super().__init__(parent)
        self.ctx, self._analizar = ctx, analizar
        self.tarjetas: list[widgets.TarjetaResultado] = []
        self.analizado = False
        capa = QVBoxLayout(self)
        cabecera = QHBoxLayout()
        nota = QLabel(descripcion)
        nota.setObjectName("subtituloVista")
        nota.setWordWrap(True)
        self.boton = widgets.boton("Analizar", "primario", self.analizar)
        cabecera.addWidget(nota, 1)
        cabecera.addWidget(self.boton)
        capa.addLayout(cabecera)
        self.etiqueta_estado = QLabel()
        self.etiqueta_estado.setStyleSheet("font-weight:600;")
        self.etiqueta_estado.setWordWrap(True)
        capa.addWidget(self.etiqueta_estado)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._contenedor = QWidget()
        self._lista = QVBoxLayout(self._contenedor)
        self._lista.addStretch()
        desplazable.setWidget(self._contenedor)
        capa.addWidget(desplazable, 1)

    def analizar(self):
        self.analizado = True
        self.boton.setEnabled(False)
        self.etiqueta_estado.setText("Analizando…")
        trabajador.ejecutar_en_segundo_plano(lambda: self._analizar(self.ctx), self._mostrar,
                                             self._fallo, self)

    def _fallo(self, mensaje: str):
        self.boton.setEnabled(True)
        self.etiqueta_estado.setText("")
        widgets.mostrar_error(self, mensaje)

    def _mostrar(self, datos: dict):
        for t in self.tarjetas:
            t.deleteLater()
        self.tarjetas = []
        for d in datos["tarjetas"]:
            insignias = []
            if d.get("grupo"):
                insignias.append((d["grupo"], "neutro"))
            if d.get("prioridad"):
                insignias.append((f"Prioridad {d['prioridad']}", widgets.TONO_PRIORIDAD[d["prioridad"]]))
            tarjeta = widgets.TarjetaResultado({**d, "insignias": insignias})
            self._lista.insertWidget(self._lista.count() - 1, tarjeta)
            self.tarjetas.append(tarjeta)
        self.etiqueta_estado.setText(datos["resumen"])
        self.boton.setEnabled(True)


class VistaAnalisisIA(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado(
            "Análisis IA", "Estimaciones a partir del historial. Cada resultado muestra su "
                           "confianza y cómo se calculó: son apoyo a la decisión, no certezas."))
        self.tabs = QTabWidget()
        self.pestanas: dict[str, PestanaAnalisis] = {}
        for clave, titulo, funcion, descripcion in PESTANAS:
            self.pestanas[clave] = PestanaAnalisis(ctx, funcion, descripcion)
            self.tabs.addTab(self.pestanas[clave], titulo)
        capa.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(self._al_cambiar)
        self._al_cambiar(0)

    def analizar(self):
        """"Ejecutar diagnóstico": vuelve a analizar la pestaña abierta (si no está ya en curso)."""
        pestana = self.tabs.currentWidget()
        if pestana.boton.isEnabled():
            pestana.analizar()

    def _al_cambiar(self, indice: int):
        pestana = self.tabs.widget(indice)
        if not pestana.analizado:  # cada análisis se ejecuta al abrir su pestaña
            pestana.analizar()
