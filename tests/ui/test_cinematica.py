"""Cinemática de arranque: una línea de tiempo determinista que la vista solo pinta."""

import pytest

from alquiler.ui import cinematica as cine


def test_tramo_va_de_0_a_1_dentro_de_su_intervalo():
    inicio, fin = cine.TRAMOS["rejilla"]
    assert cine.tramo("rejilla", inicio - 50) == 0
    assert 0 < cine.tramo("rejilla", (inicio + fin) / 2) < 1
    assert cine.tramo("rejilla", fin + 50) == 1


def test_los_tramos_caben_en_la_duracion():
    assert all(0 <= a < b <= cine.DURACION for a, b in cine.TRAMOS.values())


def test_rejilla_y_red_se_encienden():
    assert cine.escena(0).rejilla == 0 and cine.escena(0).nodos == 0
    medio = cine.escena(1000)
    assert medio.rejilla == 1 and 0 < medio.nodos < cine.NODOS
    assert cine.escena(1700).nodos == cine.NODOS
