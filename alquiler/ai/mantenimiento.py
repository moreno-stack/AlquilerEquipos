"""Recomendador de mantenimiento preventivo (spec §6.2).

Puntaje 0–100 = suma ponderada de cuatro factores normalizados en [0, 1].
Cada factor se reporta con su valor bruto y su aporte en puntos.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.ai.resultado import Resultado
from alquiler.auth import Permiso, requerir_permiso
from alquiler.models import (
    Equipo,
    EstadoAlquiler,
    EstadoEquipo,
    EstadoRecomendacion,
    Nivel,
    RecomendacionIA,
    TipoMantenimiento,
    TipoRecomendacion,
    Usuario,
)

PESOS = {
    "usos_desde_servicio": 35.0,
    "dias_desde_servicio": 25.0,
    "intensidad_reciente": 15.0,
    "fallas_12m": 25.0,
}
FALLAS_REFERENCIA = 3
UMBRAL_ALTA, UMBRAL_MEDIA = 75.0, 50.0
EVALUABLES = (EstadoEquipo.DISPONIBLE, EstadoEquipo.ALQUILADO, EstadoEquipo.RESERVADO)
ADVERTENCIA = (
    "Estimación basada en uso y fallas registrados; no reemplaza la inspección técnica. "
    "Un equipo con puntaje bajo también puede fallar."
)


def _alquileres_30d(equipo: Equipo, hoy: date) -> int:
    desde = hoy - timedelta(days=30)
    return sum(1 for a in equipo.alquileres
               if a.estado is not EstadoAlquiler.CANCELADO and desde < a.fecha_inicio <= hoy)


def _prioridad(puntaje: float) -> Nivel:
    if puntaje >= UMBRAL_ALTA:
        return Nivel.ALTA
    if puntaje >= UMBRAL_MEDIA:
        return Nivel.MEDIA
    return Nivel.BAJA


def evaluar_equipo(equipo: Equipo, hoy: date, max_alquileres_30d: int) -> Resultado:
    categoria = equipo.categoria
    cerrados = [m for m in equipo.mantenimientos if m.fecha_fin is not None]
    ultimo = max(cerrados, key=lambda m: (m.fecha_fin, m.id), default=None)
    base_usos = ultimo.usos_al_momento if ultimo else 0
    base_fecha = ultimo.fecha_fin if ultimo else equipo.fecha_adquisicion

    usos = max(0, equipo.usos_acumulados - base_usos)
    dias = max(0, (hoy - base_fecha).days)
    recientes = _alquileres_30d(equipo, hoy)
    fallas = sum(1 for m in equipo.mantenimientos
                 if m.tipo is TipoMantenimiento.CORRECTIVO
                 and hoy - timedelta(days=365) <= m.fecha_inicio <= hoy)

    brutos = {
        "usos_desde_servicio": usos,
        "dias_desde_servicio": dias,
        "intensidad_reciente": recientes,
        "fallas_12m": fallas,
    }
    normalizados = {
        "usos_desde_servicio": min(1.0, usos / categoria.intervalo_mant_usos),
        "dias_desde_servicio": min(1.0, dias / categoria.intervalo_mant_dias),
        "intensidad_reciente": min(1.0, recientes / max_alquileres_30d) if max_alquileres_30d else 0.0,
        "fallas_12m": min(1.0, fallas / FALLAS_REFERENCIA),
    }
    aportes = {k: round(PESOS[k] * v, 2) for k, v in normalizados.items()}
    puntaje = round(sum(aportes.values()), 2)
    prioridad = _prioridad(puntaje)

    total_alquileres = sum(1 for a in equipo.alquileres if a.estado is not EstadoAlquiler.CANCELADO)
    if total_alquileres < 3:
        confianza = Nivel.BAJA
    elif total_alquileres < 10:
        confianza = Nivel.MEDIA
    else:
        confianza = Nivel.ALTA

    origen = (f"último servicio cerrado el {ultimo.fecha_fin.isoformat()}" if ultimo
              else f"sin servicios registrados; se cuenta desde la adquisición "
                   f"({equipo.fecha_adquisicion.isoformat()})")
    justificacion = [
        f"Referencia: {origen}.",
        f"Usos desde el último servicio: {usos}/{categoria.intervalo_mant_usos} "
        f"→ {aportes['usos_desde_servicio']:.1f} de {PESOS['usos_desde_servicio']:.0f} pts.",
        f"Días desde el último servicio: {dias}/{categoria.intervalo_mant_dias} "
        f"→ {aportes['dias_desde_servicio']:.1f} de {PESOS['dias_desde_servicio']:.0f} pts.",
        f"Alquileres en los últimos 30 días: {recientes} (máximo de la categoría: "
        f"{max_alquileres_30d}) → {aportes['intensidad_reciente']:.1f} de "
        f"{PESOS['intensidad_reciente']:.0f} pts.",
        f"Fallas (correctivos) en 12 meses: {fallas}/{FALLAS_REFERENCIA} "
        f"→ {aportes['fallas_12m']:.1f} de {PESOS['fallas_12m']:.0f} pts.",
        f"Puntaje total {puntaje:.1f}/100 → prioridad {prioridad.value} "
        f"(alta ≥ {UMBRAL_ALTA:.0f}, media ≥ {UMBRAL_MEDIA:.0f}).",
        f"Confianza {confianza.value}: {total_alquileres} alquileres registrados para este equipo.",
    ]
    return Resultado(
        resumen=f"{equipo.codigo} ({equipo.nombre}): puntaje de revisión ≈{puntaje:.0f}/100, "
                f"prioridad {prioridad.value}.",
        valor=puntaje,
        confianza=confianza,
        indicadores={
            "equipo_id": equipo.id,
            "codigo": equipo.codigo,
            "prioridad": prioridad.value,
            "alquileres_totales": total_alquileres,
            **brutos,
            "normalizados": {k: round(v, 3) for k, v in normalizados.items()},
            "aporte_puntos": aportes,
        },
        justificacion=justificacion,
        advertencia=ADVERTENCIA,
    )


def _persistir(session: Session, equipo_id: int, r: Resultado) -> None:
    rec = session.scalar(select(RecomendacionIA).where(
        RecomendacionIA.tipo == TipoRecomendacion.MANTENIMIENTO,
        RecomendacionIA.equipo_id == equipo_id,
        RecomendacionIA.estado == EstadoRecomendacion.PENDIENTE,
    ))
    if rec is None:
        rec = RecomendacionIA(tipo=TipoRecomendacion.MANTENIMIENTO, equipo_id=equipo_id)
        session.add(rec)
    rec.puntaje = r.valor
    rec.prioridad = Nivel(r.indicadores["prioridad"])
    rec.confianza = r.confianza
    rec.resumen = r.resumen
    rec.justificacion = list(r.justificacion)
    rec.datos_respaldo = {k: v for k, v in r.indicadores.items() if k != "equipo_id"}


def recomendar_mantenimiento(
    session: Session, actor: Usuario, hoy: date | None = None, persistir: bool = True
) -> list[Resultado]:
    requerir_permiso(actor, Permiso.IA_VER)
    hoy = hoy or date.today()
    equipos = list(session.scalars(select(Equipo).where(Equipo.estado.in_(EVALUABLES))))
    max_por_categoria: dict[int, int] = {}
    for e in equipos:
        max_por_categoria[e.categoria_id] = max(max_por_categoria.get(e.categoria_id, 0),
                                                _alquileres_30d(e, hoy))
    alertas = []
    for e in equipos:
        r = evaluar_equipo(e, hoy, max_por_categoria[e.categoria_id])
        if r.valor >= UMBRAL_MEDIA:
            alertas.append(r)
            if persistir:
                _persistir(session, e.id, r)
    if persistir:
        session.commit()
    return sorted(alertas, key=lambda r: -r.valor)
