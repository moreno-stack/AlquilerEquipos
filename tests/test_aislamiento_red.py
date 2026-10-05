"""Ninguna prueba puede llamar a la red (p. ej. a la API de Groq) sin querer."""

import socket

import pytest


def test_la_red_esta_bloqueada_en_las_pruebas():
    with pytest.raises(RuntimeError, match="sin red"):
        socket.create_connection(("example.com", 443), timeout=1)
    with socket.socket() as s, pytest.raises(RuntimeError, match="sin red"):
        s.connect(("93.184.216.34", 80))
