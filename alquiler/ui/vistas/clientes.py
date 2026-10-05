"""Vista de clientes: búsqueda, alta, edición, baja e historial."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import widgets
from alquiler.ui.logica import personas
from alquiler.ui.logica.contexto import Contexto

COLUMNAS = [("documento", "Documento"), ("nombre", "Nombre"), ("telefono", "Teléfono"),
            ("email", "Correo"), ("estado", "Estado")]
COLUMNAS_HISTORIAL = [("equipo", "Equipo"), ("inicio", "Inicio"), ("fin", "Fin previsto"),
                      ("estado", "Estado"), ("total", "Total"), ("saldo", "Saldo pendiente")]


class DialogoCliente(QDialog):
    def __init__(self, datos: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar cliente" if datos else "Nuevo cliente")
        formulario = QFormLayout(self)
        self.campo_documento = QLineEdit()
        self.campo_nombre = QLineEdit()
        self.campo_telefono = QLineEdit()
        self.campo_email = QLineEdit()
        self.campo_direccion = QLineEdit()
        if datos:
            for campo, clave in ((self.campo_documento, "documento"), (self.campo_nombre, "nombre"),
                                 (self.campo_telefono, "telefono"), (self.campo_email, "email"),
                                 (self.campo_direccion, "direccion")):
                campo.setText(datos[clave])
            self.campo_documento.setEnabled(False)
        formulario.addRow("Documento", self.campo_documento)
        formulario.addRow("Nombre", self.campo_nombre)
        formulario.addRow("Teléfono", self.campo_telefono)
        formulario.addRow("Correo", self.campo_email)
        formulario.addRow("Dirección", self.campo_direccion)
        formulario.addRow(widgets.botones_dialogo(self))


class VistaClientes(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado("Clientes", "Registro de clientes y su historial."))
        filtros = QHBoxLayout()
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setPlaceholderText("Buscar por nombre o documento…")
        self.casilla_inactivos = QCheckBox("Incluir inactivos")
        filtros.addWidget(self.campo_buscar, 1)
        filtros.addWidget(self.casilla_inactivos)
        capa.addLayout(filtros)
        self.tabla = widgets.Tabla()
        capa.addWidget(self.tabla, 2)

        self.botones: dict = {}
        acciones = QHBoxLayout()
        if ctx.puede("clientes.gestionar"):
            self.botones["nuevo"] = widgets.boton("Nuevo cliente", "primario", self._nuevo)
            self.botones["editar"] = widgets.boton("Editar", al_click=self._editar)
            self.botones["desactivar"] = widgets.boton("Desactivar", "peligro", self._desactivar)
        for b in self.botones.values():
            acciones.addWidget(b)
        acciones.addStretch()
        capa.addLayout(acciones)

        self.etiqueta_historial = QLabel("<b>Historial</b> — seleccione un cliente.")
        capa.addWidget(self.etiqueta_historial)
        self.tabla_historial = widgets.Tabla()
        capa.addWidget(self.tabla_historial, 1)

        self.campo_buscar.textChanged.connect(self.recargar)
        self.casilla_inactivos.toggled.connect(self.recargar)
        self.tabla.selectionModel().selectionChanged.connect(self._al_seleccionar)
        self.recargar()

    def recargar(self, *_):
        filas = personas.clientes(self.ctx, self.campo_buscar.text() or None,
                                  self.casilla_inactivos.isChecked())
        self.tabla.cargar(COLUMNAS, filas, colores={"estado": widgets.tono_para})
        self.tabla_historial.cargar(COLUMNAS_HISTORIAL, [])

    def _al_seleccionar(self, *_):
        fila = self.tabla.seleccionada()
        if fila:
            self.etiqueta_historial.setText(f"<b>Historial de {fila['nombre']}</b>")
            self.tabla_historial.cargar(COLUMNAS_HISTORIAL,
                                        personas.historial_cliente(self.ctx, fila["id"]),
                                        colores={"estado": widgets.tono_para})

    def _seleccion(self) -> dict | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione un cliente de la tabla.")
        return fila

    def _nuevo(self):
        dlg = DialogoCliente(parent=self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: personas.registrar_cliente(
                self.ctx, dlg.campo_documento.text(), dlg.campo_nombre.text(),
                dlg.campo_telefono.text(), dlg.campo_email.text(), dlg.campo_direccion.text())):
            self.recargar()

    def _editar(self):
        fila = self._seleccion()
        if not fila:
            return
        dlg = DialogoCliente(fila, self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: personas.actualizar_cliente(
                self.ctx, fila["id"], nombre=dlg.campo_nombre.text(),
                telefono=dlg.campo_telefono.text(), email=dlg.campo_email.text(),
                direccion=dlg.campo_direccion.text())):
            self.recargar()

    def _desactivar(self):
        fila = self._seleccion()
        if fila and widgets.confirmar(
                self, f"¿Desactivar a {fila['nombre']}? No podrá alquilar ni ingresar al sistema.") \
                and widgets.ejecutar_accion(self, lambda: personas.desactivar_cliente(self.ctx, fila["id"])):
            self.recargar()
