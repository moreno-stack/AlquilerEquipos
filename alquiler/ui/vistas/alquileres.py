"""Vista de alquileres: nuevo contrato, devolución con mora en vivo y pagos."""

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import widgets
from alquiler.ui.logica import operaciones, personas
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import pesos

COLUMNAS = [("cliente", "Cliente"), ("equipo", "Equipo"), ("inicio", "Inicio"),
            ("fin", "Devolución prevista"), ("estado", "Estado"), ("situacion", "Situación"),
            ("saldo", "Saldo pendiente")]


def _fecha(valor: date, minimo: date | None = None, maximo: date | None = None) -> QDateEdit:
    campo = QDateEdit(QDate(valor))
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd/MM/yyyy")
    if minimo:
        campo.setMinimumDate(QDate(minimo))
    if maximo:
        campo.setMaximumDate(QDate(maximo))
    return campo


def _pesos(maximo: int, valor: int = 0) -> QSpinBox:
    campo = QSpinBox()
    campo.setRange(0, maximo)
    campo.setSingleStep(1_000)
    campo.setPrefix("$ ")
    campo.setGroupSeparatorShown(True)
    campo.setValue(valor)
    return campo


def _vista_previa() -> QLabel:
    etiqueta = QLabel()
    etiqueta.setWordWrap(True)
    etiqueta.setObjectName("notaInfo")
    return etiqueta


class DialogoAlquiler(QDialog):
    def __init__(self, clientes: list[dict], equipos: list[dict], hoy: date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo alquiler")
        self.setMinimumWidth(460)
        formulario = QFormLayout(self)
        self.combo_cliente = QComboBox()
        for c in clientes:
            self.combo_cliente.addItem(c["etiqueta"], c["id"])
        self.combo_equipo = QComboBox()
        for e in equipos:
            self.combo_equipo.addItem(e["etiqueta"], (e["id"], e["tarifa_valor"]))
        self.campo_inicio = _fecha(hoy, minimo=hoy)
        self.campo_fin = _fecha(hoy + timedelta(days=1), minimo=hoy)
        self.etiqueta_cotizacion = _vista_previa()
        nota = QLabel("Si el inicio es posterior a hoy, el equipo queda reservado.")
        nota.setObjectName("advertencia")
        formulario.addRow("Cliente (activos)", self.combo_cliente)
        formulario.addRow("Equipo (disponibles)", self.combo_equipo)
        formulario.addRow("Inicio", self.campo_inicio)
        formulario.addRow("Devolución prevista", self.campo_fin)
        formulario.addRow("Costo estimado", self.etiqueta_cotizacion)
        formulario.addRow(nota)
        formulario.addRow(widgets.botones_dialogo(self))
        self.campo_inicio.dateChanged.connect(self._al_cambiar_inicio)
        self.campo_fin.dateChanged.connect(self._cotizar)
        self.combo_equipo.currentIndexChanged.connect(self._cotizar)
        self._cotizar()

    def _al_cambiar_inicio(self, *_):
        self.campo_fin.setMinimumDate(self.campo_inicio.date())
        self._cotizar()

    def _cotizar(self, *_):
        datos = self.combo_equipo.currentData()
        if datos is None:
            self.etiqueta_cotizacion.setText("No hay equipos disponibles.")
            return
        self.etiqueta_cotizacion.setText(operaciones.cotizar(
            self.campo_inicio.date().toPython(), self.campo_fin.date().toPython(), datos[1])["texto"])

    def valores(self) -> tuple:
        return (self.combo_cliente.currentData(), (self.combo_equipo.currentData() or (None,))[0],
                self.campo_inicio.date().toPython(), self.campo_fin.date().toPython())


class DialogoDevolucion(QDialog):
    def __init__(self, alquiler: dict, hoy: date,
                 previsualizar: Callable[[date, int], dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar devolución")
        self.setMinimumWidth(460)
        self._previsualizar = previsualizar
        formulario = QFormLayout(self)
        formulario.addRow("Alquiler", QLabel(f"{alquiler['equipo']} — {alquiler['cliente']}"))
        self.campo_fecha = _fecha(hoy, minimo=alquiler["inicio_valor"], maximo=hoy)
        self.campo_horas = QDoubleSpinBox()
        self.campo_horas.setRange(0, 10_000)
        self.campo_horas.setSuffix(" h")
        self.casilla_danos = QCheckBox("El equipo se devolvió con daños")
        self.campo_descripcion = QPlainTextEdit()
        self.campo_descripcion.setFixedHeight(60)
        self.campo_penalizacion = _pesos(100_000_000)
        self.etiqueta_vista_previa = _vista_previa()
        formulario.addRow("Fecha de devolución", self.campo_fecha)
        formulario.addRow("Horas de uso", self.campo_horas)
        formulario.addRow(self.casilla_danos)
        formulario.addRow("Descripción de daños", self.campo_descripcion)
        formulario.addRow("Penalización por daños", self.campo_penalizacion)
        formulario.addRow("Liquidación", self.etiqueta_vista_previa)
        formulario.addRow(widgets.botones_dialogo(self))
        self.casilla_danos.toggled.connect(self._al_cambiar_danos)
        self.campo_fecha.dateChanged.connect(self._actualizar)
        self.campo_penalizacion.valueChanged.connect(self._actualizar)
        self._al_cambiar_danos(False)

    def _al_cambiar_danos(self, con_danos: bool):
        self.campo_descripcion.setEnabled(con_danos)
        self.campo_penalizacion.setEnabled(con_danos)
        self._actualizar()

    def penalizacion(self) -> int:
        return self.campo_penalizacion.value() if self.casilla_danos.isChecked() else 0

    def _actualizar(self, *_):
        self.etiqueta_vista_previa.setText(self._previsualizar(
            self.campo_fecha.date().toPython(), self.penalizacion())["texto"])


class DialogoPago(QDialog):
    def __init__(self, alquiler: dict, saldo: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pago")
        formulario = QFormLayout(self)
        formulario.addRow("Alquiler", QLabel(f"{alquiler['equipo']} — {alquiler['cliente']}"))
        self.etiqueta_saldo = QLabel(f"Saldo pendiente: {pesos(saldo)}")
        self.etiqueta_saldo.setStyleSheet("font-weight:600;")
        self.campo_monto = _pesos(saldo, saldo)
        self.combo_metodo = QComboBox()
        for valor, etiqueta in operaciones.METODOS:
            self.combo_metodo.addItem(etiqueta, valor)
        self.combo_concepto = QComboBox()
        for valor, etiqueta in operaciones.CONCEPTOS:
            self.combo_concepto.addItem(etiqueta, valor)
        formulario.addRow(self.etiqueta_saldo)
        formulario.addRow("Monto", self.campo_monto)
        formulario.addRow("Método", self.combo_metodo)
        formulario.addRow("Concepto", self.combo_concepto)
        formulario.addRow(widgets.botones_dialogo(self))


class VistaAlquileres(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado(
            "Alquileres", "Contratos en curso, devoluciones con cálculo de mora y pagos."))
        filtros = QHBoxLayout()
        self.combo_estado = QComboBox()
        for valor, etiqueta in operaciones.ESTADOS_ALQUILER:
            self.combo_estado.addItem(etiqueta, valor)
        filtros.addWidget(QLabel("Mostrar:"))
        filtros.addWidget(self.combo_estado)
        filtros.addStretch()
        leyenda = widgets.Insignia("Fila roja = devolución vencida", "peligro")
        filtros.addWidget(leyenda)
        capa.addLayout(filtros)
        self.tabla = widgets.Tabla()
        capa.addWidget(self.tabla, 1)

        self.botones: dict = {}
        acciones = QHBoxLayout()
        if ctx.puede("alquileres.gestionar"):
            self.botones["nuevo"] = widgets.boton("Nuevo alquiler", "primario", self._nuevo)
            self.botones["pago"] = widgets.boton("Registrar pago", al_click=self._pago)
        if ctx.puede("devoluciones.registrar"):
            self.botones["devolucion"] = widgets.boton("Registrar devolución", al_click=self._devolucion)
        for b in self.botones.values():
            acciones.addWidget(b)
        acciones.addStretch()
        capa.addLayout(acciones)
        self.combo_estado.currentIndexChanged.connect(self.recargar)
        self.recargar()

    def recargar(self, *_):
        filas = operaciones.alquileres(self.ctx, self.combo_estado.currentData())
        self.tabla.cargar(COLUMNAS, filas,
                          resaltar=lambda f: "peligro" if f["situacion"] == "vencido" else None,
                          colores={"estado": widgets.tono_para})

    def _seleccion(self) -> dict | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione un alquiler de la tabla.")
        return fila

    def _nuevo(self):
        clientes = personas.clientes_habilitados(self.ctx)
        equipos = operaciones.equipos_disponibles(self.ctx)
        if not clientes:
            widgets.mostrar_error(self, "No hay clientes activos registrados.")
            return
        if not equipos:
            widgets.mostrar_error(self, "No hay equipos disponibles para alquilar.")
            return
        dlg = DialogoAlquiler(clientes, equipos, self.ctx.hoy(), self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(
                self, lambda: operaciones.crear_alquiler(self.ctx, *dlg.valores())):
            self.recargar()

    def _devolucion(self):
        fila = self._seleccion()
        if not fila:
            return
        dlg = DialogoDevolucion(fila, self.ctx.hoy(), lambda f, p: operaciones.previsualizar_devolucion(
            self.ctx, fila["id"], f, p), self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: operaciones.registrar_devolucion(
                self.ctx, fila["id"], dlg.campo_fecha.date().toPython(), dlg.campo_horas.value(),
                dlg.casilla_danos.isChecked(), dlg.campo_descripcion.toPlainText(),
                dlg.penalizacion())):
            self.recargar()

    def _pago(self):
        fila = self._seleccion()
        if not fila:
            return
        saldo = operaciones.saldo(self.ctx, fila["id"])
        if saldo <= 0:
            widgets.mostrar_error(self, "El alquiler no tiene saldo pendiente.")
            return
        dlg = DialogoPago(fila, saldo, self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: operaciones.registrar_pago(
                self.ctx, fila["id"], dlg.campo_monto.value(), dlg.combo_metodo.currentData(),
                dlg.combo_concepto.currentData())):
            self.recargar()
