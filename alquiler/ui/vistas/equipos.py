"""Vista de equipos: catálogo con filtros y máquina de estados visual."""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import widgets
from alquiler.ui.logica import catalogo
from alquiler.ui.logica.contexto import Contexto

COLUMNAS = [("codigo", "Código"), ("nombre", "Nombre"), ("categoria", "Categoría"),
            ("estado", "Estado"), ("tarifa", "Tarifa diaria"), ("usos", "Usos")]


class DialogoEquipo(QDialog):
    def __init__(self, categorias: list[dict], datos: dict | None = None,
                 hoy: date | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar equipo" if datos else "Nuevo equipo")
        hoy = hoy or date.today()
        formulario = QFormLayout(self)
        self.campo_codigo = QLineEdit()
        self.campo_nombre = QLineEdit()
        self.combo_categoria = QComboBox()
        for c in categorias:
            self.combo_categoria.addItem(c["nombre"], c["id"])
        self.campo_tarifa = QSpinBox()
        self.campo_tarifa.setRange(1, 100_000_000)
        self.campo_tarifa.setSingleStep(1_000)
        self.campo_tarifa.setPrefix("$ ")
        self.campo_tarifa.setGroupSeparatorShown(True)
        self.campo_tarifa.setValue(20_000)
        self.campo_fecha = QDateEdit(QDate(hoy))
        self.campo_fecha.setCalendarPopup(True)
        self.campo_fecha.setMaximumDate(QDate(hoy))
        self.campo_fecha.setDisplayFormat("dd/MM/yyyy")
        if datos:
            self.campo_codigo.setText(datos["codigo"])
            self.campo_codigo.setEnabled(False)  # el código identifica el equipo
            self.campo_nombre.setText(datos["nombre"])
            self.combo_categoria.setCurrentIndex(self.combo_categoria.findData(datos["categoria_id"]))
            self.campo_tarifa.setValue(datos["tarifa_valor"])
            self.campo_fecha.setDate(QDate(datos["fecha_adquisicion"]))
            self.campo_fecha.setEnabled(False)
        formulario.addRow("Código", self.campo_codigo)
        formulario.addRow("Nombre", self.campo_nombre)
        formulario.addRow("Categoría", self.combo_categoria)
        formulario.addRow("Tarifa diaria", self.campo_tarifa)
        formulario.addRow("Fecha de adquisición", self.campo_fecha)
        formulario.addRow(widgets.botones_dialogo(self))


class DialogoCategoria(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva categoría")
        formulario = QFormLayout(self)
        self.campo_nombre = QLineEdit()
        self.campo_usos = QSpinBox()
        self.campo_usos.setRange(1, 10_000)
        self.campo_usos.setValue(20)
        self.campo_dias = QSpinBox()
        self.campo_dias.setRange(1, 3_650)
        self.campo_dias.setValue(90)
        formulario.addRow("Nombre", self.campo_nombre)
        formulario.addRow("Mantenimiento cada (usos)", self.campo_usos)
        formulario.addRow("Mantenimiento cada (días)", self.campo_dias)
        formulario.addRow(widgets.botones_dialogo(self))


class DialogoMantenimiento(QDialog):
    def __init__(self, equipo: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Abrir mantenimiento")
        formulario = QFormLayout(self)
        formulario.addRow("Equipo", QLabel(equipo))
        self.combo_tipo = QComboBox()
        for tipo in catalogo.TIPOS_MANTENIMIENTO:
            self.combo_tipo.addItem(tipo.capitalize(), tipo)
        self.campo_descripcion = QPlainTextEdit()
        self.campo_descripcion.setFixedHeight(80)
        formulario.addRow("Tipo", self.combo_tipo)
        formulario.addRow("Descripción", self.campo_descripcion)
        formulario.addRow(widgets.botones_dialogo(self))


class PanelEstados(QFrame):
    """Máquina de estados: estado actual resaltado y transiciones posibles marcadas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        self.setFixedWidth(260)
        capa = QVBoxLayout(self)
        titulo = QLabel("Ciclo de vida del equipo")
        titulo.setStyleSheet("font-weight:700;")
        capa.addWidget(titulo)
        self.etiqueta_equipo = QLabel("Seleccione un equipo para ver su estado.")
        self.etiqueta_equipo.setWordWrap(True)
        self.etiqueta_equipo.setObjectName("subtituloVista")
        capa.addWidget(self.etiqueta_equipo)
        rejilla = QGridLayout()
        self.insignias: dict[str, widgets.Insignia] = {}
        self._marcas: dict[str, QLabel] = {}
        for i, estado in enumerate(catalogo.ESTADOS):
            self.insignias[estado] = widgets.Insignia(estado, "neutro")
            self._marcas[estado] = QLabel("")
            rejilla.addWidget(self.insignias[estado], i, 0)
            rejilla.addWidget(self._marcas[estado], i, 1)
        capa.addLayout(rejilla)
        leyenda = QLabel("● actual   → puede pasar a")
        leyenda.setObjectName("advertencia")
        capa.addWidget(leyenda)
        capa.addStretch()
        self.estado_actual: str | None = None
        self.alcanzables: list[str] = []
        self.actualizar(None)

    def actualizar(self, estado: str | None, equipo: str = "") -> None:
        self.estado_actual = estado
        self.alcanzables = catalogo.estados_posibles(estado) if estado else []
        if equipo:
            self.etiqueta_equipo.setText(equipo)
        for e, insignia in self.insignias.items():
            if e == estado:
                insignia.set_valor(e, widgets.tono_para(e))
                self._marcas[e].setText("● actual")
            elif e in self.alcanzables:
                insignia.set_valor(e, "info")
                self._marcas[e].setText("→")
            else:
                insignia.set_valor(e, "neutro")
                self._marcas[e].setText("")


class VistaEquipos(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        gestiona = ctx.puede("equipos.gestionar")
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado(
            "Equipos", "Inventario, estados y mantenimiento." if gestiona
            else "Catálogo de equipos disponibles para alquilar."))

        filtros = QHBoxLayout()
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setPlaceholderText("Buscar por código o nombre…")
        self.combo_categoria = QComboBox()
        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos los estados", None)
        for e in catalogo.ESTADOS:
            self.combo_estado.addItem(e, e)
        self.combo_estado.setVisible(gestiona)  # el cliente solo ve disponibles
        for w in (self.campo_buscar, self.combo_categoria, self.combo_estado):
            filtros.addWidget(w)
        capa.addLayout(filtros)

        cuerpo = QHBoxLayout()
        self.tabla = widgets.Tabla()
        self.panel_estados = PanelEstados()
        cuerpo.addWidget(self.tabla, 1)
        cuerpo.addWidget(self.panel_estados)
        capa.addLayout(cuerpo, 1)

        self.botones: dict = {}
        acciones = QHBoxLayout()
        if gestiona:
            self.botones["nuevo"] = widgets.boton("Nuevo equipo", "primario", self._nuevo)
            self.botones["editar"] = widgets.boton("Editar", al_click=self._editar)
            self.botones["categoria"] = widgets.boton("Nueva categoría", al_click=self._categoria)
            self.botones["baja"] = widgets.boton("Dar de baja", "peligro", self._baja)
        if ctx.puede("equipos.eliminar"):
            self.botones["eliminar"] = widgets.boton("Eliminar", "peligro", self._eliminar)
        if ctx.puede("mantenimiento.gestionar"):
            self.botones["mantenimiento"] = widgets.boton("Abrir mantenimiento",
                                                          al_click=self._mantenimiento)
        for b in self.botones.values():
            acciones.addWidget(b)
        acciones.addStretch()
        capa.addLayout(acciones)

        self.campo_buscar.textChanged.connect(self.recargar)
        self.combo_categoria.currentIndexChanged.connect(self.recargar)
        self.combo_estado.currentIndexChanged.connect(self.recargar)
        self.tabla.selectionModel().selectionChanged.connect(self._al_seleccionar)
        self._cargar_categorias()
        self.recargar()

    # ---------------------------------------------------------------- datos
    def _cargar_categorias(self):
        self._categorias = catalogo.categorias(self.ctx)
        self.combo_categoria.blockSignals(True)
        actual = self.combo_categoria.currentData()
        self.combo_categoria.clear()
        self.combo_categoria.addItem("Todas las categorías", None)
        for c in self._categorias:
            self.combo_categoria.addItem(c["nombre"], c["id"])
        self.combo_categoria.setCurrentIndex(max(0, self.combo_categoria.findData(actual)))
        self.combo_categoria.blockSignals(False)

    def al_volver(self):
        self._cargar_categorias()
        self.recargar()

    def recargar(self):
        filas = catalogo.equipos(self.ctx, self.campo_buscar.text() or None,
                                 self.combo_estado.currentData(), self.combo_categoria.currentData())
        self.tabla.cargar(COLUMNAS, filas, colores={"estado": widgets.tono_para})
        self.panel_estados.actualizar(None)

    def _al_seleccionar(self, *_):
        fila = self.tabla.seleccionada()
        if fila:
            self.panel_estados.actualizar(fila["estado"], f"{fila['codigo']} · {fila['nombre']}")

    def _seleccion(self) -> dict | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione un equipo de la tabla.")
        return fila

    # ---------------------------------------------------------------- acciones
    def _nuevo(self):
        dlg = DialogoEquipo(self._categorias, hoy=self.ctx.hoy(), parent=self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: catalogo.crear_equipo(
                self.ctx, dlg.campo_codigo.text(), dlg.campo_nombre.text(),
                dlg.combo_categoria.currentData(), dlg.campo_tarifa.value(),
                dlg.campo_fecha.date().toPython())):
            self.recargar()

    def _editar(self):
        fila = self._seleccion()
        if not fila:
            return
        dlg = DialogoEquipo(self._categorias, fila, hoy=self.ctx.hoy(), parent=self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: catalogo.actualizar_equipo(
                self.ctx, fila["id"], nombre=dlg.campo_nombre.text(),
                categoria_id=dlg.combo_categoria.currentData(),
                tarifa_diaria=dlg.campo_tarifa.value())):
            self.recargar()

    def _categoria(self):
        dlg = DialogoCategoria(self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: catalogo.crear_categoria(
                self.ctx, dlg.campo_nombre.text(), dlg.campo_usos.value(), dlg.campo_dias.value())):
            self._cargar_categorias()

    def _baja(self):
        fila = self._seleccion()
        if fila and widgets.confirmar(self, f"¿Dar de baja {fila['codigo']}? Quedará fuera de servicio.") \
                and widgets.ejecutar_accion(self, lambda: catalogo.dar_de_baja(self.ctx, fila["id"])):
            self.recargar()

    def _eliminar(self):
        fila = self._seleccion()
        if fila and widgets.confirmar(self, f"¿Eliminar definitivamente {fila['codigo']}?") \
                and widgets.ejecutar_accion(self, lambda: catalogo.eliminar_equipo(self.ctx, fila["id"])):
            self.recargar()

    def _mantenimiento(self):
        fila = self._seleccion()
        if not fila:
            return
        dlg = DialogoMantenimiento(f"{fila['codigo']} · {fila['nombre']}", self)
        if widgets.ejecutar_dialogo(dlg) and widgets.ejecutar_accion(self, lambda: catalogo.abrir_mantenimiento(
                self.ctx, fila["id"], dlg.combo_tipo.currentData(),
                dlg.campo_descripcion.toPlainText())):
            self.recargar()
