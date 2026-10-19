"""Ventana principal estilo "centro de control": barra lateral por rol con el estado del
sistema, barra superior global (búsqueda y diagnóstico) y vistas creadas al primer uso sobre
un fondo de red de datos."""

from collections.abc import Callable

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from alquiler import __version__
from alquiler.ui import animacion, iconos, tema, trabajador, widgets
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.navegacion import secciones_para


class VentanaPrincipal(QMainWindow):
    sesion_cerrada = Signal()

    def __init__(self, ctx: Contexto, fabricas: dict[str, Callable[[Contexto], QWidget]]):
        super().__init__()
        self.ctx, self._fabricas = ctx, fabricas
        self._secciones = secciones_para(ctx)
        self.vistas_creadas: dict[str, QWidget] = {}
        self.animacion_seccion = None
        self.setWindowTitle("Sistema Inteligente de Alquiler de Equipos")
        self.resize(1280, 800)

        lateral = QWidget()
        lateral.setObjectName("panelLateral")
        lateral.setFixedWidth(236)
        capa_lateral = QVBoxLayout(lateral)
        capa_lateral.setContentsMargins(0, 0, 0, 0)
        marca = widgets.marca("Alquiler de Equipos")
        submarca = QLabel(f"Panel del sistema · v{__version__}")
        submarca.setObjectName("submarca")
        self.lista = QListWidget()
        self.lista.setObjectName("barraLateral")
        self.lista.setIconSize(QSize(20, 20))
        for s in self._secciones:
            item = QListWidgetItem(iconos.icono(s.clave, tema.PALETA["texto_lateral"],
                                                tema.PALETA["sobre_acento"]), s.titulo)
            item.setData(Qt.ItemDataRole.UserRole, s.clave)
            self.lista.addItem(item)
        self.boton_cerrar_sesion = widgets.boton("Cerrar sesión", "salir", self._cerrar_sesion)
        self.boton_cerrar_sesion.setIcon(iconos.icono("salir", tema.PALETA["texto_lateral"]))
        self.boton_cerrar_sesion.setIconSize(QSize(18, 18))
        for w in (marca, submarca, self.lista):
            capa_lateral.addWidget(w)
        capa_lateral.addWidget(self._estado_del_sistema(ctx))
        capa_lateral.addWidget(self.boton_cerrar_sesion)

        self.pila = QStackedWidget()
        cuerpo = QWidget()
        capa = QHBoxLayout(cuerpo)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(lateral)
        self.fondo = widgets.FondoCosmico(fps=10)  # deriva lenta: 10 cuadros bastan y no cargan el equipo
        capa_contenido = QVBoxLayout(self.fondo)
        capa_contenido.setContentsMargins(24, 16, 24, 16)
        capa_contenido.setSpacing(12)
        capa_contenido.addLayout(self._barra_superior())
        capa_contenido.addWidget(self.pila, 1)
        capa.addWidget(self.fondo, 1)
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

    # ---------------------------------------------------------------- piezas del marco
    def _estado_del_sistema(self, ctx: Contexto) -> QFrame:
        """Módulo "Estado del sistema": base de datos, IA, última actualización y nodo."""
        panel = QFrame()
        panel.setObjectName("estadoSistema")
        capa = QVBoxLayout(panel)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(6)
        titulo = QLabel("ESTADO DEL SISTEMA")
        titulo.setObjectName("tituloModulo")
        capa.addWidget(titulo)

        def fila_barra(nombre: str, valor: int, texto: str) -> tuple[QProgressBar, QLabel]:
            cabecera = QHBoxLayout()
            etiqueta = QLabel(nombre)
            etiqueta.setObjectName("datoSistema")
            estado = QLabel(texto)
            estado.setObjectName("valorSistema")
            cabecera.addWidget(etiqueta)
            cabecera.addStretch(1)
            cabecera.addWidget(estado)
            barra = QProgressBar()
            barra.setObjectName("barraNeon")
            barra.setRange(0, 100)
            barra.setValue(valor)
            barra.setTextVisible(False)
            capa.addLayout(cabecera)
            capa.addWidget(barra)
            return barra, estado

        self.barra_base, _ = fila_barra("Base de datos", 100, "Operativa")
        self.barra_ia, self.etiqueta_estado_ia = fila_barra(
            "IA · Groq", 100 if ctx.cliente_llm else 0, "Conectada" if ctx.cliente_llm else "Sin clave")
        datos = QGridLayout()
        datos.setVerticalSpacing(2)
        for fila, (nombre, valor) in enumerate((("Última actualización", ""), ("Nodo", "Local · SQLite"))):
            etiqueta = QLabel(nombre)
            etiqueta.setObjectName("datoSistema")
            dato = QLabel(valor)
            dato.setObjectName("valorSistema")
            dato.setAlignment(Qt.AlignmentFlag.AlignRight)
            datos.addWidget(etiqueta, fila, 0)
            datos.addWidget(dato, fila, 1)
            if fila == 0:
                self.etiqueta_actualizacion = dato
        capa.addSpacing(4)
        capa.addLayout(datos)
        self._marcar_actualizacion()
        contenedor = QWidget()
        envoltura = QVBoxLayout(contenedor)
        envoltura.setContentsMargins(12, 8, 12, 0)
        envoltura.addWidget(panel)
        return contenedor

    def _marcar_actualizacion(self) -> None:
        self.etiqueta_actualizacion.setText(datetime.now().strftime("%H:%M:%S"))

    def _barra_superior(self) -> QHBoxLayout:
        """Búsqueda global de equipos y botón "Ejecutar diagnóstico" (análisis de IA)."""
        barra = QHBoxLayout()
        barra.setSpacing(10)
        barra.addStretch(1)
        self.buscador = QLineEdit()
        self.buscador.setObjectName("buscadorGlobal")
        self.buscador.setPlaceholderText("Buscar equipo por código o nombre…")
        self.buscador.setClearButtonEnabled(True)
        self.buscador.addAction(iconos.icono("buscar", tema.PALETA["texto_secundario"]),
                                QLineEdit.ActionPosition.LeadingPosition)
        self.buscador.returnPressed.connect(self._buscar)
        self.buscador.setVisible("equipos" in self.claves_visibles())
        self.boton_diagnostico = widgets.boton("EJECUTAR DIAGNÓSTICO", "primario", self._diagnosticar)
        self.boton_diagnostico.setIcon(iconos.icono("diagnostico", tema.PALETA["sobre_acento"]))
        self.boton_diagnostico.setToolTip("Abre el Análisis IA y vuelve a calcular las estimaciones")
        self.boton_diagnostico.setVisible("analisis_ia" in self.claves_visibles())
        widgets.aplicar_brillo(self.boton_diagnostico, "purpura_neon", alfa=110, radio=24)
        animacion.brillo_al_pasar(self.boton_diagnostico, factor=1.6)
        barra.addWidget(self.buscador)
        barra.addWidget(self.boton_diagnostico)
        return barra

    def _buscar(self) -> None:
        texto = self.buscador.text().strip()
        self.ir_a("equipos")
        campo = getattr(self.vistas_creadas.get("equipos"), "campo_buscar", None)
        if campo is not None:
            campo.setText(texto)

    def _diagnosticar(self) -> None:
        self.ir_a("analisis_ia")
        analizar = getattr(self.vistas_creadas.get("analisis_ia"), "analizar", None)
        if analizar is not None:
            analizar()

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
        self._marcar_actualizacion()
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
        self.animacion_seccion = animacion.fundido_entrada(self.vistas_creadas[clave],
                                                           ms=animacion.duracion("base"))

    # ---------------------------------------------------------------- cierre
    def _cerrar_sesion(self):
        self.cerro_sesion = True
        self.sesion_cerrada.emit()
        self.close()

    def closeEvent(self, evento):
        trabajador.esperar_tareas()  # no dejar consultas de IA a medio camino
        super().closeEvent(evento)
