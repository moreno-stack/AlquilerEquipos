"""Restricciones del esquema: protegen la integridad aunque un servicio falle."""

from datetime import date

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alquiler.models import (
    Alquiler,
    Categoria,
    Cliente,
    ConceptoPago,
    Devolucion,
    Equipo,
    EstadoEquipo,
    MetodoPago,
    Nivel,
    Pago,
    RecomendacionIA,
    Rol,
    TipoRecomendacion,
    Usuario,
)

TABLAS = {
    "usuario", "cliente", "categoria", "equipo", "alquiler",
    "devolucion", "pago", "mantenimiento", "recomendacion_ia",
}


def _equipo(session, codigo="TAL-001", **kw):
    categoria = session.query(Categoria).filter_by(nombre="Taladros").one_or_none()
    if categoria is None:
        categoria = Categoria(nombre="Taladros")
        session.add(categoria)
    datos = dict(codigo=codigo, nombre="Taladro percutor", categoria=categoria,
                 tarifa_diaria=25_000, fecha_adquisicion=date(2025, 1, 10))
    datos.update(kw)
    equipo = Equipo(**datos)
    session.add(equipo)
    session.flush()
    return equipo


def _cliente(session, documento="1085000001"):
    cliente = Cliente(documento=documento, nombre="Ana Pérez", telefono="3001234567")
    session.add(cliente)
    session.flush()
    return cliente


def _alquiler(session, **kw):
    datos = dict(cliente=_cliente(session), equipo=_equipo(session),
                 fecha_inicio=date(2026, 3, 1), fecha_fin_prevista=date(2026, 3, 4),
                 tarifa_diaria=25_000, costo_estimado=75_000)
    datos.update(kw)
    alquiler = Alquiler(**datos)
    session.add(alquiler)
    session.flush()
    return alquiler


def test_se_crean_las_9_tablas(engine):
    assert TABLAS <= set(inspect(engine).get_table_names())


def test_equipo_nace_disponible_con_contadores_en_cero(session):
    equipo = _equipo(session)
    assert equipo.estado is EstadoEquipo.DISPONIBLE
    assert equipo.usos_acumulados == 0
    assert equipo.horas_uso_acumuladas == 0


def test_categoria_tiene_intervalos_de_mantenimiento_por_defecto(session):
    equipo = _equipo(session)
    assert (equipo.categoria.intervalo_mant_usos, equipo.categoria.intervalo_mant_dias) == (20, 90)


def test_estado_se_guarda_como_texto_legible(session):
    _equipo(session, estado=EstadoEquipo.EN_MANTENIMIENTO)
    assert session.execute(text("SELECT estado FROM equipo")).scalar() == "En mantenimiento"


def test_codigo_equipo_unico(session):
    _equipo(session, codigo="X-1")
    with pytest.raises(IntegrityError):
        _equipo(session, codigo="X-1")


def test_documento_cliente_unico(session):
    _cliente(session, "123")
    with pytest.raises(IntegrityError):
        _cliente(session, "123")


def test_username_unico(session):
    session.add(Usuario(username="ana", password_hash="h", nombre_completo="A", rol=Rol.EMPLEADO))
    session.flush()
    session.add(Usuario(username="ana", password_hash="h", nombre_completo="B", rol=Rol.EMPLEADO))
    with pytest.raises(IntegrityError):
        session.flush()


def test_tarifa_debe_ser_positiva(session):
    with pytest.raises(IntegrityError):
        _equipo(session, tarifa_diaria=0)


def test_contadores_de_uso_no_negativos(session):
    with pytest.raises(IntegrityError):
        _equipo(session, usos_acumulados=-1)


def test_fk_categoria_inexistente_falla(session):
    session.add(Equipo(codigo="Z", nombre="Z", categoria_id=999, tarifa_diaria=1,
                       fecha_adquisicion=date(2025, 1, 1)))
    with pytest.raises(IntegrityError):
        session.flush()


def test_fecha_fin_no_anterior_a_inicio(session):
    with pytest.raises(IntegrityError):
        _alquiler(session, fecha_inicio=date(2026, 3, 5), fecha_fin_prevista=date(2026, 3, 4))


def test_alquiler_de_un_dia_es_valido(session):
    alquiler = _alquiler(session, fecha_inicio=date(2026, 3, 5), fecha_fin_prevista=date(2026, 3, 5))
    assert alquiler.id is not None


def _devolucion(alquiler, **kw):
    datos = dict(alquiler=alquiler, fecha_devolucion=date(2026, 3, 4), dias_retraso=0,
                 recargo_mora=0, horas_uso=8.0, total=75_000)
    datos.update(kw)
    return Devolucion(**datos)


def test_un_alquiler_solo_tiene_una_devolucion(session):
    alquiler = _alquiler(session)
    session.add(_devolucion(alquiler))
    session.flush()
    session.add(Devolucion(alquiler_id=alquiler.id, fecha_devolucion=date(2026, 3, 5),
                           dias_retraso=1, recargo_mora=0, horas_uso=0, total=0))
    with pytest.raises(IntegrityError):
        session.flush()


def test_pago_monto_positivo(session):
    session.add(Pago(alquiler=_alquiler(session), monto=0, fecha=date(2026, 3, 1),
                     metodo=MetodoPago.EFECTIVO, concepto=ConceptoPago.ALQUILER))
    with pytest.raises(IntegrityError):
        session.flush()


def _recomendacion(**kw):
    datos = dict(tipo=TipoRecomendacion.MANTENIMIENTO, puntaje=80.0, prioridad=Nivel.ALTA,
                 confianza=Nivel.MEDIA, resumen="Revisar pronto",
                 justificacion=["Usos: +30 pts"], datos_respaldo={"usos": 25})
    datos.update(kw)
    return RecomendacionIA(**datos)


def test_puntaje_recomendacion_entre_0_y_100(session):
    session.add(_recomendacion(puntaje=101))
    with pytest.raises(IntegrityError):
        session.flush()


def test_recomendacion_guarda_justificacion_y_datos_json(session):
    rec = _recomendacion(equipo=_equipo(session),
                         justificacion=["Usos desde el último servicio: 25/20 → +35 pts"],
                         datos_respaldo={"usos": 25, "fallas_12m": [1, 2]})
    session.add(rec)
    session.commit()
    session.expire_all()
    leida = session.get(RecomendacionIA, rec.id)
    assert leida.justificacion == ["Usos desde el último servicio: 25/20 → +35 pts"]
    assert leida.datos_respaldo == {"usos": 25, "fallas_12m": [1, 2]}
    assert leida.estado.value == "pendiente"


def test_relaciones_navegables(session):
    alquiler = _alquiler(session)
    session.add(_devolucion(alquiler, total=90_000))
    session.add(Pago(alquiler=alquiler, monto=75_000, fecha=date(2026, 3, 1),
                     metodo=MetodoPago.TRANSFERENCIA, concepto=ConceptoPago.ALQUILER))
    session.commit()
    session.expire_all()
    cliente = session.get(Cliente, alquiler.cliente_id)
    assert cliente.alquileres[0].devolucion.total == 90_000
    assert cliente.alquileres[0].pagos[0].monto == 75_000
    assert cliente.alquileres[0].equipo.categoria.equipos[0].codigo == "TAL-001"


def test_usuario_cliente_enlazado(session):
    cliente = _cliente(session)
    session.add(Usuario(username="ana", password_hash="h", nombre_completo="Ana",
                        rol=Rol.CLIENTE, cliente=cliente))
    session.commit()
    assert cliente.usuario.username == "ana"
