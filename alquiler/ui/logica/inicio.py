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
_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
MAX_EVENTOS = 8
MAX_CATEGORIAS = 4
# prioridad de los eventos del monitor: lo urgente primero
_PRIORIDAD = {"VENCIDO": 0, "HOY": 1, "EN CURSO": 2, "PENDIENTE": 3, "OK": 4}
TONO_EVENTO = {"VENCIDO": "peligro", "HOY": "aviso", "EN CURSO": "aviso", "PENDIENTE": "reserva",
                "OK": "ok"}


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


def _ultimos_meses(hoy: date, n: int = 6) -> list[tuple[int, int]]:
    """(año, mes) de los ``n`` meses que terminan en el mes de ``hoy``, del más antiguo al actual."""
    meses = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        meses.append((anio, mes))
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    return meses[::-1]


def _dias(n: int) -> str:
    return f"{n} día" if n == 1 else f"{n} días"


def _evento(fecha_evento: date, modulo: str, mensaje: str, estado: str) -> dict:
    return {"fecha": fecha(fecha_evento), "modulo": modulo, "mensaje": mensaje, "estado": estado,
            "tono": TONO_EVENTO[estado], "_orden": (_PRIORIDAD[estado], -fecha_evento.toordinal())}


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

    eventos: list[dict] = []

    def calcular(s, a):
        if ctx.puede("equipos.gestionar"):  # sin este permiso solo se ven los disponibles
            equipos = svc_equipos.listar_equipos(s, a)
            conteo = Counter(e.estado for e in equipos)
            ocupados = conteo[EstadoEquipo.ALQUILADO] + conteo[EstadoEquipo.RESERVADO]
            por_categoria: dict[str, list[int]] = {}
            for e in equipos:
                cifras = por_categoria.setdefault(e.categoria.nombre, [0, 0])
                cifras[0] += e.estado is EstadoEquipo.ALQUILADO
                cifras[1] += 1
            categorias = sorted(por_categoria.items(), key=lambda kv: (-kv[1][1], kv[0]))
            datos["flota"] = {
                "conteos": [(e.value, conteo[e]) for e in _ORDEN_ESTADOS],
                "total": len(equipos),
                "disponibles": conteo[EstadoEquipo.DISPONIBLE],
                "utilizacion": round(100 * ocupados / len(equipos)) if equipos else 0,
                "por_categoria": [{"categoria": nombre, "alquilados": a_, "total": t_,
                                   "porcentaje": round(100 * a_ / t_)}
                                  for nombre, (a_, t_) in categorias[:MAX_CATEGORIAS]],
            }
        if ctx.puede("alquileres.ver"):
            activos = svc_alquileres.listar_alquileres(s, a, estado=EstadoAlquiler.ACTIVO)
            reservas = svc_alquileres.listar_alquileres(s, a, estado=EstadoAlquiler.RESERVADO)
            datos["operacion"] = {
                "activos": len(activos),
                "vencidos": sum(x.fecha_fin_prevista < hoy for x in activos),
                "vencen_hoy": sum(x.fecha_fin_prevista == hoy for x in activos),
                "reservas_pendientes": len(reservas),
            }
            meses = _ultimos_meses(hoy)
            iniciados, devueltos = [0] * len(meses), [0] * len(meses)
            for alq in svc_alquileres.listar_alquileres(s, a):
                if alq.estado is EstadoAlquiler.CANCELADO:
                    continue
                clave = (alq.fecha_inicio.year, alq.fecha_inicio.month)
                if clave in meses:
                    iniciados[meses.index(clave)] += 1
                if alq.devolucion is not None:
                    d = alq.devolucion.fecha_devolucion
                    if (d.year, d.month) in meses:
                        devueltos[meses.index((d.year, d.month))] += 1
            datos["tendencia"] = {"meses": [_MESES_CORTOS[m - 1] for _, m in meses],
                                  "iniciados": iniciados, "devueltos": devueltos}
            for x in activos:
                if x.fecha_fin_prevista < hoy:
                    eventos.append(_evento(x.fecha_fin_prevista, "Alquileres",
                                           f"{x.equipo.codigo} · {x.cliente.nombre} — devolución vencida "
                                           f"hace {_dias((hoy - x.fecha_fin_prevista).days)}", "VENCIDO"))
                elif x.fecha_fin_prevista == hoy:
                    eventos.append(_evento(hoy, "Alquileres",
                                           f"{x.equipo.codigo} · {x.cliente.nombre} — se devuelve hoy", "HOY"))
                else:
                    eventos.append(_evento(x.fecha_inicio, "Alquileres",
                                           f"{x.equipo.codigo} entregado a {x.cliente.nombre}", "OK"))
            for x in reservas:
                eventos.append(_evento(x.fecha_inicio, "Reservas",
                                       f"{x.equipo.codigo} reservado para {x.cliente.nombre} "
                                       f"desde el {fecha(x.fecha_inicio)}", "PENDIENTE"))
        if ctx.puede("mantenimiento.ver"):
            abiertos = svc_mant.mantenimientos_abiertos(s, a)
            datos["mantenimiento"] = {"abiertos": len(abiertos)}
            for m in abiertos:
                eventos.append(_evento(m.fecha_inicio, "Mantenimiento",
                                       f"{m.equipo.codigo} en taller ({m.tipo.value.capitalize()})",
                                       "EN CURSO"))
        if ctx.puede("alquileres.ver") or ctx.puede("mantenimiento.ver"):
            eventos.sort(key=lambda e: e["_orden"])
            datos["eventos"] = [{k: v for k, v in e.items() if k != "_orden"}
                                for e in eventos[:MAX_EVENTOS]]
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
