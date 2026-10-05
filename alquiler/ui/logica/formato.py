"""Formato de valores para mostrar en la interfaz."""

from datetime import date

from alquiler.services import pesos as _pesos


def pesos(monto: int) -> str:
    return _pesos(monto)


def fecha(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else ""


def nivel(valor: str) -> str:
    return valor.capitalize()
