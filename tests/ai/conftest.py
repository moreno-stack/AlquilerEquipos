"""Fixtures del módulo de IA: reutiliza las de servicios y añade historial sintético."""

from datetime import date, timedelta

from alquiler.models import Alquiler, Devolucion, EstadoAlquiler
from tests.services.conftest import (  # noqa: F401  (fixtures re-exportadas)
    HOY,
    admin,
    categoria,
    cliente,
    empleado,
    equipo,
    nuevo_usuario,
    usuario_cliente,
)


def alquilar(session, cliente, equipo, inicio: date, dias: int = 2, retraso: int | None = 0,
             estado=EstadoAlquiler.FINALIZADO):
    """Inserta un alquiler sintético; con ``retraso`` no nulo registra su devolución."""
    fin = inicio + timedelta(days=dias)
    alquiler = Alquiler(cliente=cliente, equipo=equipo, fecha_inicio=inicio,
                        fecha_fin_prevista=fin, tarifa_diaria=equipo.tarifa_diaria,
                        costo_estimado=dias * equipo.tarifa_diaria, estado=estado)
    session.add(alquiler)
    if retraso is not None and estado is EstadoAlquiler.FINALIZADO:
        session.add(Devolucion(alquiler=alquiler, fecha_devolucion=fin + timedelta(days=retraso),
                               dias_retraso=retraso, recargo_mora=0, horas_uso=4,
                               total=alquiler.costo_estimado))
    return alquiler
