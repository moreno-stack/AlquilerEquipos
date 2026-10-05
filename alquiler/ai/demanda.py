"""Predicción de demanda mensual por categoría (spec §6.1).

Método: índice estacional por mes del año × media desestacionalizada de los
últimos 3 meses completos. El rango sale del error histórico del mismo método.
"""

from collections import Counter
from datetime import date, timedelta
from statistics import mean, pstdev

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alquiler.ai.resultado import MESES, Resultado
from alquiler.auth import Permiso, requerir_permiso
from alquiler.models import Alquiler, Categoria, Equipo, EstadoAlquiler, Nivel, Usuario

UMBRAL_PICO = 1.25
Z_80 = 1.28
ADVERTENCIA = (
    "Estimación estadística basada solo en el historial registrado; no es una certeza. "
    "Eventos no registrados (obras, clima, temporadas atípicas) pueden cambiar la demanda."
)


def _sumar_mes(mes: date, n: int = 1) -> date:
    total = mes.year * 12 + (mes.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def serie_mensual(session: Session, categoria_id: int, hasta_mes: date) -> list[tuple[date, int]]:
    """Alquileres no cancelados por mes, desde el primer mes con datos del sistema."""
    no_cancelado = Alquiler.estado != EstadoAlquiler.CANCELADO
    primero = session.scalar(select(func.min(Alquiler.fecha_inicio)).where(no_cancelado))
    if primero is None:
        return []
    inicio = primero.replace(day=1)
    if inicio > hasta_mes:
        return []
    fechas = session.scalars(
        select(Alquiler.fecha_inicio)
        .join(Equipo)
        .where(no_cancelado, Equipo.categoria_id == categoria_id,
               Alquiler.fecha_inicio < _sumar_mes(hasta_mes))
    )
    conteo = Counter(f.replace(day=1) for f in fechas)
    serie, mes = [], inicio
    while mes <= hasta_mes:
        serie.append((mes, conteo.get(mes, 0)))
        mes = _sumar_mes(mes)
    return serie


def _indices(serie: list[tuple[date, int]]) -> list[float]:
    conteos = [c for _, c in serie]
    media = mean(conteos)
    if len(serie) < 12 or media == 0:
        return [1.0] * 12
    indices = []
    for m in range(1, 13):
        del_mes = [c for f, c in serie if f.month == m]
        indices.append(mean(del_mes) / media if del_mes else 1.0)
    return indices


def _pronostico(previos: list[tuple[date, int]], mes_objetivo: int, indices: list[float]) -> float:
    base = mean(c / max(indices[f.month - 1], 0.1) for f, c in previos)
    return base * indices[mes_objetivo - 1]


def _sin_historial(nombre: str) -> Resultado:
    return Resultado(
        resumen=f"{nombre}: sin historial de alquileres para estimar la demanda.",
        valor=None,
        confianza=Nivel.BAJA,
        indicadores={"categoria": nombre, "meses_historial": 0},
        justificacion=["No hay alquileres registrados en esta categoría."],
        advertencia=ADVERTENCIA,
    )


def _estimar(nombre: str, serie: list[tuple[date, int]], objetivo: date) -> Resultado:
    conteos = [c for _, c in serie]
    n, media = len(serie), mean(conteos)
    indices = _indices(serie)
    ultimos = serie[-3:]
    base = mean(c / max(indices[f.month - 1], 0.1) for f, c in ultimos)
    pronostico = base * indices[objetivo.month - 1]

    residuos = [c - _pronostico(serie[t - 3:t], f.month, indices)
                for t, (f, c) in enumerate(serie) if t >= 3]
    if len(residuos) >= 2:
        sigma = pstdev(residuos)
        margen = Z_80 * sigma
        cv = sigma / media if media else None
    else:
        sigma, margen, cv = None, 0.5 * pronostico, None
    # Piso de Poisson: un conteo de eventos tiene al menos ~√λ de variación propia,
    # así que el rango nunca se reduce a un punto aunque el error histórico sea 0.
    margen_poisson = Z_80 * pronostico ** 0.5
    piso_aplicado = margen < margen_poisson
    margen = max(margen, margen_poisson)
    rango = [round(max(0.0, pronostico - margen), 1), round(pronostico + margen, 1)]
    picos = [MESES[i] for i, valor in enumerate(indices) if valor >= UMBRAL_PICO]

    if n < 6:
        confianza, motivo = Nivel.BAJA, f"solo {n} meses de historial (< 6)"
    elif n < 12:
        confianza, motivo = Nivel.MEDIA, f"{n} meses de historial: sin un año completo"
    elif cv is not None and cv > 0.5:
        confianza, motivo = Nivel.MEDIA, f"la serie es muy variable (CV de errores {cv:.2f} > 0,5)"
    else:
        confianza, motivo = Nivel.ALTA, f"{n} meses de historial y errores estables"

    mes_nombre = MESES[objetivo.month - 1]
    i_obj = indices[objetivo.month - 1]
    justificacion = [
        f"Historial: {n} meses ({serie[0][0]:%Y-%m} a {serie[-1][0]:%Y-%m}), "
        f"{sum(conteos)} alquileres; media mensual {media:.1f}.",
        (f"Índice estacional de {mes_nombre}: {i_obj:.2f} (1,00 = mes promedio)."
         if n >= 12 else
         "Con menos de 12 meses no se estima estacionalidad (índice 1,00 para todos los meses)."),
        "Base: media desestacionalizada de los últimos 3 meses ("
        + ", ".join(f"{f:%Y-%m}: {c}" for f, c in ultimos) + f") = {base:.1f}.",
        f"Pronóstico = base × índice de {mes_nombre} = {pronostico:.1f}.",
        (f"Rango ≈80 %: ±{margen:.1f}, según la dispersión de {len(residuos)} errores "
         "históricos del mismo método."
         if sigma is not None else
         "Pocos datos para medir el error del método: se usa un margen de ±50 %."),
    ]
    if piso_aplicado:
        justificacion.append(
            f"El error histórico es menor que la variación natural de un conteo; "
            f"se usa como mínimo ±{margen:.1f} (≈1,28·√pronóstico)."
        )
    if picos:
        justificacion.append(f"Meses pico (índice ≥ {UMBRAL_PICO:.2f}): {', '.join(picos)}.")
    justificacion.append(f"Confianza {confianza.value}: {motivo}.")

    return Resultado(
        resumen=(f"{nombre}: se estiman ≈{pronostico:.0f} alquileres en {mes_nombre} "
                 f"{objetivo.year} (rango {rango[0]:.0f}–{rango[1]:.0f})."),
        valor=round(pronostico, 2),
        confianza=confianza,
        indicadores={
            "categoria": nombre,
            "mes_objetivo": f"{objetivo:%Y-%m}",
            "meses_historial": n,
            "pronostico": round(pronostico, 2),
            "rango": rango,
            "indice_estacional": [round(i, 3) for i in indices],
            "picos": picos,
            "ultimos_3_meses": {f"{f:%Y-%m}": c for f, c in ultimos},
        },
        justificacion=justificacion,
        advertencia=ADVERTENCIA,
    )


def predecir_demanda(session: Session, actor: Usuario, hoy: date | None = None) -> list[Resultado]:
    requerir_permiso(actor, Permiso.IA_VER)
    hoy = hoy or date.today()
    mes_actual = hoy.replace(day=1)
    ultimo_completo = (mes_actual - timedelta(days=1)).replace(day=1)
    objetivo = _sumar_mes(mes_actual)
    resultados = []
    for categoria in session.scalars(select(Categoria).order_by(Categoria.nombre)):
        serie = serie_mensual(session, categoria.id, ultimo_completo)
        if not serie or not any(c for _, c in serie):
            resultados.append(_sin_historial(categoria.nombre))
        else:
            resultados.append(_estimar(categoria.nombre, serie, objetivo))
    return resultados
