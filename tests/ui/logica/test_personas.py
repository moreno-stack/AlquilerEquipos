"""Lógica de presentación de clientes, usuarios y perfil."""

from datetime import date

import pytest

from alquiler.errors import CredencialesInvalidas
from alquiler.models import Alquiler, Cliente, EstadoAlquiler, MetodoPago, Pago, ConceptoPago, Equipo
from alquiler.ui.logica import personas


def test_clientes_y_habilitados_excluye_inactivos(ctx_factory, datos_base):
    ctx = ctx_factory("empleado")
    nuevo = personas.registrar_cliente(ctx, "777", "Luis Gómez", "3100000000", "luis@correo.co")
    personas.desactivar_cliente(ctx, nuevo)
    assert [c["nombre"] for c in personas.clientes(ctx)] == ["Ana Pérez"]
    todos = personas.clientes(ctx, incluir_inactivos=True)
    assert [(c["nombre"], c["estado"]) for c in todos] == [("Ana Pérez", "Activo"),
                                                          ("Luis Gómez", "Inactivo")]
    assert personas.clientes_habilitados(ctx) == [
        {"id": todos[0]["id"], "etiqueta": "Ana Pérez — 1085000001"}]


def test_historial_incluye_saldo(ctx_factory, datos_base, fabrica):
    with fabrica() as s:
        cliente = s.query(Cliente).one()
        equipo = s.query(Equipo).filter_by(codigo="TAL-001").one()
        a = Alquiler(cliente=cliente, equipo=equipo, fecha_inicio=date(2026, 3, 1),
                     fecha_fin_prevista=date(2026, 3, 4), tarifa_diaria=25_000,
                     costo_estimado=75_000, estado=EstadoAlquiler.ACTIVO)
        s.add_all([a, Pago(alquiler=a, monto=50_000, fecha=date(2026, 3, 1),
                           metodo=MetodoPago.EFECTIVO, concepto=ConceptoPago.ALQUILER)])
        s.commit()
        cliente_id = cliente.id
    [fila] = personas.historial_cliente(ctx_factory("empleado"), cliente_id)
    assert (fila["equipo"], fila["estado"], fila["total"], fila["saldo"], fila["saldo__orden"]) == (
        "TAL-001 · Taladro percutor", "activo", "$75.000", "$25.000", 25_000)


def test_usuarios_crear_y_listar(ctx_factory, datos_base):
    ctx = ctx_factory("admin")
    cliente_id = personas.clientes(ctx)[0]["id"]
    personas.crear_usuario(ctx, "ana", "clave-segura", "cliente", "Ana Pérez", cliente_id)
    filas = {u["username"]: u for u in personas.usuarios(ctx)}
    assert (filas["ana"]["rol"], filas["ana"]["estado"]) == ("Cliente", "Activo")
    assert [r for r, _ in personas.ROLES] == ["administrador", "empleado", "cliente"]


def test_cambiar_password_con_actual_incorrecta(ctx_factory, fabrica, config):
    from alquiler.auth import crear_usuario
    from alquiler.models import Rol
    from alquiler.ui.logica.contexto import iniciar_sesion
    with fabrica() as s:
        crear_usuario(s, "luis", "clave-segura", Rol.EMPLEADO, "Luis")
    ctx = iniciar_sesion(fabrica, config, "luis", "clave-segura")
    with pytest.raises(CredencialesInvalidas):
        personas.cambiar_password(ctx, "otra", "nueva-clave-1")
    personas.cambiar_password(ctx, "clave-segura", "nueva-clave-1")
    assert iniciar_sesion(fabrica, config, "luis", "nueva-clave-1").usuario.username == "luis"


def test_mi_cliente_y_contacto(ctx_factory, datos_base):
    ctx = ctx_factory("cliente")
    assert personas.mi_cliente(ctx)["nombre"] == "Ana Pérez"
    personas.actualizar_mi_contacto(ctx, telefono="3119998877", email="ana@correo.co", direccion="")
    assert personas.mi_cliente(ctx)["telefono"] == "3119998877"
    assert personas.mi_cliente(ctx_factory("empleado")) is None
