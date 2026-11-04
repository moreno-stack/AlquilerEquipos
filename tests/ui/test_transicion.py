"""Transición de inicio de sesión: línea de tiempo determinista con datos reales de la cuenta."""

from alquiler.ui import transicion as tr


def test_tramos_caben_en_la_duracion():
    assert all(0 <= a < b <= tr.DURACION for a, b in tr.TRAMOS.values())


def test_tramo_limites():
    inicio, fin = tr.TRAMOS["anillo"]
    assert tr.tramo("anillo", inicio - 1) == 0 and tr.tramo("anillo", fin + 1) == 1
    assert 0 < tr.tramo("anillo", (inicio + fin) / 2) < 1


def test_escena_inicial_y_final():
    assert tr.escena(0, "Ana").anillo == 0 and tr.escena(0, "Ana").saludo == ""
    final = tr.escena(tr.DURACION, "Ana")
    assert final.saludo == "Hola, Ana"  # sin suponer el género de nadie
    assert final.pasos == tr.PASOS and final.progreso == 1 and final.fundido == 1
