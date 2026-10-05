"""Ventana principal: barra lateral por rol y vistas creadas al primer uso."""

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import trabajador, widgets
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.navegacion import secciones_para


class VentanaPrincipal(QMainWindow):
    sesion_cerrada = Signal()

    def __init__(self, ctx: Contexto, fabricas: dict[str, Callable[[Contexto], QWidget]]):
        super().__init__()
        self.ctx, self._fabricas = ctx, fabricas
        self._secciones = secciones_para(ctx)
        self.vistas_creadas: dict[str, QWidget] = {}
        self.setWindowTitle("Sistema Inteligente de Alquiler de Equipos")
        self.resize(1280, 800)

        lateral = QWidget()
        lateral.setObjectName("panelLateral")
        lateral.setFixedWidth(220)
        capa_lateral = QVBoxLayout(lateral)
        capa_lateral.setContentsMargins(0, 0, 0, 0)
        marca = widgets.marca("Alquiler de Equipos")
        submarca = QLabel("Sistema inteligente")
        submarca.setObjectName("submarca")
        self.lista = QListWidget()
        self.lista.setObjectName("barraLateral")
        for s in self._secciones:
            item = QListWidgetItem(s.titulo)
            item.setData(Qt.ItemDataRole.UserRole, s.clave)
            self.lista.addItem(item)
        self.boton_cerrar_sesion = widgets.boton("Cerrar sesión", "salir", self._cerrar_sesion)
        for w in (marca, submarca, self.lista, self.boton_cerrar_sesion):
            capa_lateral.addWidget(w)

        self.pila = QStackedWidget()
        cuerpo = QWidget()
        capa = QHBoxLayout(cuerpo)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(lateral)
        contenedor = QWidget()
        capa_contenido = QVBoxLayout(contenedor)
        capa_contenido.setContentsMargins(24, 20, 24, 16)
        capa_contenido.addWidget(self.pila)
        capa.addWidget(contenedor, 1)
        self.setCentralWidget(cuerpo)

        u = ctx.usuario
        self.etiqueta_usuario = QLabel(f"{u.nombre} ({u.username}) · Rol: {u.rol.capitalize()}")
        self.etiqueta_ia = (widgets.Insignia("IA: Groq conectada", "marca") if ctx.cliente_llm
                            else widgets.Insignia("IA: sin clave (consultas predefinidas)"))
        self.statusBar().addPermanentWidget(self.etiqueta_usuario)
        self.statusBar().addPermanentWidget(self.etiqueta_ia)

        self.lista.currentItemChanged.connect(self._al_cambiar)
        self.cerro_sesion = False
        if self._secciones:
            self.lista.setCurrentRow(0)

    # ---------------------------------------------------------------- navegación
    def claves_visibles(self) -> list[str]:
        return [s.clave for s in self._secciones]

    def clave_actual(self) -> str | None:
        item = self.lista.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def ir_a(self, clave: str) -> None:
        for i in range(self.lista.count()):
            if self.lista.item(i).data(Qt.ItemDataRole.UserRole) == clave:
                self.lista.setCurrentRow(i)
                return

    def vista_actual(self) -> QWidget:
        return self.pila.currentWidget()

    def _al_cambiar(self, actual, _anterior):
        if actual is None:
            return
        clave = actual.data(Qt.ItemDataRole.UserRole)
        if clave not in self.vistas_creadas:
            fabrica = self._fabricas.get(clave)
            vista = fabrica(self.ctx) if fabrica else QLabel("Sección en construcción.")
            navegar = getattr(vista, "navegar", None)
            if navegar is not None:  # p. ej. las tarjetas de Inicio abren otra sección
                navegar.connect(self.ir_a)
            self.vistas_creadas[clave] = vista
            self.pila.addWidget(vista)
        else:
            # Al volver a una sección se recargan sus datos: otra pantalla pudo cambiarlos.
            vista = self.vistas_creadas[clave]
            refrescar = getattr(vista, "al_volver", None) or getattr(vista, "recargar", None)
            if refrescar:
                refrescar()
        self.pila.setCurrentWidget(self.vistas_creadas[clave])

    # ---------------------------------------------------------------- cierre
    def _cerrar_sesion(self):
        self.cerro_sesion = True
        self.sesion_cerrada.emit()
        self.close()

    def closeEvent(self, evento):
        trabajador.esperar_tareas()  # no dejar consultas de IA a medio camino
        super().closeEvent(evento)
