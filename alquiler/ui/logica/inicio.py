"""Lógica de la pantalla de Inicio (spec Fase 6 §3.2): indicadores por rol, sin Qt.

Solo compone servicios existentes dentro de una única sesión. Cada bloque se
incluye únicamente si el actor tiene el permiso correspondiente, así que nunca
provoca un ``PermisoDenegado``. La alerta de IA se calcula sin persistir: abrir
Inicio no debe dejar rastros en ``RecomendacionIA``.
"""

from collections import Counter
from collections.abc import Callable
from datetime import date, datetime

from alquiler.ai.mantenimiento import recomendar_mantenimiento
from alquiler.models import EstadoAlquiler, EstadoEquipo
from alquiler.services import alquileres as svc_alquileres
from alquiler.services import clientes as svc_clientes
from alquiler.services import equipos as svc_equipos
from alquiler.services import mantenimiento as svc_mant
from alquiler.services import reportes as svc_reportes
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import fecha, pesos

_DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
_ORDEN_ESTADOS = (EstadoEquipo.DISPONIBLE, EstadoEquipo.ALQUILADO, EstadoEquipo.RESERVADO,
                  EstadoEquipo.EN_MANTENIMIENTO, EstadoEquipo.FUERA_DE_SERVICIO)
_PRUDENCIA = {"baja": 0, "media": 1, "alta": 2}  # ante empate gana la confianza más baja


def fecha_larga(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month - 1]} de {d.year}"


def saludo_para(hora: int) -> str:
    if 5 <= hora <= 11:
        return "Buenos días"
    if 12 <= hora <= 18:
        return "Buenas tardes"
    return "Buenas noches"


def texto_alerta(n: int) -> str:
    if n == 0:
        return "Estimación: ningún equipo supera el umbral de revisión"
    return f"Estimación: {n} equipo{'' if n == 1 else 's'} a revisar"


def confianza_predominante(niveles: list[str]) -> str:
    if not niveles:
        return ""
    conteo = Counter(niveles)
    return min(conteo, key=lambda n: (-conteo[n], _PRUDENCIA.get(n, -1)))


# ---------------------------------------------------------------- resumen
def resumen(ctx: Contexto, ahora: Callable[[], datetime] = datetime.now) -> dict:
    hoy, u = ctx.hoy(), ctx.usuario
    datos: dict = {"saludo": {"texto": f"{saludo_para(ahora().hour)}, {u.nombre}",
                              "fecha": fecha_larga(hoy)}}

    def calcular(s, a):
        if ctx.puede("equipos.gestionar"):  # sin este permiso solo se ven los disponibles
            equipos = svc_equipos.listar_equipos(s, a)
            conteo = Counter(e.estado for e in equipos)
            datos["flota"] = {"conteos": [(e.value, conteo[e]) for e in _ORDEN_ESTADOS],
                              "total": len(equipos),
                              "disponibles": conteo[EstadoEquipo.DISPONIBLE]}
        if ctx.puede("alquileres.ver"):
            activos = svc_alquileres.listar_alquileres(s, a, estado=EstadoAlquiler.ACTIVO)
            reservas = svc_alquileres.listar_alquileres(s, a, estado=EstadoAlquiler.RESERVADO)
            datos["operacion"] = {
                "activos": len(activos),
                "vencidos": sum(x.fecha_fin_prevista < hoy for x in activos),
                "vencen_hoy": sum(x.fecha_fin_prevista == hoy for x in activos),
                "reservas_pendientes": len(reservas),
            }
        if ctx.puede("mantenimiento.ver"):
            datos["mantenimiento"] = {"abiertos": len(svc_mant.mantenimientos_abiertos(s, a))}
        if ctx.puede("reportes.ver"):
            total = svc_reportes.ingresos(s, a, hoy.replace(day=1), hoy).total
            datos["ingresos_mes"] = {"valor": total, "texto": pesos(total)}
        if ctx.puede("ia.ver"):
            resultados = recomendar_mantenimiento(s, a, hoy=hoy, persistir=False)
            datos["alerta_ia"] = {
                "equipos": len(resultados),
                "confianza": confianza_predominante([r.confianza.value for r in resultados]),
                "texto": texto_alerta(len(resultados)),
            }
        if u.rol == "cliente" and u.cliente_id is not None:
            activos = [x for x in svc_clientes.historial_cliente(s, a, u.cliente_id)
                       if x.estado is EstadoAlquiler.ACTIVO]
            saldo = sum(svc_alquileres.saldo_pendiente(x) for x in activos)
            proximo = min((x.fecha_fin_prevista for x in activos), default=None)
            datos["mis_alquileres"] = {"activos": len(activos),
                                       "proximo": fecha(proximo) if proximo else None,
                                       "saldo": saldo, "saldo_texto": pesos(saldo)}

    ctx.ejecutar(calcular)
    return datos


# ---------------------------------------------------------------- tarjetas
def tarjetas_kpi(datos: dict, visibles: set[str]) -> list[dict]:
    """Tarjetas en orden fijo; ``destino`` solo si esa sección es visible para el rol."""
    tarjetas: list[dict] = []

    def agregar(clave, titulo, valor, tono, destino, detalle=""):
        tarjetas.append({"clave": clave, "titulo": titulo, "valor": str(valor), "detalle": detalle,
                         "tono": tono, "destino": destino if destino in visibles else None})

    if "flota" in datos:
        f = datos["flota"]
        agregar("disponibles", "Equipos disponibles", f"{f['disponibles']} / {f['total']}", "ok",
                "equipos", "de la flota total")
    if "operacion" in datos:
        o = datos["operacion"]
        agregar("activos", "Alquileres activos", o["activos"], "info", "alquileres")
        agregar("vencidos", "Vencidos", o["vencidos"], "peligro" if o["vencidos"] else "neutro",
                "alquileres", "pasaron su fecha de entrega" if o["vencidos"] else "todo al día")
        agregar("vencen_hoy", "Vencen hoy", o["vencen_hoy"], "aviso" if o["vencen_hoy"] else "neutro",
                "alquileres")
        agregar("reservas", "Reservas por entregar", o["reservas_pendientes"], "reserva", "reservas")
    if "mantenimiento" in datos:
        agregar("mantenimiento", "En mantenimiento", datos["mantenimiento"]["abiertos"], "aviso",
                "mantenimiento", "órdenes abiertas")
    if "ingresos_mes" in datos:
        agregar("ingresos", "Ingresos del mes", datos["ingresos_mes"]["texto"], "marca", "reportes",
                "pagos registrados desde el día 1")
    if "mis_alquileres" in datos:
        m = datos["mis_alquileres"]
        agregar("mis_activos", "Mis alquileres activos", m["activos"], "info", "perfil",
                f"próxima entrega: {m['proximo']}" if m["proximo"] else "")
        agregar("mi_saldo", "Saldo pendiente", m["saldo_texto"],
                "aviso" if m["saldo"] > 0 else "ok", "perfil")
    return tarjetas
