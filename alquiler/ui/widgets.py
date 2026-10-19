"""Componentes visuales comunes: estilo, tablas, insignias, tarjetas de IA y diálogos."""

from collections.abc import Callable

from PySide6.QtCore import QLocale, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from alquiler.errors import ReglaNegocioError
from alquiler.ui import animacion, iconos, tema
from alquiler.ui.logo import Logo
from alquiler.ui.centro import (  # noqa: F401  (se reexportan para las vistas)
    FondoCosmico,
    GraficoDona,
    GraficoTendencia,
    Panel,
    TextoDegradado,
    aplicar_brillo,
)

# ---------------------------------------------------------------- estilo
TONOS = tema.TONOS  # tono: (fondo, texto)
_GRIS = tema.PALETA["texto_secundario"]
_TONO_POR_VALOR = {
    # estados del equipo
    "Disponible": "ok", "Alquilado": "info", "Reservado": "reserva",
    "En mantenimiento": "aviso", "Fuera de servicio": "peligro",
    # alquileres y reservas
    "activo": "info", "reservado": "reserva", "finalizado": "neutro", "cancelado": "neutro",
    "al día": "ok", "vencido": "peligro", "vencida": "peligro", "pendiente": "reserva",
    "lista para entregar": "ok",
    # confianza de una estimación
    "alta": "ok", "media": "aviso", "baja": "peligro",
    # cuentas de usuario
    "Activo": "ok", "Inactivo": "neutro",
}
TONO_PRIORIDAD = {"alta": "peligro", "media": "aviso", "baja": "neutro"}

ESTILO = tema.hoja_de_estilo()


def configurar_locale() -> None:
    """Español (Colombia): '$40.000' y '2,5' también en los campos numéricos de Qt."""
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Colombia))


def tono_para(valor: str) -> str:
    return _TONO_POR_VALOR.get(valor, "neutro")


# ---------------------------------------------------------------- piezas
class Insignia(QLabel):
    def __init__(self, texto: str = "", tono: str = "neutro", parent=None):
        super().__init__(parent)
        self.set_valor(texto, tono)

    def set_valor(self, texto: str, tono: str = "neutro") -> None:
        self.tono = tono
        fondo, color = TONOS.get(tono, TONOS["neutro"])
        self.setText(texto)
        self.setStyleSheet(f"background:{fondo}; color:{color}; border-radius:10px;"
                           "padding:2px 10px; font-weight:600; font-size:12px;")


def encabezado(titulo: str, subtitulo: str = "") -> QWidget:
    caja = QWidget()
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 8)
    t = QLabel(titulo)
    t.setObjectName("tituloVista")
    capa.addWidget(t)
    if subtitulo:
        s = QLabel(subtitulo)
        s.setObjectName("subtituloVista")
        s.setWordWrap(True)
        capa.addWidget(s)
    return caja


def marca(texto: str) -> QWidget:
    """Logotipo: cubo neural + nombre (barra lateral)."""
    caja = QWidget()
    caja.setObjectName("marca")
    capa = QHBoxLayout(caja)
    capa.setContentsMargins(18, 20, 18, 0)
    capa.setSpacing(10)
    cuadro = Logo(26)
    nombre = QLabel(texto)
    nombre.setObjectName("marcaNombre")
    capa.addWidget(cuadro)
    capa.addWidget(nombre, 1)
    caja.nombre = nombre
    return caja


def boton(texto: str, rol: str = "", al_click: Callable | None = None) -> "QPushButton":
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(texto)
    if rol:
        b.setObjectName(rol)
    if al_click:
        b.clicked.connect(al_click)
    return b


# ---------------------------------------------------------------- tabla
_FILA = Qt.ItemDataRole.UserRole
_ORDEN = Qt.ItemDataRole.UserRole + 1
_TONO = Qt.ItemDataRole.UserRole + 2


class Tabla(QTableView):
    """Tabla de solo lectura cargada desde ``list[dict]``.

    Una clave ``<columna>__orden`` en la fila define el valor de ordenamiento
    (p. ej. el número detrás de "$1.250.000").
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modelo = QStandardItemModel(self)
        self._modelo.setSortRole(_ORDEN)
        self._filas: list[dict] = []
        self.setModel(self._modelo)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().hide()
        self.horizontalHeader().setStretchLastSection(True)

    def cargar(self, columnas: list[tuple[str, str]], filas: list[dict],
               resaltar: Callable[[dict], str | None] | None = None,
               colores: dict[str, Callable[[str], str]] | None = None) -> None:
        self.setSortingEnabled(False)
        self._modelo.clear()
        self._filas = list(filas)
        self._modelo.setHorizontalHeaderLabels([titulo for _, titulo in columnas])
        for i, fila in enumerate(self._filas):
            tono = resaltar(fila) if resaltar else None
            items = []
            for clave, _ in columnas:
                valor = fila.get(clave)
                item = QStandardItem("" if valor is None else str(valor))
                item.setData(fila.get(f"{clave}__orden", item.text()), _ORDEN)
                if tono:
                    item.setBackground(QColor(TONOS[tono][0]))
                    item.setData(tono, _TONO)
                if colores and clave in colores:
                    fondo, texto = TONOS[colores[clave](item.text())]
                    item.setBackground(QColor(fondo))
                    item.setForeground(QColor(texto))
                items.append(item)
            items[0].setData(i, _FILA)
            self._modelo.appendRow(items)
        # Conserva el orden de llegada hasta que el usuario haga clic en una cabecera.
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()

    def seleccionada(self) -> dict | None:
        filas = self.selectionModel().selectedRows()
        if not filas:
            return None
        return self._filas[self._modelo.item(filas[0].row(), 0).data(_FILA)]

    def filas_mostradas(self) -> int:
        return self._modelo.rowCount()

    def texto(self, fila: int, columna: int) -> str:
        return self._modelo.item(fila, columna).text()

    def tono_fila(self, fila: int) -> str | None:
        return self._modelo.item(fila, 0).data(_TONO)


# ---------------------------------------------------------------- inicio
class TarjetaKPI(QFrame):
    """Indicador del tablero: título en versalitas, ícono en caja de color, valor grande, detalle
    y una línea neón inferior del color del tono.

    Si tiene ``destino`` (clave de sección), un clic emite ``activada(destino)``.
    """

    activada = Signal(str)

    def __init__(self, datos: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjetaKpi")
        self.destino = datos.get("destino")
        self.setProperty("navegable", bool(self.destino))
        if self.destino:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Abrir la sección")
        tono = datos.get("tono", "neutro")
        color = tema.COLOR_TONO.get(tono, tema.COLOR_TONO["neutro"])
        fondo_icono = tema.TONOS.get(tono, tema.TONOS["neutro"])[0]
        capa = QVBoxLayout(self)
        capa.setContentsMargins(16, 14, 16, 0)
        capa.setSpacing(4)
        cabecera = QHBoxLayout()
        self.etiqueta_titulo = QLabel(datos.get("titulo", ""))
        self.etiqueta_titulo.setObjectName("tituloModulo")
        cabecera.addWidget(self.etiqueta_titulo, 1)
        self.etiqueta_icono = None
        if datos.get("icono"):
            self.etiqueta_icono = QLabel()
            self.etiqueta_icono.setFixedSize(34, 34)
            self.etiqueta_icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.etiqueta_icono.setStyleSheet(f"background: {fondo_icono}; border-radius: 9px;")
            self.etiqueta_icono.setPixmap(iconos.icono(datos["icono"], color).pixmap(18, 18))
            cabecera.addWidget(self.etiqueta_icono)
        capa.addLayout(cabecera)
        self.etiqueta_valor = QLabel(str(datos.get("valor", "")))
        self.etiqueta_valor.setObjectName("kpiValor")
        self.etiqueta_detalle = QLabel(datos.get("detalle") or "")
        self.etiqueta_detalle.setObjectName("kpiDetalle")
        self.etiqueta_detalle.setVisible(bool(datos.get("detalle")))
        capa.addWidget(self.etiqueta_valor)
        capa.addWidget(self.etiqueta_detalle)
        capa.addStretch(1)
        franja = QFrame()
        franja.setObjectName("kpiFranja")
        franja.setFixedHeight(3)
        franja.setStyleSheet(f"background: {color}; border: none; border-radius: 1px;")
        capa.addSpacing(10)
        capa.addWidget(franja)
        self.setMinimumHeight(128)
        aplicar_brillo(self, "acento", alfa=38, radio=26)
        animacion.brillo_al_pasar(self)

    def mouseReleaseEvent(self, evento):
        if self.destino and evento.button() == Qt.MouseButton.LeftButton:
            self.activada.emit(self.destino)
        super().mouseReleaseEvent(evento)


class _Barra(QWidget):
    def __init__(self, padre: "BarraEstados"):
        super().__init__(padre)
        self._padre = padre
        self.setFixedHeight(18)

    def paintEvent(self, _evento):
        segmentos = self._padre.segmentos()
        total = sum(n for _, n, _ in segmentos)
        if not total:
            return
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(Qt.PenStyle.NoPen)
        x, ancho = 0.0, float(self.width())
        for _, n, color in segmentos:
            w = ancho * n / total
            pintor.setBrush(QColor(color))
            pintor.drawRect(QRectF(x, 0, w, self.height()))
            x += w
        pintor.end()


class BarraEstados(QWidget):
    """Barra apilada con la cantidad de equipos por estado y su leyenda."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conteos: list[tuple[str, int]] = []
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        self.barra = _Barra(self)
        self.leyenda = QLabel()
        self.leyenda.setObjectName("kpiDetalle")
        self.leyenda.setWordWrap(True)
        self.etiqueta_vacia = QLabel("Sin equipos registrados")
        self.etiqueta_vacia.setObjectName("subtituloVista")
        for w in (self.barra, self.leyenda, self.etiqueta_vacia):
            capa.addWidget(w)
        self.cargar([])

    def cargar(self, conteos: list[tuple[str, int]]) -> None:
        self._conteos = list(conteos)
        vacia = not any(n for _, n in self._conteos)
        self.barra.setVisible(not vacia)
        self.leyenda.setVisible(not vacia)
        self.etiqueta_vacia.setVisible(vacia)
        self.leyenda.setTextFormat(Qt.TextFormat.RichText)
        self.leyenda.setText("&nbsp;&nbsp;&nbsp;".join(
            f"<span style='color:{tema.COLOR_ESTADO[estado][0]}'>■</span> {estado} <b>{n}</b>"
            for estado, n in self._conteos))
        self.barra.update()

    def texto_leyenda(self) -> str:
        return " · ".join(f"{estado} {n}" for estado, n in self._conteos)

    def segmentos(self) -> list[tuple[str, int, str]]:
        return [(estado, n, tema.COLOR_ESTADO[estado][0]) for estado, n in self._conteos if n]


# ---------------------------------------------------------------- tarjeta de IA
class TarjetaResultado(QFrame):
    """Una estimación de IA: nunca se presenta sin su confianza y su justificación."""

    def __init__(self, datos: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)

        fila = QHBoxLayout()
        self.insignia_estimacion = Insignia("Estimación", "info")
        self.insignia_confianza = Insignia(f"Confianza {datos['confianza'].capitalize()}",
                                           tono_para(datos["confianza"]))
        fila.addWidget(self.insignia_estimacion)
        fila.addWidget(self.insignia_confianza)
        self.insignias_extra = [Insignia(texto, tono) for texto, tono in datos.get("insignias", [])]
        for insignia in self.insignias_extra:
            fila.addWidget(insignia)
        fila.addStretch()
        capa.addLayout(fila)

        self.etiqueta_resumen = QLabel(datos["resumen"])
        self.etiqueta_resumen.setWordWrap(True)
        self.etiqueta_resumen.setStyleSheet("font-size:14px; font-weight:600; margin-top:4px;")
        capa.addWidget(self.etiqueta_resumen)

        self.boton_detalle = QToolButton()
        self.boton_detalle.setText("Ver justificación ▾")
        self.boton_detalle.setObjectName("enlace")
        self.boton_detalle.clicked.connect(self._alternar)
        capa.addWidget(self.boton_detalle, alignment=Qt.AlignmentFlag.AlignLeft)

        self.detalle = QLabel()
        self.detalle.setWordWrap(True)
        self.detalle.setTextFormat(Qt.TextFormat.RichText)
        pasos = "".join(f"<li>{j}</li>" for j in datos["justificacion"])
        indicadores = "".join(f"<tr><td style='color:{_GRIS};padding-right:12px'>{k}</td>"
                              f"<td>{v}</td></tr>" for k, v in datos.get("indicadores", []))
        self.detalle.setText(f"<b>Cómo se calculó</b><ol>{pasos}</ol>"
                             + (f"<b>Indicadores</b><table>{indicadores}</table>" if indicadores else ""))
        self.detalle.hide()
        capa.addWidget(self.detalle)

        advertencia = QLabel(datos["advertencia"])
        advertencia.setObjectName("advertencia")
        advertencia.setWordWrap(True)
        capa.addWidget(advertencia)

    def _alternar(self):
        visible = self.detalle.isHidden()
        self.detalle.setVisible(visible)
        self.boton_detalle.setText("Ocultar justificación ▴" if visible else "Ver justificación ▾")

    def detalle_texto(self) -> str:
        return self.detalle.text()


# ---------------------------------------------------------------- diálogos y acciones
def botones_dialogo(dialogo: QDialog) -> QDialogButtonBox:
    """Guardar/Cancelar. Guardar se deshabilita al primer clic: un doble clic no
    puede aceptar el diálogo dos veces."""
    caja = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                            | QDialogButtonBox.StandardButton.Cancel)
    guardar = caja.button(QDialogButtonBox.StandardButton.Ok)
    guardar.setText("Guardar")
    guardar.setObjectName("primario")
    caja.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    caja.accepted.connect(lambda: guardar.setEnabled(False))
    caja.accepted.connect(dialogo.accept)
    caja.rejected.connect(dialogo.reject)
    dialogo.boton_guardar = guardar
    return caja


def ejecutar_dialogo(dialogo: QDialog) -> bool:
    """Muestra un diálogo modal; las pruebas reemplazan esta función."""
    return dialogo.exec() == QDialog.DialogCode.Accepted


def ejecutar_accion(parent: QWidget | None, accion: Callable[[], object]) -> bool:
    """Ejecuta una acción de la interfaz y muestra cualquier error sin traceback."""
    try:
        accion()
    except ReglaNegocioError as e:
        mostrar_error(parent, str(e))
        return False
    except Exception as e:
        mostrar_error(parent, f"Error inesperado: {type(e).__name__}: {e}")
        return False
    return True


def mostrar_error(parent: QWidget | None, mensaje: str) -> None:
    QMessageBox.warning(parent, "No se pudo completar la acción", mensaje)


def informar(parent: QWidget | None, mensaje: str) -> None:
    QMessageBox.information(parent, "Listo", mensaje)


def confirmar(parent: QWidget | None, texto: str) -> bool:
    respuesta = QMessageBox.question(parent, "Confirmar", texto)
    return respuesta == QMessageBox.StandardButton.Yes
