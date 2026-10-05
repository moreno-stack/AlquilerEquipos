"""Vista de mantenimiento: abiertos, cierre con costo e historial por equipo."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import widgets
from alquiler.ui.logica import catalogo
from alquiler.ui.logica.contexto import Contexto

COLUMNAS_ABIERTOS = [("equipo", "Equipo"), ("tipo", "Tipo"), ("desde", "Desde"),
                     ("dias", "Días abierto"), ("descripcion", "Descripción")]
COLUMNAS_HISTORIAL = [("tipo", "Tipo"), ("inicio", "Inicio"), ("fin", "Fin"),
                      ("costo", "Costo"), ("descripcion", "Descripción")]


class DialogoCierre(QDialog):
    def __init__(self, equipo: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cerrar mantenimiento")
        formulario = QFormLayout(self)
        formulario.addRow("Equipo", QLabel(equipo))
        self.campo_costo = QSpinBox()
        self.campo_costo.setRange(0, 100_000_000)
        self.campo_costo.setSingleStep(5_000)
        self.campo_costo.setPrefix("$ ")
        self.campo_costo.setGroupSeparatorShown(True)
        self.campo_notas = QPlainTextEdit()
        self.campo_notas.setFixedHeight(70)
        formulario.addRow("Costo", self.campo_costo)
        formulario.addRow("Notas de cierre", self.campo_notas)
        formulario.addRow(widgets.botones_dialogo(self))


class VistaMantenimiento(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado(
            "Mantenimiento", "Equipos en taller y su historial de servicios preventivos y correctivos."))
        capa.addWidget(QLabel("<b>Mantenimientos abiertos</b>"))
        self.tabla_abiertos = widgets.Tabla()
        capa.addWidget(self.tabla_abiertos, 1)
        acciones = QHBoxLayout()
        self.boton_cerrar = widgets.boton("Cerrar mantenimiento", "primario", self._cerrar)
        self.boton_cerrar.setVisible(ctx.puede("mantenimiento.gestionar"))
        acciones.addWidget(self.boton_cerrar)
        acciones.addStretch()
        capa.addLayout(acciones)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("<b>Historial del equipo</b>"))
        self.combo_equipo = QComboBox()
        self.combo_equipo.setMinimumWidth(320)
        fila.addWidget(self.combo_equipo)
        fila.addStretch()
        capa.addLayout(fila)
        self.tabla_historial = widgets.Tabla()
        capa.addWidget(self.tabla_historial, 1)

        self.combo_equipo.currentIndexChanged.connect(self._cargar_historial)
        self.al_volver()

    def al_volver(self):
        actual = self.combo_equipo.currentData()
        self.combo_equipo.blockSignals(True)
        self.combo_equipo.clear()
        for e in catalogo.equipos_para_mantenimiento(self.ctx):
            self.combo_equipo.addItem(e["etiqueta"], e["id"])
        self.combo_equipo.setCurrentIndex(max(0, self.combo_equipo.findData(actual)))
        self.combo_equipo.blockSignals(False)
        self.recargar()

    def recargar(self):
        self.tabla_abiertos.cargar(COLUMNAS_ABIERTOS, catalogo.mantenimientos_abiertos(self.ctx))
        self._cargar_historial()

    def _cargar_historial(self, *_):
        equipo_id = self.combo_equipo.currentData()
        filas = catalogo.historial_mantenimiento(self.ctx, equipo_id) if equipo_id else []
        self.tabla_historial.cargar(COLUMNAS_HISTORIAL, filas)

    def _cerrar(self):
        fila = self.tabla_abiertos.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione un mantenimiento abierto.")
            return
        dlg = DialogoCierre(fila["equipo"], self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: catalogo.cerrar_mantenimiento(
                self.ctx, fila["id"], dlg.campo_costo.value(), dlg.campo_notas.toPlainText())):
            self.recargar()
