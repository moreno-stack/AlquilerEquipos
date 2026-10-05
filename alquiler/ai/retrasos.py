"""Análisis de patrones de retraso en devoluciones (spec §6.3).

Usa una tasa suavizada (r + k·p) / (n + k) que acerca a la media global a quien
tiene pocas devoluciones, para no señalar a nadie por un caso aislado.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.ai.resultado import Resultado
from alquiler.auth import Permiso, requerir_permiso
from alquiler.models import (
    Devolucion,
    EstadoRecomendacion,
    Nivel,
    RecomendacionIA,
    TipoRecomendacion,
    Usuario,
)

K_SUAVIZADO = 5
MIN_DEVOLUCIONES = 3
ADVERTENCIA = (
    "Estimación basada en el historial de devoluciones: describe un patrón pasado, no una "
    "certeza sobre el comportamiento futuro de una persona. Úsela para revisar condiciones "
    "(depósito, plazos), no para negar el servicio sin revisión humana."
)


@dataclass
class AnalisisRetrasos:
    tasa_global: float
    n_devoluciones: int
    clientes_marcados: list[Resultado]
    por_categoria: list[Resultado]


def tasa_suavizada(retrasos: int, n: int, p_global: float, k: int = K_SUAVIZADO) -> float:
    return (retrasos + k * p_global) / (n + k)


def _pct(x: float) -> str:
    return f"{100 * x:.1f} %".replace(".", ",")


def _confianza(n: int) -> Nivel:
    return Nivel.BAJA if n < 5 else Nivel.MEDIA if n < 15 else Nivel.ALTA


def _evaluar_cliente(nombre: str, devs: list[Devolucion], p: float, total: int) -> Resultado:
    n = len(devs)
    tardias = [d for d in devs if d.dias_retraso > 0]
    r = len(tardias)
    suavizada = tasa_suavizada(r, n, p)
    dias_prom = sum(d.dias_retraso for d in tardias) / r if r else 0.0
    categorias = Counter(d.alquiler.equipo.categoria.nombre for d in tardias)
    categoria = min(categorias, key=lambda c: (-categorias[c], c)) if categorias else None
    confianza = _confianza(n)
    return Resultado(
        resumen=f"{nombre}: riesgo estimado de devolución tardía ≈{_pct(suavizada)}.",
        valor=round(suavizada, 4),
        confianza=confianza,
        indicadores={
            "cliente_id": devs[0].alquiler.cliente_id,
            "n": n,
            "retrasos": r,
            "tasa_observada": round(r / n, 4),
            "tasa_suavizada": round(suavizada, 4),
            "dias_promedio_retraso": round(dias_prom, 2),
            "categoria_mas_asociada": categoria,
        },
        justificacion=[
            f"{nombre}: {r} de {n} devoluciones con retraso (tasa observada {_pct(r / n)}).",
            f"Tasa global del sistema: {_pct(p)} sobre {total} devoluciones.",
            f"Tasa suavizada = ({r} + {K_SUAVIZADO}×{p:.2f}) / ({n} + {K_SUAVIZADO}) = "
            f"{_pct(suavizada)}: el suavizado acerca a la media a quien tiene pocas devoluciones.",
            f"Se marca porque {_pct(suavizada)} supera el doble de la tasa global "
            f"({_pct(2 * p)}) y tiene al menos {MIN_DEVOLUCIONES} devoluciones.",
            f"Retraso promedio: {dias_prom:.1f} días; categoría más asociada: {categoria}.",
            f"Confianza {confianza.value}: basada en {n} devoluciones del cliente.",
        ],
        advertencia=ADVERTENCIA,
    )


def _evaluar_categoria(nombre: str, devs: list[Devolucion], p: float) -> Resultado:
    n = len(devs)
    r = sum(1 for d in devs if d.dias_retraso > 0)
    suavizada = tasa_suavizada(r, n, p)
    return Resultado(
        resumen=f"{nombre}: tasa estimada de devolución tardía ≈{_pct(suavizada)}.",
        valor=round(suavizada, 4),
        confianza=_confianza(n),
        indicadores={"categoria": nombre, "n": n, "retrasos": r,
                     "tasa_observada": round(r / n, 4), "tasa_suavizada": round(suavizada, 4)},
        justificacion=[
            f"{r} de {n} devoluciones con retraso (observada {_pct(r / n)}).",
            f"Suavizada hacia la tasa global {_pct(p)}: {_pct(suavizada)}.",
        ],
        advertencia=ADVERTENCIA,
    )


def _persistir(session: Session, r: Resultado) -> None:
    cliente_id = r.indicadores["cliente_id"]
    rec = session.scalar(select(RecomendacionIA).where(
        RecomendacionIA.tipo == TipoRecomendacion.RETRASO,
        RecomendacionIA.cliente_id == cliente_id,
        RecomendacionIA.estado == EstadoRecomendacion.PENDIENTE,
    ))
    if rec is None:
        rec = RecomendacionIA(tipo=TipoRecomendacion.RETRASO, cliente_id=cliente_id)
        session.add(rec)
    rec.puntaje = round(100 * r.valor, 2)
    rec.prioridad = Nivel.ALTA if r.valor >= 0.5 else Nivel.MEDIA
    rec.confianza = r.confianza
    rec.resumen = r.resumen
    rec.justificacion = list(r.justificacion)
    rec.datos_respaldo = dict(r.indicadores)


def analizar_retrasos(session: Session, actor: Usuario, persistir: bool = True) -> AnalisisRetrasos:
    requerir_permiso(actor, Permiso.IA_VER)
    devoluciones = list(session.scalars(select(Devolucion)))
    total = len(devoluciones)
    if total == 0:
        return AnalisisRetrasos(0.0, 0, [], [])
    p = sum(1 for d in devoluciones if d.dias_retraso > 0) / total

    por_cliente: dict[int, list[Devolucion]] = defaultdict(list)
    por_categoria: dict[str, list[Devolucion]] = defaultdict(list)
    for d in devoluciones:
        por_cliente[d.alquiler.cliente_id].append(d)
        por_categoria[d.alquiler.equipo.categoria.nombre].append(d)

    marcados = []
    if p > 0:
        for devs in por_cliente.values():
            r = sum(1 for d in devs if d.dias_retraso > 0)
            if len(devs) >= MIN_DEVOLUCIONES and tasa_suavizada(r, len(devs), p) > 2 * p:
                marcados.append(_evaluar_cliente(devs[0].alquiler.cliente.nombre, devs, p, total))
    marcados.sort(key=lambda r: -r.valor)
    categorias = sorted((_evaluar_categoria(c, devs, p) for c, devs in por_categoria.items()),
                        key=lambda r: (-r.valor, r.indicadores["categoria"]))
    if persistir:
        for r in marcados:
            _persistir(session, r)
        session.commit()
    return AnalisisRetrasos(round(p, 4), total, marcados, categorias)
