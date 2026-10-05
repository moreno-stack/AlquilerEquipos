"""Esquema inicial: las 9 entidades del sistema (spec §4.2).

Revision ID: 0001
Revises: 
Create Date: 2026-10-04 17:19:33.064763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('categoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=80), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('intervalo_mant_usos', sa.Integer(), nullable=False),
    sa.Column('intervalo_mant_dias', sa.Integer(), nullable=False),
    sa.CheckConstraint('intervalo_mant_dias > 0', name=op.f('ck_categoria_intervalo_dias_positivo')),
    sa.CheckConstraint('intervalo_mant_usos > 0', name=op.f('ck_categoria_intervalo_usos_positivo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categoria')),
    sa.UniqueConstraint('nombre', name=op.f('uq_categoria_nombre'))
    )
    op.create_table('cliente',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('documento', sa.String(length=20), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('telefono', sa.String(length=30), nullable=False),
    sa.Column('direccion', sa.String(length=200), nullable=True),
    sa.Column('fecha_registro', sa.Date(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cliente')),
    sa.UniqueConstraint('documento', name=op.f('uq_cliente_documento'))
    )
    op.create_table('equipo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=30), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.Enum('Disponible', 'Alquilado', 'En mantenimiento', 'Reservado', 'Fuera de servicio', name='estadoequipo', native_enum=False), nullable=False),
    sa.Column('tarifa_diaria', sa.Integer(), nullable=False),
    sa.Column('usos_acumulados', sa.Integer(), nullable=False),
    sa.Column('horas_uso_acumuladas', sa.Double(), nullable=False),
    sa.Column('fecha_adquisicion', sa.Date(), nullable=False),
    sa.CheckConstraint('horas_uso_acumuladas >= 0', name=op.f('ck_equipo_horas_no_negativas')),
    sa.CheckConstraint('tarifa_diaria > 0', name=op.f('ck_equipo_tarifa_positiva')),
    sa.CheckConstraint('usos_acumulados >= 0', name=op.f('ck_equipo_usos_no_negativos')),
    sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], name=op.f('fk_equipo_categoria_id_categoria')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_equipo')),
    sa.UniqueConstraint('codigo', name=op.f('uq_equipo_codigo'))
    )
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('nombre_completo', sa.String(length=120), nullable=False),
    sa.Column('rol', sa.Enum('administrador', 'empleado', 'cliente', name='rol', native_enum=False), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('cliente_id', sa.Integer(), nullable=True),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], name=op.f('fk_usuario_cliente_id_cliente')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario')),
    sa.UniqueConstraint('cliente_id', name=op.f('uq_usuario_cliente_id')),
    sa.UniqueConstraint('username', name=op.f('uq_usuario_username'))
    )
    op.create_table('alquiler',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cliente_id', sa.Integer(), nullable=False),
    sa.Column('equipo_id', sa.Integer(), nullable=False),
    sa.Column('registrado_por_id', sa.Integer(), nullable=True),
    sa.Column('fecha_inicio', sa.Date(), nullable=False),
    sa.Column('fecha_fin_prevista', sa.Date(), nullable=False),
    sa.Column('tarifa_diaria', sa.Integer(), nullable=False),
    sa.Column('costo_estimado', sa.Integer(), nullable=False),
    sa.Column('estado', sa.Enum('reservado', 'activo', 'finalizado', 'cancelado', name='estadoalquiler', native_enum=False), nullable=False),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.CheckConstraint('costo_estimado >= 0', name=op.f('ck_alquiler_costo_no_negativo')),
    sa.CheckConstraint('fecha_fin_prevista >= fecha_inicio', name=op.f('ck_alquiler_fechas_ordenadas')),
    sa.CheckConstraint('tarifa_diaria > 0', name=op.f('ck_alquiler_tarifa_positiva')),
    sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], name=op.f('fk_alquiler_cliente_id_cliente')),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipo.id'], name=op.f('fk_alquiler_equipo_id_equipo')),
    sa.ForeignKeyConstraint(['registrado_por_id'], ['usuario.id'], name=op.f('fk_alquiler_registrado_por_id_usuario')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alquiler'))
    )
    op.create_table('mantenimiento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('equipo_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('preventivo', 'correctivo', name='tipomantenimiento', native_enum=False), nullable=False),
    sa.Column('fecha_inicio', sa.Date(), nullable=False),
    sa.Column('fecha_fin', sa.Date(), nullable=True),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('costo', sa.Integer(), nullable=False),
    sa.Column('usos_al_momento', sa.Integer(), nullable=False),
    sa.CheckConstraint('costo >= 0', name=op.f('ck_mantenimiento_costo_no_negativo')),
    sa.CheckConstraint('fecha_fin IS NULL OR fecha_fin >= fecha_inicio', name=op.f('ck_mantenimiento_fechas_ordenadas')),
    sa.CheckConstraint('usos_al_momento >= 0', name=op.f('ck_mantenimiento_usos_no_negativos')),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipo.id'], name=op.f('fk_mantenimiento_equipo_id_equipo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mantenimiento'))
    )
    op.create_table('recomendacion_ia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('mantenimiento', 'demanda', 'retraso', name='tiporecomendacion', native_enum=False), nullable=False),
    sa.Column('equipo_id', sa.Integer(), nullable=True),
    sa.Column('cliente_id', sa.Integer(), nullable=True),
    sa.Column('categoria_id', sa.Integer(), nullable=True),
    sa.Column('puntaje', sa.Double(), nullable=False),
    sa.Column('prioridad', sa.Enum('baja', 'media', 'alta', name='nivel', native_enum=False), nullable=False),
    sa.Column('confianza', sa.Enum('baja', 'media', 'alta', name='nivel', native_enum=False), nullable=False),
    sa.Column('resumen', sa.String(length=300), nullable=False),
    sa.Column('justificacion', sa.JSON(), nullable=False),
    sa.Column('datos_respaldo', sa.JSON(), nullable=False),
    sa.Column('estado', sa.Enum('pendiente', 'atendida', 'descartada', name='estadorecomendacion', native_enum=False), nullable=False),
    sa.Column('creada_en', sa.DateTime(), nullable=False),
    sa.CheckConstraint('puntaje >= 0 AND puntaje <= 100', name=op.f('ck_recomendacion_ia_puntaje_en_rango')),
    sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], name=op.f('fk_recomendacion_ia_categoria_id_categoria')),
    sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], name=op.f('fk_recomendacion_ia_cliente_id_cliente')),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipo.id'], name=op.f('fk_recomendacion_ia_equipo_id_equipo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recomendacion_ia'))
    )
    op.create_table('devolucion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alquiler_id', sa.Integer(), nullable=False),
    sa.Column('fecha_devolucion', sa.Date(), nullable=False),
    sa.Column('dias_retraso', sa.Integer(), nullable=False),
    sa.Column('recargo_mora', sa.Integer(), nullable=False),
    sa.Column('horas_uso', sa.Double(), nullable=False),
    sa.Column('con_danos', sa.Boolean(), nullable=False),
    sa.Column('descripcion_danos', sa.Text(), nullable=True),
    sa.Column('penalizacion_danos', sa.Integer(), nullable=False),
    sa.Column('total', sa.Integer(), nullable=False),
    sa.Column('registrado_por_id', sa.Integer(), nullable=True),
    sa.CheckConstraint('dias_retraso >= 0', name=op.f('ck_devolucion_retraso_no_negativo')),
    sa.CheckConstraint('horas_uso >= 0', name=op.f('ck_devolucion_horas_no_negativas')),
    sa.CheckConstraint('penalizacion_danos >= 0', name=op.f('ck_devolucion_penalizacion_no_negativa')),
    sa.CheckConstraint('recargo_mora >= 0', name=op.f('ck_devolucion_mora_no_negativa')),
    sa.CheckConstraint('total >= 0', name=op.f('ck_devolucion_total_no_negativo')),
    sa.ForeignKeyConstraint(['alquiler_id'], ['alquiler.id'], name=op.f('fk_devolucion_alquiler_id_alquiler')),
    sa.ForeignKeyConstraint(['registrado_por_id'], ['usuario.id'], name=op.f('fk_devolucion_registrado_por_id_usuario')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_devolucion')),
    sa.UniqueConstraint('alquiler_id', name=op.f('uq_devolucion_alquiler_id'))
    )
    op.create_table('pago',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alquiler_id', sa.Integer(), nullable=False),
    sa.Column('monto', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('metodo', sa.Enum('efectivo', 'tarjeta', 'transferencia', name='metodopago', native_enum=False), nullable=False),
    sa.Column('concepto', sa.Enum('alquiler', 'mora', 'danos', name='conceptopago', native_enum=False), nullable=False),
    sa.CheckConstraint('monto > 0', name=op.f('ck_pago_monto_positivo')),
    sa.ForeignKeyConstraint(['alquiler_id'], ['alquiler.id'], name=op.f('fk_pago_alquiler_id_alquiler')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pago'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('pago')
    op.drop_table('devolucion')
    op.drop_table('recomendacion_ia')
    op.drop_table('mantenimiento')
    op.drop_table('alquiler')
    op.drop_table('usuario')
    op.drop_table('equipo')
    op.drop_table('cliente')
    op.drop_table('categoria')
