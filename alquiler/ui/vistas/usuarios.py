"""Vista de usuarios del sistema (solo administradores)."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import widgets
from alquiler.ui.logica import personas
from alquiler.ui.logica.contexto import Contexto

COLUMNAS = [("username", "Usuario"), ("nombre", "Nombre"), ("rol", "Rol"), ("estado", "Estado")]


def _campo_clave() -> QLineEdit:
    campo = QLineEdit()
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    campo.setPlaceholderText("Mínimo 8 caracteres")
    return campo


class DialogoUsuario(QDialog):
    def __init__(self, clientes_habilitados: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo usuario")
        formulario = QFormLayout(self)
        self.campo_usuario = QLineEdit()
        self.campo_nombre = QLineEdit()
        self.combo_rol = QComboBox()
        for valor, etiqueta in personas.ROLES:
            self.combo_rol.addItem(etiqueta, valor)
        self.combo_rol.setCurrentIndex(self.combo_rol.findData("empleado"))
        self.combo_cliente = QComboBox()
        for c in clientes_habilitados:
            self.combo_cliente.addItem(c["etiqueta"], c["id"])
        self.campo_password = _campo_clave()
        formulario.addRow("Usuario", self.campo_usuario)
        formulario.addRow("Nombre completo", self.campo_nombre)
        formulario.addRow("Rol", self.combo_rol)
        formulario.addRow("Cliente vinculado", self.combo_cliente)
        formulario.addRow("Contraseña", self.campo_password)
        formulario.addRow(widgets.botones_dialogo(self))
        self.combo_rol.currentIndexChanged.connect(self._al_cambiar_rol)
        self._al_cambiar_rol()

    def _al_cambiar_rol(self, *_):
        self.combo_cliente.setEnabled(self.combo_rol.currentData() == "cliente")

    def cliente_id(self) -> int | None:
        return self.combo_cliente.currentData() if self.combo_cliente.isEnabled() else None


class DialogoClave(QDialog):
    def __init__(self, usuario: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Restablecer contraseña de {usuario}")
        formulario = QFormLayout(self)
        self.campo_password = _campo_clave()
        formulario.addRow("Nueva contraseña", self.campo_password)
        formulario.addRow(widgets.botones_dialogo(self))


class VistaUsuarios(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado("Usuarios", "Cuentas de acceso y roles del sistema."))
        self.tabla = widgets.Tabla()
        capa.addWidget(self.tabla, 1)
        acciones = QHBoxLayout()
        self.botones = {
            "nuevo": widgets.boton("Nuevo usuario", "primario", self._nuevo),
            "estado": widgets.boton("Activar / desactivar", al_click=self._alternar),
            "clave": widgets.boton("Restablecer contraseña", al_click=self._clave),
        }
        for b in self.botones.values():
            acciones.addWidget(b)
        acciones.addStretch()
        capa.addLayout(acciones)
        self.recargar()

    def recargar(self):
        self.tabla.cargar(COLUMNAS, personas.usuarios(self.ctx), colores={"estado": widgets.tono_para})

    def _seleccion(self) -> dict | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione un usuario de la tabla.")
        return fila

    def _nuevo(self):
        dlg = DialogoUsuario(personas.clientes_habilitados(self.ctx), self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: personas.crear_usuario(
                self.ctx, dlg.campo_usuario.text(), dlg.campo_password.text(),
                dlg.combo_rol.currentData(), dlg.campo_nombre.text(), dlg.cliente_id())):
            self.recargar()

    def _alternar(self):
        fila = self._seleccion()
        if fila and widgets.ejecutar_accion(self, lambda: personas.cambiar_estado_usuario(
                self.ctx, fila["id"], not fila["activo"])):
            self.recargar()

    def _clave(self):
        fila = self._seleccion()
        if not fila:
            return
        dlg = DialogoClave(fila["username"], self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: personas.restablecer_password(
                self.ctx, fila["id"], dlg.campo_password.text())):
            widgets.informar(self, f"Contraseña de {fila['username']} restablecida.")
