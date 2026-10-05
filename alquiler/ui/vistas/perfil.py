"""Mi perfil: contraseña propia y, para clientes, contacto e historial."""

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from alquiler.ui import widgets
from alquiler.ui.logica import personas
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.vistas.clientes import COLUMNAS_HISTORIAL


def _clave() -> QLineEdit:
    campo = QLineEdit()
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    return campo


class VistaPerfil(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        u = ctx.usuario
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado("Mi perfil", f"{u.nombre} · usuario «{u.username}» · "
                                                       f"rol {u.rol}"))
        fila = QHBoxLayout()

        grupo_clave = QGroupBox("Cambiar contraseña")
        formulario = QFormLayout(grupo_clave)
        self.campo_actual, self.campo_nueva, self.campo_confirmar = _clave(), _clave(), _clave()
        formulario.addRow("Contraseña actual", self.campo_actual)
        formulario.addRow("Nueva contraseña", self.campo_nueva)
        formulario.addRow("Confirmar", self.campo_confirmar)
        self.boton_password = widgets.boton("Actualizar contraseña", "primario", self._cambiar_clave)
        formulario.addRow(self.boton_password)
        fila.addWidget(grupo_clave)

        self.grupo_contacto = self.tabla_historial = None
        cliente = personas.mi_cliente(ctx)
        if cliente:
            self.grupo_contacto = QGroupBox("Mis datos de contacto")
            datos = QFormLayout(self.grupo_contacto)
            self.campo_telefono = QLineEdit(cliente["telefono"])
            self.campo_email = QLineEdit(cliente["email"])
            self.campo_direccion = QLineEdit(cliente["direccion"])
            datos.addRow("Teléfono", self.campo_telefono)
            datos.addRow("Correo", self.campo_email)
            datos.addRow("Dirección", self.campo_direccion)
            self.boton_contacto = widgets.boton("Guardar contacto", "primario", self._guardar_contacto)
            datos.addRow(self.boton_contacto)
            fila.addWidget(self.grupo_contacto)
        capa.addLayout(fila)

        if cliente:
            capa.addWidget(widgets.encabezado("Mis alquileres"))
            self.tabla_historial = widgets.Tabla()
            self.tabla_historial.cargar(COLUMNAS_HISTORIAL,
                                        personas.historial_cliente(ctx, u.cliente_id),
                                        colores={"estado": widgets.tono_para})
            capa.addWidget(self.tabla_historial, 1)
        else:
            capa.addStretch()

    def _cambiar_clave(self):
        if self.campo_nueva.text() != self.campo_confirmar.text():
            widgets.mostrar_error(self, "Las contraseñas nuevas no coinciden.")
            return
        if widgets.ejecutar_accion(self, lambda: personas.cambiar_password(
                self.ctx, self.campo_actual.text(), self.campo_nueva.text())):
            for campo in (self.campo_actual, self.campo_nueva, self.campo_confirmar):
                campo.clear()
            widgets.informar(self, "Contraseña actualizada.")

    def _guardar_contacto(self):
        if widgets.ejecutar_accion(self, lambda: personas.actualizar_mi_contacto(
                self.ctx, self.campo_telefono.text(), self.campo_email.text(),
                self.campo_direccion.text())):
            widgets.informar(self, "Datos de contacto actualizados.")
