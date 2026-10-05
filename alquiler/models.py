"""Modelos ORM de las 9 entidades (spec §4)."""

import enum
from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alquiler.db import Base


# ---------------------------------------------------------------- enumeraciones
class Rol(str, enum.Enum):
    ADMIN = "administrador"
    EMPLEADO = "empleado"
    CLIENTE = "cliente"


class EstadoEquipo(str, enum.Enum):
    DISPONIBLE = "Disponible"
    ALQUILADO = "Alquilado"
    EN_MANTENIMIENTO = "En mantenimiento"
    RESERVADO = "Reservado"
    FUERA_DE_SERVICIO = "Fuera de servicio"


class EstadoAlquiler(str, enum.Enum):
    RESERVADO = "reservado"
    ACTIVO = "activo"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class TipoMantenimiento(str, enum.Enum):
    PREVENTIVO = "preventivo"
    CORRECTIVO = "correctivo"


class ConceptoPago(str, enum.Enum):
    ALQUILER = "alquiler"
    MORA = "mora"
    DANOS = "danos"


class MetodoPago(str, enum.Enum):
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"


class TipoRecomendacion(str, enum.Enum):
    MANTENIMIENTO = "mantenimiento"
    DEMANDA = "demanda"
    RETRASO = "retraso"


class EstadoRecomendacion(str, enum.Enum):
    PENDIENTE = "pendiente"
    ATENDIDA = "atendida"
    DESCARTADA = "descartada"


class Nivel(str, enum.Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


def _enum(tipo: type[enum.Enum]) -> SAEnum:
    """Enum guardado como su valor legible ("En mantenimiento"), no como el nombre."""
    return SAEnum(
        tipo,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
        name=tipo.__name__.lower(),
    )


# ---------------------------------------------------------------- entidades
class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str] = mapped_column(String(30))
    direccion: Mapped[str | None] = mapped_column(String(200))
    fecha_registro: Mapped[date] = mapped_column(default=date.today)
    activo: Mapped[bool] = mapped_column(default=True)

    alquileres: Mapped[list["Alquiler"]] = relationship(back_populates="cliente")
    usuario: Mapped["Usuario | None"] = relationship(back_populates="cliente")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    nombre_completo: Mapped[str] = mapped_column(String(120))
    rol: Mapped[Rol] = mapped_column(_enum(Rol))
    activo: Mapped[bool] = mapped_column(default=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"), unique=True)
    creado_en: Mapped[datetime] = mapped_column(default=datetime.now)

    cliente: Mapped[Cliente | None] = relationship(back_populates="usuario")


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        CheckConstraint("intervalo_mant_usos > 0", name="intervalo_usos_positivo"),
        CheckConstraint("intervalo_mant_dias > 0", name="intervalo_dias_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    intervalo_mant_usos: Mapped[int] = mapped_column(default=20)
    intervalo_mant_dias: Mapped[int] = mapped_column(default=90)

    equipos: Mapped[list["Equipo"]] = relationship(back_populates="categoria")


class Equipo(Base):
    __tablename__ = "equipo"
    __table_args__ = (
        CheckConstraint("tarifa_diaria > 0", name="tarifa_positiva"),
        CheckConstraint("usos_acumulados >= 0", name="usos_no_negativos"),
        CheckConstraint("horas_uso_acumuladas >= 0", name="horas_no_negativas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    estado: Mapped[EstadoEquipo] = mapped_column(
        _enum(EstadoEquipo), default=EstadoEquipo.DISPONIBLE
    )
    tarifa_diaria: Mapped[int]
    usos_acumulados: Mapped[int] = mapped_column(default=0)
    horas_uso_acumuladas: Mapped[float] = mapped_column(default=0.0)
    fecha_adquisicion: Mapped[date]

    categoria: Mapped[Categoria] = relationship(back_populates="equipos")
    alquileres: Mapped[list["Alquiler"]] = relationship(back_populates="equipo")
    mantenimientos: Mapped[list["Mantenimiento"]] = relationship(back_populates="equipo")


class Alquiler(Base):
    __tablename__ = "alquiler"
    __table_args__ = (
        CheckConstraint("fecha_fin_prevista >= fecha_inicio", name="fechas_ordenadas"),
        CheckConstraint("tarifa_diaria > 0", name="tarifa_positiva"),
        CheckConstraint("costo_estimado >= 0", name="costo_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipo.id"))
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fecha_inicio: Mapped[date]
    fecha_fin_prevista: Mapped[date]
    tarifa_diaria: Mapped[int]
    costo_estimado: Mapped[int]
    estado: Mapped[EstadoAlquiler] = mapped_column(
        _enum(EstadoAlquiler), default=EstadoAlquiler.ACTIVO
    )
    creado_en: Mapped[datetime] = mapped_column(default=datetime.now)

    cliente: Mapped[Cliente] = relationship(back_populates="alquileres")
    equipo: Mapped[Equipo] = relationship(back_populates="alquileres")
    registrado_por: Mapped[Usuario | None] = relationship()
    devolucion: Mapped["Devolucion | None"] = relationship(back_populates="alquiler")
    pagos: Mapped[list["Pago"]] = relationship(back_populates="alquiler")


class Devolucion(Base):
    __tablename__ = "devolucion"
    __table_args__ = (
        CheckConstraint("dias_retraso >= 0", name="retraso_no_negativo"),
        CheckConstraint("recargo_mora >= 0", name="mora_no_negativa"),
        CheckConstraint("penalizacion_danos >= 0", name="penalizacion_no_negativa"),
        CheckConstraint("horas_uso >= 0", name="horas_no_negativas"),
        CheckConstraint("total >= 0", name="total_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alquiler_id: Mapped[int] = mapped_column(ForeignKey("alquiler.id"), unique=True)
    fecha_devolucion: Mapped[date]
    dias_retraso: Mapped[int]
    recargo_mora: Mapped[int]
    horas_uso: Mapped[float]
    con_danos: Mapped[bool] = mapped_column(default=False)
    descripcion_danos: Mapped[str | None] = mapped_column(Text)
    penalizacion_danos: Mapped[int] = mapped_column(default=0)
    total: Mapped[int]
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    alquiler: Mapped[Alquiler] = relationship(back_populates="devolucion")


class Pago(Base):
    __tablename__ = "pago"
    __table_args__ = (CheckConstraint("monto > 0", name="monto_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alquiler_id: Mapped[int] = mapped_column(ForeignKey("alquiler.id"))
    monto: Mapped[int]
    fecha: Mapped[date]
    metodo: Mapped[MetodoPago] = mapped_column(_enum(MetodoPago))
    concepto: Mapped[ConceptoPago] = mapped_column(_enum(ConceptoPago))

    alquiler: Mapped[Alquiler] = relationship(back_populates="pagos")


class Mantenimiento(Base):
    __tablename__ = "mantenimiento"
    __table_args__ = (
        CheckConstraint("costo >= 0", name="costo_no_negativo"),
        CheckConstraint("usos_al_momento >= 0", name="usos_no_negativos"),
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin >= fecha_inicio", name="fechas_ordenadas"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipo.id"))
    tipo: Mapped[TipoMantenimiento] = mapped_column(_enum(TipoMantenimiento))
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date | None]
    descripcion: Mapped[str] = mapped_column(Text)
    costo: Mapped[int] = mapped_column(default=0)
    usos_al_momento: Mapped[int] = mapped_column(default=0)

    equipo: Mapped[Equipo] = relationship(back_populates="mantenimientos")


class RecomendacionIA(Base):
    __tablename__ = "recomendacion_ia"
    __table_args__ = (
        CheckConstraint("puntaje >= 0 AND puntaje <= 100", name="puntaje_en_rango"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoRecomendacion] = mapped_column(_enum(TipoRecomendacion))
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("equipo.id"))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    puntaje: Mapped[float]
    prioridad: Mapped[Nivel] = mapped_column(_enum(Nivel))
    confianza: Mapped[Nivel] = mapped_column(_enum(Nivel))
    resumen: Mapped[str] = mapped_column(String(300))
    justificacion: Mapped[list] = mapped_column(JSON, default=list)
    datos_respaldo: Mapped[dict] = mapped_column(JSON, default=dict)
    estado: Mapped[EstadoRecomendacion] = mapped_column(
        _enum(EstadoRecomendacion), default=EstadoRecomendacion.PENDIENTE
    )
    creada_en: Mapped[datetime] = mapped_column(default=datetime.now)

    equipo: Mapped[Equipo | None] = relationship()
    cliente: Mapped[Cliente | None] = relationship()
    categoria: Mapped[Categoria | None] = relationship()
