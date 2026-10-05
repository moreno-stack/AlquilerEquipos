# Sistema Inteligente de Alquiler de Equipos — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la app de escritorio de alquiler de equipos con RBAC, lógica de negocio probada y un módulo de IA explicable.

**Architecture:** Monolito en capas `ui → services → models/db`, con `ai` como funciones puras que leen vía `Session`. SQLite + SQLAlchemy 2 + Alembic; autorización en la capa de servicios.

**Tech Stack:** Python ≥ 3.11, PySide6, SQLAlchemy 2.x, Alembic, bcrypt, anthropic, pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-04-alquiler-equipos-design.md`

**Execution method:** Native (elegido por el usuario: "Inicia inmediatamente la FASE 1").

## Global Constraints

- Python ≥ 3.11; paquete `alquiler`; código, mensajes y nombres de dominio en español.
- Montos en COP como `int` (pesos enteros), redondeo half-up.
- Fechas de alquiler como `date`.
- Enums guardados como texto con los valores exactos de spec §4.1.
- SQLite con `PRAGMA foreign_keys=ON` en cada conexión.
- Servicios: `def op(session: Session, actor: Usuario, ...)`; errores de negocio = `ReglaNegocioError` (mensaje en español).
- Contraseñas: bcrypt, mínimo 8 caracteres; jamás en texto plano ni en logs.
- La IA nunca presenta certezas: todo resultado es un `Resultado` con `confianza`, `indicadores`, `justificacion` y `advertencia`.
- Text-to-SQL: solo lectura, sin acceso a `usuario`, `LIMIT 200`, 3 s máximo.
- Pruebas con SQLite en memoria; `pytest` debe pasar completo al final de cada tarea.

## Review Focus

1. **Usuario escrito con mayúsculas o espacios** (`" Admin "`) → debe autenticar igual que `admin`; los usernames se normalizan con `strip().lower()` al crear y al autenticar. (Tarea 1.4)
2. **Claves foráneas silenciosamente desactivadas** en SQLite → insertar un `Equipo` con `categoria_id` inexistente debe fallar. (Tarea 1.1)
3. **Primer arranque en Windows sin la carpeta de datos** → `crear_engine` crea los directorios padre de `ALQUILER_DB_PATH`. (Tarea 1.1)
4. **`ALQUILER_FACTOR_MORA=1,5` (coma decimal, configuración regional es-CO)** → se acepta como 1.5; un valor no numérico o ≤ 0 lanza `ValueError` con un mensaje claro. (Tarea 1.1)
5. **Contraseña de más de 72 bytes UTF‑8** (límite de bcrypt; las tildes ocupan 2 bytes) → `ReglaNegocioError` claro en lugar de una excepción de la librería o un truncado silencioso. (Tarea 1.4)

---

## FASE 1 — Base: estructura, DB, modelos, migraciones, autenticación

### Task 1 (Tarea 1.1): Estructura, configuración y conexión a la DB

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md` (mínimo), `alquiler/__init__.py`, `alquiler/config.py`, `alquiler/db.py`, `alquiler/errors.py`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_config.py`, `tests/test_db.py`

**Interfaces:**
- Produces:
  - `config.Config` (dataclass frozen): `db_path: Path`, `admin_password: str`, `factor_mora: float`, `anthropic_api_key: str | None`, `anthropic_model: str | None`
  - `config.cargar_config(env: Mapping[str, str] | None = None) -> Config` (por defecto `os.environ`)
  - `db.Base` (DeclarativeBase)
  - `db.crear_engine(url_o_ruta: str | Path) -> Engine` — acepta una ruta de archivo o una URL `sqlite://`; activa `foreign_keys`; crea directorios padre
  - `db.crear_sessionmaker(engine) -> sessionmaker[Session]` (`expire_on_commit=False`)
  - `errors.ReglaNegocioError`, `errors.CredencialesInvalidas(ReglaNegocioError)`, `errors.PermisoDenegado(ReglaNegocioError)`
  - fixtures `engine`, `session` en `tests/conftest.py` (SQLite en memoria con `StaticPool` + `Base.metadata.create_all`)

- [ ] **Step 1: Tests de config**
  - `test_valores_por_defecto`: `cargar_config({})` → `db_path == Path.home()/".alquiler_equipos"/"alquiler.db"`, `admin_password == "admin1234"`, `factor_mora == 1.5`, `anthropic_api_key is None`
  - `test_factor_mora_acepta_coma_decimal`: `{"ALQUILER_FACTOR_MORA": "1,5"}` → `1.5`
  - `test_factor_mora_invalido`: `"abc"` y `"0"` → `pytest.raises(ValueError, match="ALQUILER_FACTOR_MORA")`
  - `test_api_key_vacia_es_none`: `{"ANTHROPIC_API_KEY": "  "}` → `None`
- [ ] **Step 2: Tests de DB**
  - `test_foreign_keys_activas`: `PRAGMA foreign_keys` devuelve 1 en una conexión nueva
  - `test_crea_directorio_padre(tmp_path)`: `crear_engine(tmp_path/"a"/"b"/"x.db")` + conectar → existe el archivo
- [ ] **Step 3: Ejecutar** `pytest -q` → FAIL (módulos inexistentes)
- [ ] **Step 4: Implementar** `config.py`, `db.py` (listener `connect` que ejecuta `PRAGMA foreign_keys=ON`), `errors.py`, `conftest.py`
- [ ] **Step 5: Ejecutar** `pytest -q` → PASS
- [ ] **Step 6: Commit** `feat: estructura base, configuración y conexión SQLite`

### Task 2 (Tarea 1.2): Modelos ORM de las 9 entidades

**Files:**
- Create: `alquiler/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `db.Base`, fixture `session`
- Produces: enums `Rol, EstadoEquipo, EstadoAlquiler, TipoMantenimiento, ConceptoPago, MetodoPago, TipoRecomendacion, EstadoRecomendacion, Nivel` (`str, enum.Enum`, valores de spec §4.1) y modelos `Usuario, Cliente, Categoria, Equipo, Alquiler, Devolucion, Pago, Mantenimiento, RecomendacionIA` con los campos de spec §4.2. Relaciones: `Categoria.equipos`, `Equipo.categoria`, `Equipo.alquileres`, `Equipo.mantenimientos`, `Cliente.alquileres`, `Cliente.usuario`, `Usuario.cliente`, `Alquiler.cliente`, `Alquiler.equipo`, `Alquiler.devolucion` (uselist=False), `Alquiler.pagos`, `Devolucion.alquiler`, `Pago.alquiler`, `Mantenimiento.equipo`. Enums con `SAEnum(..., native_enum=False, values_callable=lambda e: [m.value for m in e], validate_strings=True)`. Restricciones CHECK con nombre (`ck_<tabla>_<regla>`).

- [ ] **Step 1: Tests** (helper `_equipo(session, **kw)` que crea una categoría y un equipo válidos)
  - `test_se_crean_las_9_tablas`: `inspect(engine).get_table_names()` ⊇ `{"usuario","cliente","categoria","equipo","alquiler","devolucion","pago","mantenimiento","recomendacion_ia"}`
  - `test_equipo_nace_disponible_con_contadores_en_cero`
  - `test_estado_se_guarda_como_texto_legible`: SQL crudo `SELECT estado FROM equipo` → `"Disponible"`
  - `test_codigo_equipo_unico`, `test_documento_cliente_unico`, `test_username_unico` → `IntegrityError`
  - `test_tarifa_debe_ser_positiva` (0 → `IntegrityError`)
  - `test_fk_categoria_inexistente_falla` (Review Focus 2)
  - `test_fecha_fin_no_anterior_a_inicio` → `IntegrityError`
  - `test_un_alquiler_solo_tiene_una_devolucion` → `IntegrityError`
  - `test_pago_monto_positivo` → `IntegrityError`
  - `test_puntaje_recomendacion_entre_0_y_100` (101 → `IntegrityError`)
  - `test_recomendacion_guarda_justificacion_y_datos_json`: lista + dict sobreviven a un ciclo commit/expire/reload
  - `test_relaciones_navegables`: alquiler con pago y devolución → `cliente.alquileres[0].devolucion.total`, `alquiler.pagos[0].monto`
- [ ] **Step 2: Ejecutar** `pytest tests/test_models.py -q` → FAIL
- [ ] **Step 3: Implementar** `alquiler/models.py`; `JSON` de SQLAlchemy para `justificacion`/`datos_respaldo`; `creado_en` con `default=datetime.now`
- [ ] **Step 4: Ejecutar** `pytest -q` → PASS
- [ ] **Step 5: Commit** `feat: modelos ORM de las 9 entidades con restricciones`

### Task 3 (Tarea 1.3): Migración inicial con Alembic e `init_db`

**Files:**
- Create: `alembic.ini`, `alquiler/migrations/env.py`, `alquiler/migrations/script.py.mako`, `alquiler/migrations/versions/0001_esquema_inicial.py`
- Modify: `alquiler/db.py` (añadir `init_db`)
- Test: `tests/test_migraciones.py`

**Interfaces:**
- Consumes: `models` (todo), `db.crear_engine`
- Produces: `db.init_db(engine: Engine) -> None` — ejecuta `alembic upgrade head` programáticamente sobre ese engine (pasando la conexión vía `config.attributes["connection"]`). `env.py` usa `render_as_batch=True` (SQLite) y `target_metadata = Base.metadata`.

- [ ] **Step 1: Tests**
  - `test_upgrade_crea_esquema(tmp_path)`: `init_db(crear_engine(tmp_path/"t.db"))` → existen las 9 tablas + `alembic_version`
  - `test_migracion_coincide_con_modelos(tmp_path)`: tras `init_db`, `alembic.autogenerate.compare_metadata(MigrationContext.configure(conn), Base.metadata) == []`
  - `test_init_db_es_idempotente(tmp_path)`: dos llamadas no fallan
- [ ] **Step 2: Ejecutar** → FAIL
- [ ] **Step 3: Generar** la revisión `0001` con `alembic revision --autogenerate` contra una DB vacía, revisarla a mano (nombres de CHECK, longitudes), e implementar `init_db`
- [ ] **Step 4: Ejecutar** `pytest -q` → PASS
- [ ] **Step 5: Commit** `feat: migración inicial Alembic e init_db`

### Task 4 (Tarea 1.4): Autenticación y RBAC

**Files:**
- Create: `alquiler/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Usuario`, `Rol`, `Cliente`, errores
- Produces:
  - `class Permiso(str, Enum)` con los 15 valores de spec §5 (`catalogo.ver`, `perfil.propio`, `equipos.gestionar`, `equipos.eliminar`, `clientes.ver`, `clientes.gestionar`, `alquileres.ver`, `alquileres.gestionar`, `devoluciones.registrar`, `mantenimiento.ver`, `mantenimiento.gestionar`, `ia.ver`, `ia.consultas`, `reportes.ver`, `usuarios.gestionar`)
  - `PERMISOS_POR_ROL: dict[Rol, frozenset[Permiso]]`
  - `hash_password(plano: str) -> str`, `verificar_password(plano: str, hash_: str) -> bool`
  - `crear_usuario(session, username, password, rol: Rol, nombre_completo: str, cliente_id: int | None = None) -> Usuario`
  - `autenticar(session, username, password) -> Usuario`
  - `tiene_permiso(usuario: Usuario, permiso: Permiso) -> bool`, `requerir_permiso(usuario, permiso) -> None`
  - `asegurar_admin_inicial(session, password: str) -> Usuario | None` (devuelve el admin creado o `None` si ya había uno)

- [ ] **Step 1: Tests**
  - Hash: `test_hash_no_es_texto_plano_y_verifica`, `test_hash_con_sal_distinta` (dos hashes del mismo texto difieren)
  - `test_password_corta_rechazada` (7 caracteres → `ReglaNegocioError`)
  - `test_password_mayor_72_bytes_rechazada`: `"ñ"*37` (74 bytes) → `ReglaNegocioError` (Review Focus 5)
  - `test_username_se_normaliza`: crear `" Admin "` → guardado `"admin"`; `autenticar(s, "ADMIN", pwd)` funciona (Review Focus 1)
  - `test_username_duplicado_rechazado` → `ReglaNegocioError` (no `IntegrityError`)
  - `test_rol_cliente_requiere_cliente_id` y `test_rol_no_cliente_no_admite_cliente_id` → `ReglaNegocioError`
  - `test_autenticar_password_incorrecta`, `test_autenticar_usuario_inexistente` → `CredencialesInvalidas` con el **mismo** mensaje
  - `test_usuario_inactivo_no_entra` → `CredencialesInvalidas`
  - Matriz: `test_admin_tiene_todos_los_permisos`; parametrizado `test_matriz_rbac[rol, permiso, esperado]` para las filas de spec §5 (empleado sin `reportes.ver`, `ia.consultas`, `usuarios.gestionar`, `equipos.eliminar`; cliente solo `catalogo.ver` y `perfil.propio`)
  - `test_requerir_permiso_lanza_permiso_denegado`
  - `test_admin_inicial_se_crea_una_sola_vez`
- [ ] **Step 2: Ejecutar** → FAIL
- [ ] **Step 3: Implementar** `auth.py` (bcrypt `gensalt()`; validar tamaño en bytes antes de hashear)
- [ ] **Step 4: Ejecutar** `pytest -q` → PASS (suite completa)
- [ ] **Step 5: Commit** `feat: autenticación bcrypt y matriz RBAC`

---

## FASE 2 — Servicios de dominio

**Spec:** §3 (contrato de servicios), §4.3–4.4 (estados y cálculos), §5 (RBAC), §7 (reportes).

### Convenciones de la Fase 2 (aplican a las Tareas 5–11)

- Cada operación pública: `def op(session: Session, actor: Usuario, ..., hoy: date | None = None)`. El primer paso es `requerir_permiso(actor, Permiso.X)`; después se validan **todas** las reglas y solo entonces se modifica algo y se hace `session.commit()`. Un `ReglaNegocioError` nunca deja cambios a medias.
- Las funciones que dependen de la fecha reciben `hoy` (por defecto `date.today()`) para que las pruebas sean deterministas.
- `alquiler/services/__init__.py` expone un único helper: `obtener(session, modelo, id_) -> objeto`, que lanza `ReglaNegocioError("<Entidad> no existe.")` (nombres: Equipo, Categoría, Cliente, Alquiler, Mantenimiento, Usuario).
- Los textos de identificación (`codigo` de equipo, `documento` de cliente) se normalizan con `strip()` (código además en mayúsculas) **antes** de comprobar la unicidad, y el duplicado da `ReglaNegocioError`, nunca `IntegrityError`.
- Fixtures compartidas en `tests/services/conftest.py` (sobre la fixture `session` de la Fase 1): `admin`, `empleado`, `usuario_cliente` (enlazado a `cliente`), `categoria` ("Taladros", 20 usos / 90 días), `equipo` ("TAL-001", tarifa 25 000, Disponible), `cliente` (documento "1085000001"). Los usuarios se crean con `password_hash="x"` directamente en el modelo (sin bcrypt, para que la suite sea rápida). Constante `HOY = date(2026, 3, 10)`.

### Review Focus (Fase 2)

1. **Doble clic en "Registrar devolución"** → la segunda llamada da `ReglaNegocioError("El alquiler no está activo…")` y los contadores de uso del equipo solo suben una vez. (Tarea 9)
2. **Pago mayor que el saldo pendiente, o pago a un alquiler cancelado** → rechazado con un mensaje que indica el saldo. (Tarea 7)
3. **Fecha de devolución anterior al inicio del alquiler (error de digitación)** → rechazada; no se calcula una mora negativa ni un total menor que el costo. (Tarea 9)
4. **Código o documento duplicado escrito con espacios o en minúsculas** (`" tal-001 "`) → se detecta como duplicado. (Tareas 5 y 6)
5. **Reporte con período invertido o sin datos** → `desde > hasta` da `ReglaNegocioError`; un período vacío devuelve ceros, sin división por cero. (Tarea 10)

### Task 5 (Tarea 2.1): Equipos, categorías y máquina de estados

**Files:** Create `alquiler/services/__init__.py`, `alquiler/services/equipos.py`, `tests/services/__init__.py`, `tests/services/conftest.py` · Test `tests/services/test_equipos.py`

**Interfaces:**
- Consumes: `auth.requerir_permiso`, `Permiso`, modelos.
- Produces:
  - `TRANSICIONES: dict[EstadoEquipo, frozenset[EstadoEquipo]]` = tabla de spec §4.3.
  - `transicionar(equipo: Equipo, nuevo: EstadoEquipo) -> None`: valida contra `TRANSICIONES`, si no es válida lanza `ReglaNegocioError("Transición no permitida: <actual> → <nuevo>")`; **no** hace commit. La usan las Tareas 7–9.
  - `crear_categoria(session, actor, nombre, descripcion=None, intervalo_mant_usos=20, intervalo_mant_dias=90) -> Categoria` · `EQUIPOS_GESTIONAR`.
  - `listar_categorias(session, actor) -> list[Categoria]` · `CATALOGO_VER`.
  - `crear_equipo(session, actor, codigo, nombre, categoria_id, tarifa_diaria, fecha_adquisicion, descripcion=None) -> Equipo` · `EQUIPOS_GESTIONAR`.
  - `actualizar_equipo(session, actor, equipo_id, **campos) -> Equipo` · `EQUIPOS_GESTIONAR`; solo admite `nombre, descripcion, categoria_id, tarifa_diaria`.
  - `dar_de_baja(session, actor, equipo_id) -> Equipo` · `EQUIPOS_GESTIONAR`; pasa a `Fuera de servicio`.
  - `eliminar_equipo(session, actor, equipo_id) -> None` · `EQUIPOS_ELIMINAR`; solo si no tiene alquileres ni mantenimientos.
  - `listar_equipos(session, actor, estado=None, categoria_id=None, texto=None) -> list[Equipo]` · `CATALOGO_VER`; si el actor es cliente, solo devuelve los `Disponible`; `texto` busca en código y nombre sin distinguir mayúsculas; orden por código.

- [ ] **Step 1: Pruebas (RED)**
  - `test_transiciones_validas[desde,hacia]` (parametrizado con las 11 ✔ de §4.3) y `test_transiciones_invalidas[desde,hacia]` (las 9 ✘) → `ReglaNegocioError` con el texto "Transición no permitida".
  - `test_crear_equipo_normaliza_codigo`: `" tal-002 "` → `"TAL-002"`, estado Disponible.
  - `test_codigo_duplicado_con_espacios_y_minusculas` → `ReglaNegocioError` (Review Focus 4).
  - `test_tarifa_no_positiva_rechazada` (0 y −1), `test_categoria_inexistente_rechazada`.
  - `test_categoria_duplicada_sin_importar_mayusculas`.
  - `test_actualizar_equipo_campo_no_permitido` (`estado=`) → `ReglaNegocioError`; `test_actualizar_tarifa`.
  - `test_dar_de_baja_equipo_alquilado_rechazado`; `test_dar_de_baja_disponible`.
  - `test_eliminar_equipo_con_historial_rechazado` (con un `Mantenimiento`); `test_eliminar_equipo_sin_historial`.
  - `test_empleado_no_puede_eliminar` → `PermisoDenegado`; `test_cliente_no_puede_crear` → `PermisoDenegado`.
  - `test_cliente_solo_ve_disponibles`: 1 disponible + 1 en mantenimiento → el cliente ve 1, el empleado ve 2.
  - `test_listar_filtra_por_texto_estado_y_categoria`.
- [ ] **Step 2:** `pytest tests/services/test_equipos.py` → FAIL (`ModuleNotFoundError: alquiler.services`)
- [ ] **Step 3:** Implementar `services/__init__.py` y `services/equipos.py`
- [ ] **Step 4:** `pytest -W error` → PASS (suite completa)
- [ ] **Step 5:** Commit `feat: servicio de equipos con máquina de estados`

### Task 6 (Tarea 2.2): Clientes

**Files:** Create `alquiler/services/clientes.py` · Test `tests/services/test_clientes.py`

**Interfaces:**
- Produces:
  - `registrar_cliente(session, actor, documento, nombre, telefono, email=None, direccion=None) -> Cliente` · `CLIENTES_GESTIONAR`. El documento y el nombre son obligatorios, y el documento es único (Review Focus 4). Si se da un email, debe coincidir con `^[^@\s]+@[^@\s]+\.[^@\s]+$`.
  - `actualizar_cliente(session, actor, cliente_id, **campos) -> Cliente` puede usarse de dos formas:
    - con `CLIENTES_GESTIONAR`: modifica `nombre, telefono, email, direccion`;
    - un cliente sobre su propio registro (`perfil.propio` y `actor.cliente_id == cliente_id`): solo `telefono, email, direccion`.
  - `desactivar_cliente(session, actor, cliente_id) -> Cliente` · `CLIENTES_GESTIONAR`; se rechaza si tiene alquileres `reservado`/`activo`.
  - `buscar_clientes(session, actor, texto=None, incluir_inactivos=False) -> list[Cliente]` · `CLIENTES_VER`; busca en documento y nombre; orden por nombre.
  - `obtener_cliente`, `historial_cliente` (todos sus alquileres, orden `fecha_inicio` descendente) y `alquileres_activos_cliente` (estados reservado/activo) reciben `(session, actor, cliente_id)`. Se permiten con `CLIENTES_VER` o cuando el actor es ese mismo cliente; en otro caso, `PermisoDenegado`.
- [ ] **Step 1: Pruebas (RED)**
  - Registro y validaciones:
    - `test_registrar_cliente`
    - `test_documento_duplicado_con_espacios`
    - `test_email_invalido_rechazado`
    - `test_nombre_vacio_rechazado`
  - Edición:
    - `test_cliente_edita_su_telefono`
    - `test_cliente_no_edita_su_nombre` → `PermisoDenegado`
    - `test_cliente_no_edita_a_otro` → `PermisoDenegado`
  - Consultas del propio cliente: `test_cliente_ve_su_historial_y_no_el_ajeno`.
  - Bajas:
    - `test_desactivar_con_alquiler_activo_rechazado`
    - `test_desactivado_no_aparece_en_busqueda_por_defecto`
  - `test_historial_ordenado_del_mas_reciente`: dos alquileres, el más nuevo primero.
  - `test_alquileres_activos_excluye_finalizados_y_cancelados`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** `pytest -W error` PASS · **Step 5:** Commit `feat: servicio de clientes`

### Task 7 (Tarea 2.3): Alquileres y pagos

**Files:** Create `alquiler/services/alquileres.py` · Test `tests/services/test_alquileres.py`

**Interfaces:**
- Consumes: `equipos.transicionar`.
- Produces:
  - Funciones puras sobre los datos:
    - `dias_contratados(inicio: date, fin: date) -> int` = `max(1, (fin − inicio).days)`
    - `calcular_costo(inicio, fin, tarifa_diaria) -> int`
    - `total_adeudado(alquiler) -> int` = `devolucion.total` si hay devolución; si no, `costo_estimado`
    - `saldo_pendiente(alquiler) -> int` = adeudado − Σ pagos
  - `crear_alquiler(session, actor, cliente_id, equipo_id, fecha_inicio, fecha_fin_prevista, hoy=None) -> Alquiler` · `ALQUILERES_GESTIONAR`.
    - Exige cliente activo, equipo `Disponible`, `fecha_inicio ≥ hoy` y `fin ≥ inicio`.
    - Si `fecha_inicio > hoy`: alquiler `reservado` y equipo `Reservado`; si no, alquiler `activo` y equipo `Alquilado`.
    - Copia la tarifa del equipo y registra `registrado_por = actor`.
  - `entregar_reserva(session, actor, alquiler_id, hoy=None) -> Alquiler`: el alquiler debe estar `reservado` y debe cumplirse `hoy ≥ fecha_inicio`. Pasa el equipo a `Alquilado` y el alquiler a `activo`.
  - `cancelar_alquiler(session, actor, alquiler_id) -> Alquiler`: solo desde `reservado`. Pasa el equipo a `Disponible` y el alquiler a `cancelado`.
  - `registrar_pago(session, actor, alquiler_id, monto, metodo: MetodoPago, concepto: ConceptoPago, hoy=None) -> Pago`.
    - Exige `monto > 0` y que el alquiler no esté cancelado.
    - Exige `monto ≤ saldo_pendiente`; si no, da `ReglaNegocioError("El pago excede el saldo pendiente ($X).")` (Review Focus 2).
  - `listar_alquileres(session, actor, estado=None, cliente_id=None) -> list[Alquiler]` · `ALQUILERES_VER`, orden descendente por `fecha_inicio`.
  - `alquileres_vencidos(session, actor, hoy=None) -> list[Alquiler]` · `ALQUILERES_VER`: activos con `fecha_fin_prevista < hoy`.
- [ ] **Step 1: Pruebas (RED)**
  - Costos:
    - `test_costo_mismo_dia_cobra_un_dia` (25 000)
    - `test_costo_tres_dias` (1→4 de marzo = 75 000)
  - Creación y estados:
    - `test_alquiler_hoy_queda_activo_y_equipo_alquilado`
    - `test_alquiler_futuro_queda_reservado`
    - `test_tarifa_se_congela_al_contratar`: se cambia la tarifa del equipo después y el alquiler conserva la original.
  - Validaciones al crear:
    - `test_fecha_inicio_pasada_rechazada`
    - `test_equipo_no_disponible_rechazado`
    - `test_cliente_inactivo_rechazado`
    - `test_cliente_no_puede_crear_alquiler` → `PermisoDenegado`
  - Reservas:
    - `test_entregar_reserva`
    - `test_entregar_antes_de_inicio_rechazado`
    - `test_cancelar_reserva_libera_equipo`
    - `test_cancelar_activo_rechazado`
  - Pagos:
    - `test_pago_parcial_reduce_saldo`
    - `test_pago_mayor_al_saldo_rechazado`
    - `test_pago_a_cancelado_rechazado`
  - Consultas: `test_vencidos_solo_activos_con_fin_pasado`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: servicio de alquileres y pagos`

### Task 8 (Tarea 2.5): Mantenimiento

*(Se implementa antes que las devoluciones, porque una devolución con daños abre un correctivo.)*

**Files:** Create `alquiler/services/mantenimiento.py` · Test `tests/services/test_mantenimiento.py`

**Interfaces:**
- Produces:
  - `abrir(session, equipo, tipo, descripcion, fecha) -> Mantenimiento`: helper interno, sin permiso ni commit.
    - Ejecuta `transicionar(equipo, EN_MANTENIMIENTO)`.
    - Guarda `usos_al_momento = equipo.usos_acumulados`.
    - La Tarea 9 lo reutiliza.
  - `abrir_mantenimiento(session, actor, equipo_id, tipo, descripcion, hoy=None) -> Mantenimiento` · `MANTENIMIENTO_GESTIONAR`.
    - Exige una descripción no vacía.
    - Si el equipo ya está `En mantenimiento`, da `ReglaNegocioError("ya tiene un mantenimiento abierto")`.
    - Un equipo `Fuera de servicio` se puede rehabilitar a través de aquí.
  - `cerrar_mantenimiento(session, actor, mantenimiento_id, costo=0, notas=None, hoy=None) -> Mantenimiento`.
    - Exige que esté abierto, `costo ≥ 0` y `hoy ≥ fecha_inicio`.
    - Fija `fecha_fin = hoy` y añade las `notas` a la descripción.
    - Deja el equipo `Disponible`.
  - `historial_mantenimiento(session, actor, equipo_id) -> list[Mantenimiento]` (descendente) y `mantenimientos_abiertos(session, actor) -> list[Mantenimiento]` · `MANTENIMIENTO_VER`.
- [ ] **Step 1: Pruebas (RED)**
  - Apertura:
    - `test_abrir_preventivo_pasa_equipo_a_mantenimiento_y_guarda_usos`: un equipo con 12 usos guarda `usos_al_momento == 12`.
    - `test_abrir_en_equipo_alquilado_rechazado`
    - `test_abrir_dos_veces_rechazado`
    - `test_descripcion_vacia_rechazada`
  - Cierre:
    - `test_cerrar_devuelve_disponible_con_costo_y_fecha`
    - `test_cerrar_ya_cerrado_rechazado`
    - `test_costo_negativo_rechazado`
  - `test_rehabilitar_fuera_de_servicio`: pasa de Fuera de servicio a En mantenimiento y luego a Disponible.
  - `test_historial_descendente`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: servicio de mantenimiento`

### Task 9 (Tarea 2.4): Devoluciones

**Files:** Create `alquiler/services/devoluciones.py` · Test `tests/services/test_devoluciones.py`

**Interfaces:**
- Consumes: `equipos.transicionar`, `mantenimiento.abrir`.
- Produces:
  - `@dataclass(frozen=True) Liquidacion(dias_retraso: int, recargo_mora: int, total: int)`
  - `liquidar(alquiler, fecha_devolucion, factor_mora: float, penalizacion_danos: int = 0) -> Liquidacion`. Aplica spec §4.4; el redondeo es half-up con `Decimal`.
  - `registrar_devolucion(session, actor, alquiler_id, fecha_devolucion, horas_uso: float, factor_mora: float, con_danos=False, descripcion_danos=None, penalizacion_danos=0) -> Devolucion` · `DEVOLUCIONES_REGISTRAR`.
    - Validaciones:
      - el alquiler debe estar `activo` (Review Focus 1);
      - `fecha_devolucion ≥ fecha_inicio` (Review Focus 3);
      - `horas_uso ≥ 0` y `penalizacion_danos ≥ 0`;
      - `con_danos` exige una descripción;
      - una penalización > 0 sin daños se rechaza.
    - Efectos:
      - el alquiler pasa a `finalizado`;
      - el equipo suma `usos_acumulados += 1` y `horas_uso_acumuladas += horas_uso`;
      - sin daños, el equipo queda `Disponible`;
      - con daños, se abre un correctivo con `"Daños reportados en devolución: <desc>"`.
- [ ] **Step 1: Pruebas (RED)**
  - Liquidación:
    - `test_devolucion_a_tiempo_sin_mora`
    - `test_devolucion_anticipada_no_reembolsa`: el total sigue siendo `costo_estimado`.
    - `test_mora_dos_dias_factor_1_5`: tarifa 25 000, 2 días → mora 75 000 y total = costo + 75 000.
    - `test_mora_redondeo_half_up`: tarifa 10 003, 1 día, factor 1,5 → 15 005. La cuenta exacta da 15 004,5: el half-up sube a 15 005, mientras que el `round` de Python (redondeo bancario) bajaría a 15 004.
  - Efectos sobre el equipo:
    - `test_devolucion_sin_danos_libera_equipo_y_suma_uso`: usos 0→1, horas 0→8.
    - `test_devolucion_con_danos_abre_correctivo`: equipo En mantenimiento, 1 correctivo con la descripción y penalización en el total.
  - Validaciones:
    - `test_danos_sin_descripcion_rechazado`
    - `test_penalizacion_sin_danos_rechazada`
    - `test_fecha_devolucion_antes_del_inicio_rechazada`
    - `test_horas_negativas_rechazadas`
  - `test_doble_devolucion_rechazada_sin_duplicar_usos`: tras el segundo intento, `usos_acumulados == 1`.
  - `test_devolver_reserva_rechazado`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: servicio de devoluciones con mora y daños`

### Task 10 (Tarea 2.6): Reportes

**Files:** Create `alquiler/services/reportes.py` · Test `tests/services/test_reportes.py`

**Interfaces:** (todas exigen `REPORTES_VER`; `desde > hasta` lanza `ReglaNegocioError`)
- `ingresos(session, actor, desde, hasta) -> Ingresos`.
  - Tipo: `@dataclass Ingresos(total: int, por_concepto: dict[ConceptoPago, int], por_mes: dict[str, int])`.
  - Suma los `Pago` con fecha en [desde, hasta].
  - `por_concepto` incluye los 3 conceptos aunque valgan 0.
  - `por_mes` usa claves `"AAAA-MM"`.
- `uso_flota(session, actor, desde, hasta, hoy=None) -> list[UsoEquipo]`.
  - Tipo: `@dataclass UsoEquipo(equipo_id, codigo, nombre, categoria, dias_alquilado, dias_periodo, porcentaje)`.
  - Cada alquiler ocupa el intervalo semiabierto `[fecha_inicio, fin)`:
    - `fin` = fecha de devolución; si sigue activo, `min(hoy, hasta) + 1 día`;
    - un alquiler de un solo día ocupa 1 día.
  - Se excluyen los alquileres cancelados y reservados.
  - `dias_periodo = (hasta − desde).days + 1`; `porcentaje` va redondeado a 1 decimal.
  - Orden: `porcentaje` descendente, luego código. Incluye los equipos sin uso (0 %).
- `uso_por_categoria(session, actor, desde, hasta, hoy=None) -> dict[str, float]`: Σ días ÷ (n.º de equipos × días del período) × 100.
- `morosidad(session, actor, factor_mora, hoy=None) -> Morosidad`.
  - Tipo: `@dataclass Morosidad(vencidos: list[AlquilerVencido], mora_facturada: int, mora_cobrada: int, tasa_retraso: float)`.
  - Tipo: `AlquilerVencido(alquiler_id, cliente, equipo, dias_vencido, mora_estimada)`.
  - `tasa_retraso` = devoluciones con retraso ÷ devoluciones (0.0 si no hay ninguna).
- [ ] **Step 1: Pruebas (RED)**
  - Ingresos:
    - `test_ingresos_suma_por_concepto_y_mes`: pagos en febrero y en marzo, uno fuera del período.
    - `test_periodo_invertido_rechazado`
    - `test_periodo_sin_datos_da_ceros`: los 3 conceptos en 0 y `total == 0` (Review Focus 5).
  - Uso de flota:
    - `test_uso_flota_porcentaje`: período del 1 al 10 de marzo (10 días) y alquiler del 1 al 4 devuelto el 4 → 3 días = 30.0 %.
    - `test_uso_flota_recorta_al_periodo`: un alquiler que empieza antes del período solo cuenta los días dentro.
    - `test_uso_flota_activo_cuenta_hasta_hoy`
    - `test_uso_flota_ignora_cancelados`
    - `test_equipo_sin_uso_aparece_con_cero`
  - Morosidad:
    - `test_morosidad_vencidos_y_mora_estimada`: un activo vencido 2 días con tarifa 25 000 y factor 1,5 da `mora_estimada == 75 000`.
    - `test_tasa_retraso_sin_devoluciones_es_cero`
  - `test_empleado_no_ve_reportes` → `PermisoDenegado`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: servicio de reportes`

### Task 11 (Tarea 2.7): Usuarios

**Files:** Create `alquiler/services/usuarios.py` · Modify `alquiler/auth.py` (renombrar `_validar_password` → `validar_password` público; exigir `nombre_completo` no vacío — minor diferido de la Fase 1) · Test `tests/services/test_usuarios.py`

**Interfaces:**
- `crear_usuario(session, actor, username, password, rol, nombre_completo, cliente_id=None) -> Usuario` · `USUARIOS_GESTIONAR`; delega en `auth.crear_usuario`.
- `listar_usuarios(session, actor) -> list[Usuario]` · `USUARIOS_GESTIONAR`; orden por username.
- `cambiar_estado_usuario(session, actor, usuario_id, activo: bool) -> Usuario` · `USUARIOS_GESTIONAR`. Al desactivar se aplican dos restricciones:
  - no puede tratarse del propio actor;
  - no puede ser el último administrador activo.
- `cambiar_password(session, actor, actual, nueva) -> None` · `PERFIL_PROPIO`. Verifica la contraseña actual: si es incorrecta, da `CredencialesInvalidas`. Valida la nueva.
- `restablecer_password(session, actor, usuario_id, nueva) -> None` · `USUARIOS_GESTIONAR`.
- [ ] **Step 1: Pruebas (RED)**
  - Creación:
    - `test_admin_crea_empleado`
    - `test_empleado_no_crea_usuarios` → `PermisoDenegado`
    - `test_nombre_completo_vacio_rechazado`
  - Desactivación:
    - `test_admin_no_se_desactiva_a_si_mismo`
    - `test_no_se_desactiva_el_ultimo_admin`: hay dos admins y uno de ellos ya está desactivado.
    - `test_desactivar_y_reactivar_empleado`
  - Contraseñas:
    - `test_cambiar_password_propia`: la nueva autentica y la anterior no.
    - `test_cambiar_password_con_actual_incorrecta`
    - `test_cliente_cambia_su_password`
    - `test_restablecer_password_por_admin`
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: servicio de usuarios`

## FASE 3 — Motor de IA explicable

**Spec:** §6 (6.1–6.4 revisado), §9. Paquete `alquiler/ai/`. Pruebas en `tests/ai/`; **ninguna prueba llama a la red**.

### Convenciones de la Fase 3

- Cada analizador devuelve `Resultado` (spec §6) y exige `Permiso.IA_VER`. Las consultas en lenguaje natural exigen `Permiso.IA_CONSULTAS`.
- Los analizadores reciben `hoy: date | None` y son deterministas.
- `tests/ai/conftest.py` reutiliza las fixtures de `tests/services/conftest.py` (re-export) y añade `historial(session, ...)`. Este helper inserta alquileres y devoluciones sintéticos directamente en los modelos.
- Orden de las tareas: primero los analizadores (12–14), porque la consulta predefinida "equipos a revisar" usa el recomendador. Después la capa Text-to-SQL (15–17), siguiendo los bloques pedidos por el usuario: configuración → seguridad → prompt/cliente → orquestación y explicabilidad.

### Review Focus (Fase 3)

1. **Ruta real del usuario con espacios** (`…\Nueva carpeta\…`) y con tildes → el ejecutor de solo lectura abre la base sin error. (Tarea 15)
2. **SQL legítimo con palabras "peligrosas" dentro de literales o funciones** (`replace(nombre, …)`, `LIKE '%drop%'`, `-- delete` en un comentario) → se permite, sin falsos positivos; `WITH … DELETE` sigue bloqueado. (Tarea 15)
3. **El modelo devuelve JSON con forma inesperada, la clave API es inválida o no hay red** → `RespuestaConsulta(estado="error")` con un mensaje en español, sin excepción no controlada. (Tareas 16–17)
4. **Resultado enorme** (miles de filas) → se devuelven 200 filas marcadas como `truncado` y solo 50 viajan al modelo en el paso 3. (Tareas 15 y 17)
5. **Pregunta vacía, solo espacios o de más de 500 caracteres** → se rechaza sin llamar a la API (costo 0). (Tarea 17)

### Task 12 (Tarea 3.1): `Resultado` y predicción de demanda

**Files:** Create `alquiler/ai/__init__.py`, `alquiler/ai/resultado.py`, `alquiler/ai/demanda.py`, `tests/ai/__init__.py`, `tests/ai/conftest.py` · Test `tests/ai/test_demanda.py`

**Interfaces:**
- `@dataclass(frozen=True) Resultado(resumen: str, valor: float | None, confianza: Nivel, indicadores: dict, justificacion: list[str], advertencia: str)`.
- `serie_mensual(session, categoria_id, hasta_mes: date) -> list[tuple[date, int]]`.
  - Cuenta los alquileres no cancelados por mes de `fecha_inicio`, desde el primer mes con datos del sistema hasta el último mes completo anterior a `hoy`.
  - Incluye los meses en 0.
- `predecir_demanda(session, actor, hoy=None) -> list[Resultado]`: uno por categoría, ordenado por nombre. Algoritmo de spec §6.1, con estas precisiones:
  - índice estacional `I_m = media(mes m) / media global` solo si hay ≥ 12 meses (si no, o si la media global es 0, `I_m = 1`);
  - al desestacionalizar, `max(I_m, 0.1)`;
  - residuos = predicción con el mismo método sobre los 3 meses previos frente al valor real, para cada mes desde el 4.º;
  - `σ` = desviación poblacional de los residuos; si hay menos de 2 residuos, margen = 50 % del pronóstico;
  - `cv = σ / media de la serie`.
- `indicadores` incluye: `meses_historial`, `pronostico`, `rango` [min, max], `indice_estacional` (12 valores), `picos` (nombres de mes en español), `ultimos_3_meses`.
- [ ] **Step 1: Pruebas (RED)**
  - `test_pico_de_diciembre_detectado`:
    - datos: 24 meses con 10 alquileres por mes y 25 en diciembre; `hoy` = 2026-11-15;
    - esperado: `"diciembre" in picos`, pronóstico entre 20 y 30, confianza alta.
  - `test_historial_corto_confianza_baja_e_indice_neutro`: 4 meses de datos dan confianza baja y los 12 índices en 1.0.
  - `test_categoria_sin_alquileres`: `valor is None`, confianza baja y un resumen que dice "sin historial".
  - `test_rango_contiene_pronostico_y_no_es_negativo`.
  - `test_cancelados_no_cuentan`.
  - `test_resultado_siempre_explicado`: para cada resultado, una justificación no vacía, una advertencia con "Estimación" y un resumen que contiene "≈" o "estima".
  - `test_cliente_no_accede` → `PermisoDenegado`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** `pytest -W error` PASS · **Step 5:** Commit `feat(ia): predicción de demanda explicable`

### Task 13 (Tarea 3.2): Recomendador de mantenimiento preventivo

**Files:** Create `alquiler/ai/mantenimiento.py` · Test `tests/ai/test_mantenimiento_ia.py`

**Interfaces:**
- `evaluar_equipo(equipo: Equipo, hoy: date, max_alquileres_30d: int) -> Resultado`: función pura sobre el objeto y sus relaciones, con los factores y pesos de spec §6.2.
  - "Último servicio" = el mantenimiento cerrado más reciente. La base de usos es su `usos_al_momento` y la de días es su `fecha_fin`.
  - Si no hay servicio previo: base de usos 0 y `fecha_adquisicion`.
  - Fallas = correctivos con `fecha_inicio` en los últimos 365 días.
  - `indicadores` incluye: cada factor (bruto y normalizado), `aporte_puntos` por factor, `prioridad`, `alquileres_totales`.
- `recomendar_mantenimiento(session, actor, hoy=None, persistir=True) -> list[Resultado]`.
  - Solo considera equipos `Disponible`, `Alquilado` y `Reservado`.
  - Devuelve únicamente los de puntaje ≥ 50, ordenados por puntaje descendente.
  - Con `persistir=True` hace un upsert de una `RecomendacionIA` **pendiente** por equipo (tipo mantenimiento). Actualiza la existente en lugar de duplicarla.
- [ ] **Step 1: Pruebas (RED)**
  - `test_equipo_desgastado_prioridad_alta`:
    - datos: 25 usos desde el servicio, intervalo de 20, 120 días contra 90, 2 correctivos en el año y el máximo de alquileres de la categoría;
    - esperado: puntaje ≥ 75, prioridad alta.
  - `test_equipo_nuevo_no_genera_alerta`: no aparece en `recomendar_mantenimiento`.
  - `test_puntaje_desglosado_suma_el_total`: la suma de `aporte_puntos` coincide con `valor` (tolerancia 0,01).
  - `test_factor_recortado_a_1`: con 100 usos sobre un intervalo de 20, el factor de usos aporta exactamente 35 pts.
  - `test_servicio_reciente_reinicia_contadores`: un preventivo cerrado ayer con `usos_al_momento == usos_acumulados` deja el factor de usos y el de días en ≈ 0.
  - `test_excluye_fuera_de_servicio_y_en_mantenimiento`.
  - `test_persiste_sin_duplicar`: dos ejecuciones dejan 1 `RecomendacionIA` pendiente por equipo, con `justificacion` y `datos_respaldo`.
  - `test_confianza_baja_con_pocos_alquileres`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ia): recomendador de mantenimiento preventivo`

### Task 14 (Tarea 3.3): Análisis de retrasos

**Files:** Create `alquiler/ai/retrasos.py` · Test `tests/ai/test_retrasos.py`

**Interfaces:**
- `K_SUAVIZADO = 5`
- `tasa_suavizada(retrasos: int, n: int, p_global: float, k: int = K_SUAVIZADO) -> float`
- `@dataclass AnalisisRetrasos(tasa_global: float, n_devoluciones: int, clientes_marcados: list[Resultado], por_categoria: list[Resultado])`
- `analizar_retrasos(session, actor, persistir=True) -> AnalisisRetrasos`. Aplica spec §6.3 sobre las `Devolucion`.
  - Los indicadores de cliente incluyen: `cliente_id`, `n`, `retrasos`, `tasa_observada`, `tasa_suavizada`, `dias_promedio_retraso`, `categoria_mas_asociada`.
  - Persiste una `RecomendacionIA` pendiente por cliente marcado (tipo retraso, `puntaje = 100 × tasa_suavizada`), haciendo upsert.
- [ ] **Step 1: Pruebas (RED)**
  - Casos de cliente:
    - `test_cliente_moroso_marcado`: un cliente con 4/4 tardías y 16 devoluciones a tiempo de otros (p = 0,2) queda marcado, con tasa suavizada > 0,4 y la categoría asociada en los indicadores.
    - `test_un_solo_retraso_no_marca`: un cliente con 1/1 tardía no queda marcado; con n < 3 nunca se marca.
  - Casos de la tasa global:
    - `test_tasa_suavizada_formula`: `tasa_suavizada(4, 4, 0.2) == (4 + 1) / 9`.
    - `test_sin_devoluciones`: tasa 0, sin marcados ni excepción.
    - `test_sin_retrasos_globales_no_marca_a_nadie`.
  - Explicación y persistencia:
    - `test_justificacion_explica_el_suavizado`: el texto menciona la tasa observada y la suavizada.
    - `test_persiste_sin_duplicar`.
  - `test_por_categoria_ordena_por_tasa`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ia): análisis de patrones de retraso`

### Task 15 (Tarea 3.4a): Configuración del modelo, validador SQL y ejecutor de solo lectura

**Files:** Modify `alquiler/config.py`, `tests/test_config.py`, `pyproject.toml`, `requirements.txt` (+ `anthropic>=1.11`) · Create `alquiler/ai/sql_seguro.py` · Test `tests/ai/test_sql_seguro.py`

**Interfaces:**
- `Config` gana `anthropic_timeout: float` (`ANTHROPIC_TIMEOUT`, por defecto 30, > 0, acepta coma decimal) y `anthropic_max_retries: int` (`ANTHROPIC_MAX_RETRIES`, por defecto 2, entre 0 y 10). `anthropic_model` pasa a tener por defecto `"claude-sonnet-5-5"`.
- `class ErrorSQL(ReglaNegocioError)`.
- `validar_sql(sql: str) -> str`: devuelve la sentencia limpia, sin el `;` final; si no es válida, lanza `ErrorSQL` con un motivo legible. Reglas de spec §6.4 Paso 2.
- `@dataclass ResultadoSQL(columnas: list[str], filas: list[tuple], truncado: bool, milisegundos: int)`.
- `ejecutar_lectura(db_path: Path, sql: str, limite: int = 200, timeout_s: float = 3.0) -> ResultadoSQL`. Valida primero; abre con `db_path.resolve().as_uri() + "?mode=ro"` y `uri=True`, `PRAGMA query_only=ON`, autorizador, `set_progress_handler` y `fetchmany(limite + 1)`. Los errores de SQLite se traducen a `ErrorSQL`; el de timeout dice "tardó demasiado".
- [ ] **Step 1: Pruebas (RED)**
  - Config:
    - `test_defaults_del_modelo`: `claude-sonnet-5-5`, 30.0 y 2.
    - `test_timeout_invalido` (0 y "x") y `test_reintentos_fuera_de_rango` (−1 y 11) → `ValueError` que nombra la variable.
  - Validador, consultas aceptadas: parametrizado `test_permite` con 4 casos:
    - `SELECT … ;` con espacios;
    - `WITH t AS (SELECT …) SELECT …`;
    - `SELECT replace(nombre,'a','b') FROM equipo`;
    - `SELECT * FROM equipo WHERE descripcion LIKE '%drop table%' -- delete`.
  - Validador, consultas rechazadas: parametrizado `test_rechaza` con 15 casos, todos con `ErrorSQL`:
    - `INSERT`, `UPDATE`, `DELETE`, `DROP TABLE`, `ALTER TABLE`, `CREATE TABLE`;
    - `REPLACE INTO`, `ATTACH DATABASE`, `PRAGMA`, `VACUUM`;
    - `WITH x AS (SELECT 1) DELETE FROM pago`;
    - `SELECT 1; DROP TABLE pago`;
    - `SELECT * FROM usuario`, `SELECT load_extension('x')`;
    - cadena vacía.
  - Ejecutor:
    - `test_ejecuta_y_devuelve_columnas`: sobre una base de archivo creada con `init_db` en `tmp_path / "Nueva carpeta ñ"` (Review Focus 1).
    - `test_trunca_a_limite`: 250 filas devuelven 200 con `truncado=True` (Review Focus 4).
    - `test_autorizador_bloquea_usuario_aunque_se_evada_el_validador`: llama a la función interna `_ejecutar_sin_validar` con `SELECT * FROM "usuario"` y espera `ErrorSQL`.
    - `test_conexion_es_de_solo_lectura`: un `INSERT` por la vía interna sin validador da `ErrorSQL` y la tabla sigue vacía.
    - `test_timeout`: un CTE recursivo infinito con `timeout_s=0.2` da `ErrorSQL` "tardó demasiado".
    - `test_sql_con_error_de_sintaxis_o_columna_inexistente` → `ErrorSQL` legible.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ia): configuración del modelo y ejecutor SQL de solo lectura`

### Task 16 (Tarea 3.4b): Inyección de esquema y cliente de Claude

**Files:** Create `alquiler/ai/prompts.py`, `alquiler/ai/llm.py` · Test `tests/ai/test_prompts.py`, `tests/ai/test_llm.py`

**Interfaces:**
- `prompts.TABLAS_EXCLUIDAS = {"usuario", "alembic_version"}`.
- `prompts.describir_esquema(metadata=Base.metadata) -> str`: genera una línea por tabla, con columnas, tipo, `PK`/`FK→tabla.col` y los valores permitidos de cada enum.
- `prompts.prompt_generacion(hoy: date) -> str`: esquema + reglas de negocio + restricciones + protocolo de ambigüedad + fecha.
- `prompts.ESQUEMA_GENERACION`: JSON Schema con `tipo` (enum), `sql`, `pasos` (array de string), `mensaje` y `sugerencias`, todos requeridos y `additionalProperties: false`.
- `prompts.prompt_respuesta()` y `prompts.mensaje_respuesta(pregunta, sql, columnas, filas, truncado) -> str`: como máximo 50 filas, en formato de tabla de texto. Con `prompts.ESQUEMA_RESPUESTA = {respuesta: string}`.
- `llm.ErrorIA(ReglaNegocioError)`.
- `llm.ClienteLLM` (Protocol): `generar_json(sistema: str, mensajes: list[dict], esquema: dict) -> dict`.
- `llm.ClienteClaude(api_key, modelo, timeout, max_retries, http_client=None)`.
  - Llama a `messages.create(model, max_tokens=2048, system, messages, output_config={"format": {"type": "json_schema", "schema": esquema}})`, toma el primer bloque de texto y hace `json.loads`.
  - Traduce los errores a `ErrorIA`:
    - `AuthenticationError` → "clave API inválida";
    - `RateLimitError` → "límite de uso";
    - `APITimeoutError`/`APIConnectionError` → "sin conexión o tiempo agotado";
    - `APIStatusError` → "el servicio respondió con un error (código)";
    - JSON inválido → "respuesta con formato inesperado".
- `llm.crear_cliente(config) -> ClienteLLM | None`: devuelve `None` si no hay `anthropic_api_key`.
- [ ] **Step 1: Pruebas (RED)** (las de `ClienteClaude` usan `httpx.MockTransport`, sin red)
  - Esquema:
    - `test_esquema_incluye_tablas_y_excluye_usuario`: contiene `equipo`, `alquiler`, `pago` y los valores `"En mantenimiento"` y `"activo"`; no contiene `usuario` ni `password_hash`.
    - `test_esquema_refleja_fk`: `alquiler.cliente_id FK→cliente.id`.
  - Prompts:
    - `test_prompt_generacion_incluye_fecha_y_reglas`: contiene `2026-03-10`, "solo SELECT" y "pesos".
    - `test_mensaje_respuesta_limita_a_50_filas_y_avisa_truncado`.
  - Cliente de Claude:
    - `test_cliente_envia_modelo_esquema_y_system`: inspecciona el cuerpo de la petición (`model == "claude-sonnet-5-5"`, `output_config.format.type == "json_schema"`, `system` presente).
    - `test_cliente_parsea_json_del_bloque_de_texto`.
    - parametrizado `test_traduce_errores` con 401, 429 (con `max_retries=0`), 500 (`max_retries=0`) y texto no JSON → `ErrorIA` con el mensaje esperado.
    - `test_reintenta_ante_500`: con `max_retries=1`, el transporte responde 500 y luego 200, y se obtiene el resultado tras 2 peticiones.
    - `test_crear_cliente_sin_clave_devuelve_none`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ia): inyección de esquema y cliente de Claude con salida estructurada`

### Task 17 (Tarea 3.4c): Orquestador de consultas, explicabilidad y consultas predefinidas

**Files:** Create `alquiler/ai/consultas.py` · Test `tests/ai/test_consultas.py`

**Interfaces:**
- `MAX_CARACTERES = 500`
- `ADVERTENCIA`: el texto fijo de spec §6.4.
- `@dataclass RespuestaConsulta(estado: str, pregunta: str, respuesta: str, pasos: list[str], sql: str | None = None, columnas: list[str] = [], filas: list[tuple] = [], truncado: bool = False, advertencia: str = ADVERTENCIA, sugerencias: list[str] = [])`, con listas por `field(default_factory=list)`.
- `consultar(session, actor, pregunta, cliente: ClienteLLM | None, db_path: Path, hoy=None) -> RespuestaConsulta`.
  - Sigue el flujo de spec §6.4: permiso → validación de la pregunta → `sin_api` → generación → `aclaracion`/`no_resoluble` → validar+ejecutar con **1 corrección** → `sin_datos` | segunda llamada → `ok`.
  - Un `ErrorIA` produce `estado="error"`.
- `@dataclass(frozen=True) ConsultaPredefinida(id: str, titulo: str, sql: str | None, pasos: tuple[str, ...])`.
- `CONSULTAS_PREDEFINIDAS: tuple[ConsultaPredefinida, ...]` (6). La de `equipos_a_revisar` tiene `sql=None` y usa el recomendador.
- `ejecutar_predefinida(session, actor, id_, db_path, hoy=None) -> RespuestaConsulta`.
  - Permiso `IA_CONSULTAS`.
  - Respuesta determinista: "N registros".
  - El SQL usa `:hoy`/fechas calculadas en Python e insertadas como literales ISO validados.
- [ ] **Step 1: Pruebas (RED)** (con `ClienteFalso(respuestas: list[dict | Exception])`, que registra las llamadas)
  - Preguntas inválidas:
    - `test_pregunta_vacia_o_larga_no_llama_api`: `""`, `"   "` y `"x"*501` dan `ReglaNegocioError` con 0 llamadas.
    - `test_empleado_sin_permiso` → `PermisoDenegado`.
  - Estados sin SQL ejecutado:
    - `test_sin_api_ofrece_predefinidas`: estado `sin_api` con 6 sugerencias.
    - `test_flujo_ok_dos_partes`:
      - el falso devuelve el SQL de los equipos más alquilados y luego `{respuesta: "El TAL-001…"}`;
      - esperado: estado `ok`, `respuesta` con el texto, `pasos` iguales a los del modelo, filas reales de la base, advertencia y 2 llamadas;
      - la 2.ª llamada contiene la pregunta, el SQL y las filas.
    - `test_sin_datos_no_hace_segunda_llamada`: estado `sin_datos`, 1 llamada, respuesta con "no devolvió registros".
    - `test_aclaracion`: estado `aclaracion` con el mensaje y las sugerencias del modelo, y `sql is None`.
    - `test_no_resoluble`.
  - Corrección del SQL:
    - `test_sql_destructivo_se_rechaza_y_se_corrige`:
      - 1.ª generación `DELETE FROM pago`, 2.ª un `SELECT` válido;
      - esperado: estado `ok`, la tabla `pago` intacta y la 2.ª llamada contiene el motivo del rechazo.
    - `test_dos_fallos_dan_error_con_sql_visible`: estado `error`, se muestra el `sql` y la tabla queda intacta.
  - Errores del modelo y del resultado:
    - `test_error_ia_da_estado_error`: el falso lanza `ErrorIA("sin conexión")`; estado `error` con el mensaje.
    - `test_respuesta_con_forma_invalida`: falta la clave `tipo` → estado `error` (Review Focus 3).
    - `test_truncado_se_advierte_y_solo_50_filas_al_modelo` (Review Focus 4).
  - Consultas predefinidas:
    - `test_predefinidas_ejecutan_sobre_base_real`: las 6 se ejecutan sin error sobre una base con datos.
    - `test_equipos_a_revisar_usa_recomendador`.
    - `test_todas_las_predefinidas_pasan_el_validador`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ia): consultas en lenguaje natural con explicabilidad`

## FASE 4 — Interfaz PySide6, datos de demostración e integración

**Spec:** §8 (revisado), §5 (RBAC), §6, §7.
**Pruebas:**
- Las de interfaz están en `tests/ui/` (pytest-qt, `QT_QPA_PLATFORM=offscreen` fijado en `tests/ui/conftest.py`).
- Las de lógica de presentación están en `tests/ui/logica/` y no usan Qt.
- Fixture común: `ctx_factory(tmp_path)` crea una base en archivo con `init_db`, una `fabrica_sesion` y un `Contexto` para el rol pedido. Usa un reloj fijo (`HOY = 2026-03-10`) y un `ClienteFalso` opcional.

### Convenciones de la Fase 4

- Funciones de `alquiler/ui/logica/*`:
  - firma `fn(ctx: Contexto, ...)`;
  - todo el trabajo con la base ocurre dentro de `ctx.ejecutar(lambda s, actor: …)`;
  - devuelven `list[dict]` o dataclasses planas;
  - las acciones devuelven `None` o un id.
- Formato:
  - `logica.formato.pesos(int) -> "$1.234.567"` (reutiliza `services.pesos`);
  - `fecha(date) -> "10/03/2026"`;
  - `nivel(str) -> "Alta" | "Media" | "Baja"`.
- En las vistas, los errores se muestran con `widgets.mostrar_error(parent, mensaje)`. Las pruebas la reemplazan con `monkeypatch` para registrar el mensaje en lugar de abrir un diálogo modal.
- Las confirmaciones usan `widgets.confirmar(parent, texto) -> bool`, que también se reemplaza en las pruebas.

### Review Focus (Fase 4)

1. **Cerrar la ventana con una consulta de IA en curso** → no se cae: `closeEvent` espera al pool y los slots ignoran resultados de widgets destruidos. (Tareas 18 y 25)
2. **Doble clic en "Consultar"/"Guardar"** → una sola operación: el botón se deshabilita hasta terminar. (Tareas 23 y 25)
3. **Un admin desactiva a un usuario con sesión abierta** → la siguiente acción de ese usuario da "La sesión ya no es válida", sin traceback. (Tarea 18)
4. **Primer arranque con base vacía** → se crea el admin y se ofrecen los datos demo. Si se rechazan, todas las vistas abren vacías sin errores. (Tareas 20 y 26)
5. **Entradas de formulario fuera de rango**:
   - fechas solo con `QDateEdit`; la devolución tiene como mínimo la fecha de inicio;
   - montos con `QSpinBox` (≥ 0, máximo 100 000 000);
   - cancelar un diálogo no escribe nada en la base. (Tareas 21–23 y 26)

### Task 18 (Tarea 4.1): Contexto, rollback, navegación, worker y prueba de arquitectura

**Files:** Create `alquiler/ui/__init__.py`, `alquiler/ui/logica/__init__.py`, `alquiler/ui/logica/contexto.py`, `alquiler/ui/logica/navegacion.py`, `alquiler/ui/logica/formato.py`, `alquiler/ui/trabajador.py`, `tests/ui/__init__.py`, `tests/ui/conftest.py`, `tests/ui/logica/__init__.py` · Modify `requirements.txt`/`pyproject.toml` (+ `PySide6>=6.6`, dev `pytest-qt>=4.4`) · Test `tests/ui/logica/test_contexto.py`, `tests/ui/test_trabajador.py`, `tests/ui/test_arquitectura.py`

**Interfaces:**
- `UsuarioSesion` (dataclass frozen): `id`, `username`, `nombre`, `rol: str`, `cliente_id`, `permisos: frozenset[str]`.
- `Contexto(fabrica_sesion, usuario: UsuarioSesion, config: Config, cliente_llm=None, reloj=date.today)`:
  - atributos `.usuario`, `.config`, `.cliente_llm`;
  - métodos `.hoy()`, `.puede(permiso: str) -> bool` y `.ejecutar(fn: Callable[[Session, Usuario], T]) -> T`.
- `iniciar_sesion(fabrica_sesion, config, username, password, cliente_llm=None, reloj=date.today) -> Contexto`.
- `navegacion.Seccion(clave, titulo, permiso)`, `SECCIONES` (10, en el orden de spec §8) y `secciones_para(ctx) -> list[Seccion]`.
- `trabajador.ejecutar_en_segundo_plano(fn: Callable[[], T], al_terminar: Callable[[T], None], al_fallar: Callable[[str], None], dueno: QObject) -> None`. Mantiene una referencia a la tarea hasta que termina. Errores: `ReglaNegocioError` → `str(e)`; otro error → `"Error inesperado: <Tipo>: <msg>"`.
- `trabajador.esperar_tareas(timeout_ms=5000)`.
- [ ] **Step 1: Pruebas (RED)**
  - Sesión e inicio:
    - `test_iniciar_sesion_ok_y_permisos_del_rol`
    - `test_credenciales_invalidas`
  - Rollback y errores:
    - `test_ejecutar_hace_rollback_si_falla`: añade una categoría, hace `flush` y lanza → la base no la tiene y la excepción se propaga.
    - `test_tras_un_error_la_siguiente_operacion_funciona`
    - `test_resultado_utilizable_tras_cerrar_sesion`
    - `test_usuario_desactivado_durante_la_sesion` (Review Focus 3)
  - Navegación:
    - `test_secciones_por_rol`: admin 10, empleado 7 (sin Reportes, Consola ni Usuarios), cliente 2 (Equipos y Mi perfil).
  - Formato: `test_formato_pesos_fecha_nivel`.
  - Trabajador (`qtbot`):
    - `test_trabajador_entrega_resultado_en_hilo_gui`: la función corre en otro hilo y el callback en el hilo GUI.
    - `test_trabajador_traduce_errores`: regla de negocio frente a error inesperado.
    - `test_trabajador_accede_a_la_base_desde_otro_hilo`
  - Arquitectura:
    - `test_vistas_no_importan_backend`: análisis AST de `alquiler/ui/**/*.py` excepto `app.py` y `logica/`. Prohíbe `alquiler.services`, `alquiler.ai`, `alquiler.models`, `alquiler.auth`, `alquiler.db`, `alquiler.seed` y `sqlalchemy`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** `pytest -W error` PASS · **Step 5:** Commit `feat(ui): contexto con rollback, navegación por rol y worker`

### Task 19 (Tarea 4.2): Datos de demostración

**Files:** Create `alquiler/seed.py` · Test `tests/test_seed.py` (base en memoria a nivel de módulo; `poblar` se ejecuta una vez)

**Interfaces:**
- `poblar(session, hoy: date, semilla: int = 42, meses: int = 18, admin_password: str = "admin1234") -> dict[str, int]`.
  - Simula día por día con los servicios reales: devoluciones (con propensión al retraso por cliente; 3 clientes morosos), daños (≈4 %) → correctivos que se cierran en 2–5 días, preventivos solo a veces, alquileres nuevos con estacionalidad por categoría y pagos (≈90 % al inicio; mora pagada ≈70 %).
  - Al final crea:
    - 3 reservas (pendiente, lista y vencida);
    - 5 clientes inactivos;
    - 2 equipos fuera de servicio.
  - Usuarios demo: spec §8.
  - Lanza `ReglaNegocioError` si ya hay alquileres.
- `main(argv=None) -> int`: argumentos `--hoy AAAA-MM-DD` y `--semilla N`. Migra la base, crea el admin, puebla e imprime el resumen.
- [ ] **Step 1: Pruebas (RED)**
  - Estado final:
    - `test_resumen_y_volumen`: ≥ 6 categorías, ≥ 35 equipos, ≥ 50 clientes, ≥ 800 alquileres.
    - `test_estados_finales_variados`: hay equipos en los 5 estados; clientes inactivos ≥ 5, alquileres activos ≥ 3, vencidos ≥ 1 y reservas en las 3 situaciones.
    - `test_usuarios_demo_autentican`
  - Alimenta a los analizadores y reportes:
    - `test_alimenta_a_los_analizadores`:
      - `recomendar_mantenimiento` devuelve ≥ 1 alerta;
      - `analizar_retrasos` marca ≥ 1 cliente;
      - `predecir_demanda` da al menos una categoría con confianza alta y con "diciembre" entre los picos;
      - `reportes.ingresos` > 0.
  - Determinismo y repetición:
    - `test_determinista`: misma semilla → mismo resumen.
    - `test_no_puebla_dos_veces`
  - CLI: `test_cli_crea_base_y_puebla(tmp_path)`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat: datos de demostración simulados con los servicios reales`

### Task 20 (Tarea 4.3): Widgets comunes, login, ventana principal y arranque

**Files:** Create `alquiler/ui/widgets.py`, `alquiler/ui/login.py`, `alquiler/ui/ventana.py`, `alquiler/ui/app.py`, `alquiler/__main__.py` · Test `tests/ui/test_ventana.py`

**Interfaces:**
- `widgets.Tabla(QTableView)`: método `.cargar(columnas: list[tuple[clave, titulo]], filas: list[dict])` y `.seleccionada() -> dict | None`. Es de solo lectura, con orden por columna.
- Otros widgets: `widgets.Insignia(texto, tono)` y `widgets.TarjetaResultado(dict)`; además `widgets.mostrar_error`, `widgets.confirmar` y `widgets.informar`.
- `LoginDialog(fabrica_sesion, config, cliente_llm, reloj)` con la propiedad `.contexto`.
- `VentanaPrincipal(ctx, fabricas: dict[str, Callable[[Contexto], QWidget]])`.
  - Barra lateral con `secciones_para(ctx)`; crea cada vista de forma perezosa en un `QStackedWidget`.
  - La barra de estado muestra usuario, rol y "IA: conectada / sin clave".
  - Señal `sesion_cerrada`.
- `app.preparar_base(config) -> sessionmaker`: `init_db` + `asegurar_admin_inicial`.
- `app.base_vacia(fabrica) -> bool`.
- `app.main(argv=None, preguntar_demo=None) -> int`.
- [ ] **Step 1: Pruebas (RED)**
  - Inicio de sesión:
    - `test_login_correcto_y_fallido`: un fallo muestra el error en la etiqueta y no cierra el diálogo.
  - Ventana principal:
    - `test_barra_lateral_por_rol[admin|empleado|cliente]`
    - `test_vistas_se_crean_al_visitarlas`
    - `test_barra_estado_muestra_usuario_y_modo_ia`
    - `test_cerrar_sesion_emite_senal`
  - Arranque:
    - `test_preparar_base_vacia_ofrece_demo`: con `preguntar_demo` falso que responde "no", la base queda con el admin y sin equipos.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): login, ventana principal por rol y arranque`

### Task 21 (Tarea 4.4): Equipos, máquina de estados visual y mantenimiento

**Files:** Create `alquiler/ui/logica/catalogo.py`, `alquiler/ui/vistas/__init__.py`, `alquiler/ui/vistas/equipos.py`, `alquiler/ui/vistas/mantenimiento.py` · Test `tests/ui/logica/test_catalogo.py`, `tests/ui/test_vista_equipos.py`

**Interfaces (logica.catalogo):**
- Consultas:
  - `categorias(ctx) -> list[dict(id, nombre)]`
  - `ESTADOS: list[str]`
  - `equipos(ctx, texto=None, estado=None, categoria_id=None) -> list[dict]` con: `id, codigo, nombre, categoria, estado, tarifa (formateada), tarifa_valor, usos`
  - `estados_posibles(estado: str) -> list[str]`: desde `TRANSICIONES`
- Acciones sobre equipos:
  - `crear_equipo(ctx, codigo, nombre, categoria_id, tarifa, fecha_adquisicion) -> int`
  - `actualizar_equipo(ctx, id, **campos)`
  - `dar_de_baja(ctx, id)`
  - `eliminar_equipo(ctx, id)`
  - `crear_categoria(ctx, nombre, usos, dias)`
- Mantenimiento:
  - `mantenimientos_abiertos(ctx)` e `historial_mantenimiento(ctx, equipo_id) -> list[dict]`
  - `abrir_mantenimiento(ctx, equipo_id, tipo: str, descripcion)`
  - `cerrar_mantenimiento(ctx, mantenimiento_id, costo, notas)`
- Vistas:
  - `VistaEquipos(ctx)`: filtros, tabla, `PanelEstados` (5 insignias: la actual resaltada y las alcanzables marcadas) y botones según permiso.
  - `DialogoEquipo`.
  - `VistaMantenimiento(ctx)`.
- [ ] **Step 1: Pruebas (RED)**
  - Lógica de presentación:
    - `test_equipos_filtrados_y_formateados`
    - `test_estados_posibles_refleja_la_tabla`
    - `test_crear_equipo_duplicado_no_escribe` (rollback)
  - Vista de equipos:
    - `test_vista_equipos_cliente_solo_lectura`: sin botones de gestión y solo disponibles.
    - `test_filtro_por_categoria_y_texto`
    - `test_panel_estados_al_seleccionar`
    - `test_nuevo_equipo_desde_dialogo`
    - `test_cancelar_dialogo_no_escribe`
    - `test_error_se_muestra_y_tabla_intacta`
    - `test_empleado_no_ve_eliminar`
  - Vista de mantenimiento:
    - `test_abrir_y_cerrar_mantenimiento_desde_vista`
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): catálogo de equipos con máquina de estados y mantenimiento`

### Task 22 (Tarea 4.5): Clientes, usuarios y perfil

**Files:** Create `alquiler/ui/logica/personas.py`, `alquiler/ui/vistas/clientes.py`, `alquiler/ui/vistas/usuarios.py`, `alquiler/ui/vistas/perfil.py` · Test `tests/ui/logica/test_personas.py`, `tests/ui/test_vistas_personas.py`

**Interfaces (logica.personas):**
- Clientes:
  - `clientes(ctx, texto=None, incluir_inactivos=False)`
  - `clientes_habilitados(ctx) -> list[dict(id, etiqueta)]`: solo activos, `"Nombre — documento"`
  - `registrar_cliente`, `actualizar_cliente` y `desactivar_cliente`
  - `historial_cliente(ctx, cliente_id) -> list[dict]` (con el saldo pendiente)
- Usuarios: `usuarios(ctx)`, `crear_usuario`, `cambiar_estado_usuario` y `restablecer_password`.
- Perfil:
  - `cambiar_password(ctx, actual, nueva)`
  - `mi_cliente(ctx) -> dict | None`
  - `actualizar_mi_contacto(ctx, **campos)`
- [ ] **Step 1: Pruebas (RED)**
  - Lógica de presentación:
    - `test_clientes_habilitados_excluye_inactivos`
    - `test_historial_incluye_saldo`
  - Vistas de clientes y usuarios:
    - `test_vista_clientes_busca_y_desactiva` (con confirmación simulada)
    - `test_vista_usuarios_crea_y_desactiva`
  - Perfil:
    - `test_perfil_cambio_password_error_actual`
    - `test_perfil_cliente_edita_contacto_y_ve_historial`
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): clientes, usuarios y perfil`

### Task 23 (Tarea 4.6): Alquileres, devoluciones, pagos y reservas

**Files:** Create `alquiler/ui/logica/operaciones.py`, `alquiler/ui/vistas/alquileres.py`, `alquiler/ui/vistas/reservas.py` · Test `tests/ui/logica/test_operaciones.py`, `tests/ui/test_vistas_operaciones.py`

**Interfaces (logica.operaciones):**
- `equipos_disponibles(ctx) -> list[dict(id, etiqueta, tarifa_valor)]`.
- `cotizar(inicio, fin, tarifa) -> dict(dias, costo, texto)`: función pura.
- `crear_alquiler(ctx, cliente_id, equipo_id, inicio, fin) -> int`.
- `alquileres(ctx, estado: str | None) -> list[dict]`:
  - columnas `id, cliente, equipo, inicio, fin, estado, situacion ('al día' | 'vencido'), saldo`;
  - por defecto, solo activos.
- Devolución:
  - `previsualizar_devolucion(ctx, alquiler_id, fecha, penalizacion) -> dict(dias_retraso, mora, total, texto)`: usa `liquidar` y `config.factor_mora`;
  - `registrar_devolucion(ctx, alquiler_id, fecha, horas, con_danos, descripcion, penalizacion)`.
- Pagos:
  - `saldo(ctx, alquiler_id) -> int`
  - `registrar_pago(ctx, alquiler_id, monto, metodo: str, concepto: str)`
- Reservas:
  - `reservas(ctx) -> list[dict]` con `situacion ∈ {'pendiente', 'lista para entregar', 'vencida'}`;
  - `entregar_reserva(ctx, id)` y `cancelar_reserva(ctx, id)`.
- Diálogos:
  - `DialogoAlquiler`: combos de clientes habilitados y equipos disponibles; fechas con mínimo hoy; etiqueta de cotización en vivo.
  - `DialogoDevolucion`: fecha con mínimo el inicio; vista previa en vivo.
  - `DialogoPago`: saldo visible; máximo = saldo.
- Vistas: `VistaAlquileres` y `VistaReservas`, con resaltado de las vencidas.
- [ ] **Step 1: Pruebas (RED)**
  - Lógica de presentación:
    - `test_cotizar`
    - `test_previsualizar_devolucion_con_mora`: 2 días con factor 1,5 → mora 75 000.
    - `test_reservas_clasificadas`
  - Diálogo de alquiler:
    - `test_dialogo_alquiler_solo_habilitados_y_cotiza_en_vivo`
    - `test_guardar_dos_veces_crea_un_solo_alquiler`: doble clic (Review Focus 2).
  - Devolución y pago:
    - `test_dialogo_devolucion_vista_previa_y_registro`
    - `test_fecha_devolucion_minima_es_el_inicio`
    - `test_pago_maximo_es_el_saldo`
  - Reservas y vencidos:
    - `test_vista_reservas_entrega_y_cancela`
    - `test_vencida_no_se_entrega_y_se_explica`
    - `test_alquiler_vencido_resaltado`
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): alquileres, devoluciones, pagos y reservas`

### Task 24 (Tarea 4.7): Reportes con gráficos

**Files:** Create `alquiler/ui/logica/reportes.py`, `alquiler/ui/vistas/reportes.py` · Test `tests/ui/test_vista_reportes.py`

**Interfaces:**
- `logica.reportes.generar(ctx, desde, hasta) -> dict`. Claves:
  - `kpis`: total, alquiler, mora, daños y tasa de retraso;
  - `ingresos_mes`: lista de (mes, monto);
  - `uso_equipos`: lista de dict;
  - `uso_categorias`: lista de (categoría, %);
  - `vencidos`: lista de dict.
- `VistaReportes(ctx)`: selector de fechas (por defecto, los últimos 6 meses); "Generar" se ejecuta en segundo plano. Incluye fila de KPIs, `QChart` de barras de ingresos por mes y de uso por categoría, y tablas.
- [ ] **Step 1: Pruebas (RED)**
  - `test_generar_reporte_plano`.
  - `test_vista_reportes_genera_en_segundo_plano`: espera la señal y verifica que el botón se deshabilita durante la tarea y que los gráficos tienen series.
  - `test_periodo_invertido_muestra_error`.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): reportes con gráficos`

### Task 25 (Tarea 4.8): Análisis IA y Consola IA

**Files:** Create `alquiler/ui/logica/ia.py`, `alquiler/ui/vistas/ia.py`, `alquiler/ui/vistas/consola_ia.py` · Test `tests/ui/logica/test_ia.py`, `tests/ui/test_vistas_ia.py`

**Interfaces (logica.ia):**
- Analizadores:
  - `tarjeta(resultado) -> dict`: resumen, valor, confianza, justificación, advertencia y la lista de indicadores como (clave, texto).
  - `demanda(ctx)`, `mantenimiento(ctx)` y `retrasos(ctx) -> list[dict]`. La última incluye una tarjeta global con la tasa.
- Consola:
  - `PREDEFINIDAS: list[(id, titulo)]`
  - `preguntar(ctx, texto) -> dict` y `predefinida(ctx, id) -> dict`
  - `ia_disponible(ctx) -> bool`
- La vista de la consola recibe una respuesta como dict con estas claves: `estado, titulo_estado, pregunta, respuesta, pasos, sql, columnas, filas, advertencia, sugerencias`.
- `VistaAnalisisIA(ctx)`: 3 pestañas; cada una con botón "Analizar" que corre en segundo plano y muestra una `TarjetaResultado` por resultado.
- `VistaConsolaIA(ctx)`:
  - campo de pregunta, botón Consultar (Enter) y los 6 botones de consultas predefinidas;
  - historial (`QListWidget`): un clic vuelve a mostrar la respuesta guardada;
  - panel de respuesta con dos partes y botones de sugerencias;
  - aviso si no hay API;
  - todo corre en segundo plano.
- [ ] **Step 1: Pruebas (RED)** (con `ClienteFalso`)
  - Lógica de presentación: `test_tarjeta_conserva_explicacion`.
  - Análisis IA: `test_analisis_mantenimiento_muestra_tarjetas`.
  - Consola, flujo principal:
    - `test_consola_respuesta_en_dos_partes`
    - `test_consola_historial_reabre_respuesta`
    - `test_consola_predefinida_sin_api`
    - `test_consola_sugerencia_clicable_rellena_pregunta`
  - Consola, casos límite:
    - `test_consola_doble_enter_una_sola_llamada` (Review Focus 2)
    - `test_consola_error_ia_se_muestra_sin_romper`
    - `test_cerrar_con_consulta_en_curso` (Review Focus 1)
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit `feat(ui): análisis y consola de IA con trabajo en segundo plano`

### Task 26 (Tarea 4.9): Integración, rollback de punta a punta y verificación visual

**Files:** Modify `alquiler/ui/app.py` (registro de fábricas de vistas) · Test `tests/ui/test_integracion.py`

- [ ] **Step 1: Pruebas (RED)**
  - Recorrido y base vacía:
    - `test_recorrido_completo_admin_con_datos_demo`: abre cada sección sin errores; el contenido no está vacío donde hay datos.
    - `test_base_vacia_todas_las_vistas_abren` (Review Focus 4)
  - Rollback de punta a punta:
    - `test_rollback_de_punta_a_punta`: un servicio falla a mitad de un `ejecutar` desde una vista; la base no cambia y la siguiente acción funciona.
    - `test_cancelar_dialogos_no_escribe`: alquiler, devolución, pago y equipo.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS
- [ ] **Step 5: Verificación visual**: script en el scratchpad que abre cada sección con datos demo, sin pantalla, y guarda un `grab()` en PNG. Se revisa cada imagen; los problemas visibles se corrigen y se anotan en el registro.
- [ ] **Step 6:** Commit `feat(ui): integración de vistas y pruebas de punta a punta`

## FASE 5 — Documentación, empaquetado y cierre

### Review Focus (Fase 5)

1. **El ejecutable no encuentra las migraciones de Alembic** (archivos `.py` que se cargan desde disco) → el primer arranque congelado falla. Se cubre con `datas` en el spec y la `--autoprueba` del binario. (Tarea 28)
2. **La ruta de la base con espacios o tildes dentro del ejecutable** → `--autoprueba` con `ALQUILER_DB_PATH` en "Nueva carpeta ñ". (Tarea 28)
3. **La documentación menciona archivos que ya no existen** → prueba que verifica cada ruta citada en `PROJECT_INDEX.md`. (Tarea 30)
4. **Una prueba futura llama a la red sin querer** → aislamiento de red automático en toda la suite. (Tarea 27)
5. **El README promete variables o comandos que no existen** → cada variable documentada se contrasta con `config.py` y cada comando se ejecuta. (Tarea 29)

### Task 27 (Tarea 5.1): Aislamiento de red en la suite y modo `--autoprueba`

**Files:** Modify `tests/conftest.py`, `alquiler/ui/app.py` · Test `tests/test_aislamiento_red.py`, `tests/ui/test_autoprueba.py`

**Interfaces:**
- Fixture `autouse` de sesión en `tests/conftest.py`: `socket.socket.connect` y `socket.create_connection` lanzan `RuntimeError("Prueba sin red: …")`.
- `app.autoprueba(config) -> int`, que también se invoca como `python -m alquiler --autoprueba`.
  1. Prepara la base y crea el admin.
  2. Si la base está vacía, carga la demo de 2 meses.
  3. Inicia sesión como admin y recorre las 10 secciones esperando las tareas en segundo plano.
  4. Imprime `AUTOPRUEBA OK: <n> secciones` y devuelve 0; si algo falla, devuelve 1 con el mensaje.
- `app.main(argv)` acepta además `--version`.

- [ ] **Step 1: Pruebas (RED)**
  - `test_la_red_esta_bloqueada_en_las_pruebas`: `socket.create_connection(("example.com", 443))` lanza `RuntimeError`.
  - `test_autoprueba_en_base_nueva(tmp_path)`: con una ruta que tiene espacio y tilde, devuelve 0, imprime "AUTOPRUEBA OK: 10 secciones" y la base queda con datos demo.
  - `test_autoprueba_informa_error`: la fábrica de vistas lanza una excepción, devuelve 1 y el mensaje se imprime.
  - `test_version`: `main(["--version"])` devuelve 0 e imprime la versión.
- [ ] **Step 2:** FAIL · **Step 3:** implementar · **Step 4:** PASS · **Step 5:** Commit

### Task 28 (Tarea 5.2): Empaquetado con PyInstaller

**Files:** Create `AlquilerEquipos.spec`, `scripts/empaquetar.py`, `scripts/empaquetar_windows.bat`.
- El spec es *onedir* (arranque más rápido y menos falsos positivos de antivirus).
- `datas`: `alquiler/migrations/**` incluye `env.py`, `script.py.mako` y `versions/*.py`.
- `hiddenimports`: `alquiler.migrations.env`, módulos de Alembic y `sqlalchemy.dialects.sqlite`.
- Se excluyen los módulos de Qt que no se usan.
- `console=False` en Windows.

- [ ] **Step 1:** construir con `python scripts/empaquetar.py` → `dist/AlquilerEquipos/`.
- [ ] **Step 2: Verificación en entorno limpio**:
  - `env -i HOME=<tmp> PATH=/usr/bin:/bin QT_QPA_PLATFORM=offscreen ALQUILER_DB_PATH="<tmp>/Nueva carpeta ñ/a.db" dist/AlquilerEquipos/AlquilerEquipos --autoprueba` debe imprimir AUTOPRUEBA OK y terminar con código 0;
  - el directorio se ejecuta copiado fuera del repositorio;
  - en el PATH no hay `python` (se comprueba con `command -v python3` en el mismo entorno).
- [ ] **Step 3:** Commit (el spec y los scripts; `dist/` y `build/` siguen en `.gitignore`).

### Task 29 (Tarea 5.3): README completo

Secciones:
- requisitos, instalación (clonar o recuperar desde el bundle, venv, `pip install -r requirements.txt`);
- variables de entorno: todas las de `config.py`, con valor por defecto y validación;
- inicio rápido, flujo del primer arranque y credenciales demo;
- guía de uso por rol, IA explicable y consola;
- privacidad y gobierno de datos;
- pruebas, empaquetado y estructura;
- limitaciones conocidas: los pendientes diferidos del registro.

Verificación: un script que compara las variables `ALQUILER_*`/`ANTHROPIC_*` del README con las de `config.py` y ejecuta `python -m alquiler.seed --help` y `python -m alquiler --version`.

### Task 30 (Tarea 5.4): PROJECT_INDEX.md

**Files:** Create `PROJECT_INDEX.md` · Test `tests/test_documentacion.py`
- Contenido:
  - mapa por capas (Fase 1–4) con la responsabilidad de cada archivo;
  - flujo de una operación y de una consulta de IA;
  - guía de pruebas por módulo.
- `test_rutas_del_indice_existen`: toda ruta entre comillas invertidas que empiece por `alquiler/`, `tests/`, `docs/` o `scripts/` existe.
- `test_todo_modulo_esta_indexado`: cada `.py` de `alquiler/` aparece en el índice.

### Task 31 (Tarea 5.5): Cierre

Comprende:
- suite completa con el aislamiento de red activo;
- revisión final;
- merge a `main`;
- bundle actualizado;
- entrega a la carpeta;
- registro del estado del proyecto en memoria (`/areas/alquiler-equipos.md`).
