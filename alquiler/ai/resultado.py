"""Contrato común de los analizadores de IA (spec §6)."""

from dataclasses import dataclass

from alquiler.models import Nivel

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


@dataclass(frozen=True)
class Resultado:
    """Una estimación con todo lo necesario para entenderla y cuestionarla."""

    resumen: str            # frase corta, redactada como estimación
    valor: float | None     # número principal (puntaje, demanda esperada, tasa)
    confianza: Nivel        # según cantidad y dispersión de los datos
    indicadores: dict       # cifras de respaldo
    justificacion: list[str]  # pasos legibles del razonamiento
    advertencia: str        # límites de la estimación
