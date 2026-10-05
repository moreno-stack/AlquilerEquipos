"""Lógica de presentación del módulo de reportes (spec §7)."""

from datetime import date, timedelta

from alquiler.models import ConceptoPago
from alquiler.services import reportes as svc
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import pesos

MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _pct(valor: float) -> str:
    return f"{valor:.1f} %".replace(".", ",")


def _meses(desde: date, hasta: date) -> list[str]:
    claves, anio, mes = [], desde.year, desde.month
    while (anio, mes) <= (hasta.year, hasta.month):
        claves.append(f"{anio:04d}-{mes:02d}")
        anio, mes = (anio, mes + 1) if mes < 12 else (anio + 1, 1)
    return claves


def _etiqueta_mes(clave: str, desde: date, hasta: date) -> str:
    """'mar 2026', o 'mar 2026*' si el período no cubre el mes completo."""
    etiqueta = f"{MESES_CORTOS[int(clave[5:]) - 1]} {clave[:4]}"
    fin_de_mes = (hasta.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    parcial = ((clave == f"{hasta:%Y-%m}" and hasta != fin_de_mes)
               or (clave == f"{desde:%Y-%m}" and desde.day != 1))
    return f"{etiqueta}*" if parcial else etiqueta


def generar(ctx: Contexto, desde: date, hasta: date) -> dict:
    hoy = ctx.hoy()

    def construir(s, a):
        ingresos = svc.ingresos(s, a, desde, hasta)
        uso = svc.uso_flota(s, a, desde, hasta, hoy)
        categorias = svc.uso_por_categoria(s, a, desde, hasta, hoy)
        mora = svc.morosidad(s, a, ctx.config.factor_mora, hoy)
        return ingresos, uso, categorias, mora

    ingresos, uso, categorias, mora = ctx.ejecutar(construir)
    meses = _meses(desde, hasta)
    return {
        "kpis": [
            ("Ingresos del período", pesos(ingresos.total)),
            ("Por alquiler", pesos(ingresos.por_concepto[ConceptoPago.ALQUILER])),
            ("Por mora", pesos(ingresos.por_concepto[ConceptoPago.MORA])),
            ("Por daños", pesos(ingresos.por_concepto[ConceptoPago.DANOS])),
            ("Devoluciones tardías", _pct(100 * mora.tasa_retraso)),
            ("Alquileres vencidos hoy", str(len(mora.vencidos))),
        ],
        "ingresos_mes": [(_etiqueta_mes(m, desde, hasta), ingresos.por_mes.get(m, 0))
                         for m in meses],
        "uso_equipos": [{
            "codigo": u.codigo, "nombre": u.nombre, "categoria": u.categoria,
            "dias": u.dias_alquilado, "dias__orden": u.dias_alquilado,
            "porcentaje": _pct(u.porcentaje), "porcentaje__orden": u.porcentaje,
        } for u in uso],
        "uso_categorias": sorted(categorias.items(), key=lambda kv: -kv[1]),
        "vencidos": [{
            "cliente": v.cliente, "equipo": v.equipo, "dias": v.dias_vencido,
            "dias__orden": v.dias_vencido, "mora": pesos(v.mora_estimada),
            "mora__orden": v.mora_estimada,
        } for v in mora.vencidos],
    }
