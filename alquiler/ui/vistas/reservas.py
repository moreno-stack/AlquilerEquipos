"""Vista de reservas no entregadas: pendientes, listas para entregar y vencidas."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from alquiler.ui import widgets
from alquiler.ui.logica import operaciones
from alquiler.ui.logica.contexto import Contexto

COLUMNAS = [("cliente", "Cliente"), ("equipo", "Equipo"), ("inicio", "Inicio"),
            ("fin", "Devolución prevista"), ("situacion", "Situación"), ("costo", "Costo")]


class VistaReservas(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado(
            "Reservas", "Equipos apartados que aún no se han entregado al cliente."))
        leyenda = QHBoxLayout()
        for texto, tono in (("pendiente: inicia más adelante", "reserva"),
                            ("lista para entregar: ya puede salir", "ok"),
                            ("vencida: pasó su fecha; cancélela", "peligro")):
            leyenda.addWidget(widgets.Insignia(texto, tono))
        leyenda.addStretch()
        capa.addLayout(leyenda)
        self.tabla = widgets.Tabla()
        capa.addWidget(self.tabla, 1)
        self.botones: dict = {}
        acciones = QHBoxLayout()
        if ctx.puede("alquileres.gestionar"):
            self.botones["entregar"] = widgets.boton("Entregar equipo", "primario", self._entregar)
            self.botones["cancelar"] = widgets.boton("Cancelar reserva", "peligro", self._cancelar)
        for b in self.botones.values():
            acciones.addWidget(b)
        acciones.addStretch()
        self.etiqueta_resumen = QLabel()
        acciones.addWidget(self.etiqueta_resumen)
        capa.addLayout(acciones)
        self.recargar()

    def recargar(self):
        filas = operaciones.reservas(self.ctx)
        self.tabla.cargar(COLUMNAS, filas,
                          resaltar=lambda f: "peligro" if f["situacion"] == "vencida" else None,
                          colores={"situacion": widgets.tono_para})
        vencidas = sum(1 for f in filas if f["situacion"] == "vencida")
        self.etiqueta_resumen.setText(
            f"{len(filas)} {'reserva' if len(filas) == 1 else 'reservas'} · "
            f"{vencidas} {'vencida' if vencidas == 1 else 'vencidas'}")

    def _seleccion(self) -> dict | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            widgets.mostrar_error(self, "Seleccione una reserva de la tabla.")
        return fila

    def _entregar(self):
        fila = self._seleccion()
        if fila and widgets.ejecutar_accion(self, lambda: operaciones.entregar_reserva(self.ctx, fila["id"])):
            self.recargar()

    def _cancelar(self):
        fila = self._seleccion()
        if fila and widgets.confirmar(self, f"¿Cancelar la reserva de {fila['equipo']}?") \
                and widgets.ejecutar_accion(self, lambda: operaciones.cancelar_reserva(self.ctx, fila["id"])):
            self.recargar()
