"""Lógica de presentación: clientes, usuarios del sistema y perfil propio."""

from alquiler.models import Rol
from alquiler.services import alquileres as svc_alquileres
from alquiler.services import clientes as svc_clientes
from alquiler.services import usuarios as svc_usuarios
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import fecha, pesos

ROLES: list[tuple[str, str]] = [(r.value, r.value.capitalize()) for r in Rol]


def _fila_cliente(c) -> dict:
    return {"id": c.id, "documento": c.documento, "nombre": c.nombre, "telefono": c.telefono,
            "email": c.email or "", "direccion": c.direccion or "",
            "estado": "Activo" if c.activo else "Inactivo"}


def clientes(ctx: Contexto, texto: str | None = None, incluir_inactivos: bool = False) -> list[dict]:
    return ctx.ejecutar(lambda s, a: [
        _fila_cliente(c) for c in svc_clientes.buscar_clientes(s, a, texto, incluir_inactivos)])


def clientes_habilitados(ctx: Contexto) -> list[dict]:
    """Clientes a los que se les puede registrar un alquiler (solo activos)."""
    return [{"id": c["id"], "etiqueta": f"{c['nombre']} — {c['documento']}"} for c in clientes(ctx)]


def registrar_cliente(ctx: Contexto, documento: str, nombre: str, telefono: str,
                      email: str | None = None, direccion: str | None = None) -> int:
    return ctx.ejecutar(lambda s, a: svc_clientes.registrar_cliente(
        s, a, documento, nombre, telefono, email, direccion).id)


def actualizar_cliente(ctx: Contexto, cliente_id: int, **campos) -> None:
    ctx.ejecutar(lambda s, a: svc_clientes.actualizar_cliente(s, a, cliente_id, **campos))


def desactivar_cliente(ctx: Contexto, cliente_id: int) -> None:
    ctx.ejecutar(lambda s, a: svc_clientes.desactivar_cliente(s, a, cliente_id))


def historial_cliente(ctx: Contexto, cliente_id: int) -> list[dict]:
    def filas(s, a):
        resultado = []
        for alq in svc_clientes.historial_cliente(s, a, cliente_id):
            saldo = svc_alquileres.saldo_pendiente(alq)
            resultado.append({
                "id": alq.id, "equipo": f"{alq.equipo.codigo} · {alq.equipo.nombre}",
                "inicio": fecha(alq.fecha_inicio), "inicio__orden": alq.fecha_inicio.isoformat(),
                "fin": fecha(alq.fecha_fin_prevista), "estado": alq.estado.value,
                "total": pesos(svc_alquileres.total_adeudado(alq)),
                "saldo": pesos(saldo), "saldo__orden": saldo,
            })
        return resultado
    return ctx.ejecutar(filas)


# ---------------------------------------------------------------- usuarios
def usuarios(ctx: Contexto) -> list[dict]:
    return ctx.ejecutar(lambda s, a: [{
        "id": u.id, "username": u.username, "nombre": u.nombre_completo,
        "rol": u.rol.value.capitalize(), "estado": "Activo" if u.activo else "Inactivo",
        "activo": u.activo,
    } for u in svc_usuarios.listar_usuarios(s, a)])


def crear_usuario(ctx: Contexto, username: str, password: str, rol: str, nombre: str,
                  cliente_id: int | None = None) -> int:
    return ctx.ejecutar(lambda s, a: svc_usuarios.crear_usuario(
        s, a, username, password, Rol(rol), nombre, cliente_id).id)


def cambiar_estado_usuario(ctx: Contexto, usuario_id: int, activo: bool) -> None:
    ctx.ejecutar(lambda s, a: svc_usuarios.cambiar_estado_usuario(s, a, usuario_id, activo))


def restablecer_password(ctx: Contexto, usuario_id: int, nueva: str) -> None:
    ctx.ejecutar(lambda s, a: svc_usuarios.restablecer_password(s, a, usuario_id, nueva))


# ---------------------------------------------------------------- perfil propio
def cambiar_password(ctx: Contexto, actual: str, nueva: str) -> None:
    ctx.ejecutar(lambda s, a: svc_usuarios.cambiar_password(s, a, actual, nueva))


def mi_cliente(ctx: Contexto) -> dict | None:
    if ctx.usuario.cliente_id is None:
        return None
    return ctx.ejecutar(lambda s, a: _fila_cliente(
        svc_clientes.obtener_cliente(s, a, ctx.usuario.cliente_id)))


def actualizar_mi_contacto(ctx: Contexto, telefono: str, email: str, direccion: str) -> None:
    actualizar_cliente(ctx, ctx.usuario.cliente_id, telefono=telefono, email=email,
                       direccion=direccion)
