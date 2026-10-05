# Sistema Inteligente de Alquiler de Equipos — Especificación de diseño

- **Fecha:** 2026-10-04
- **Autor:** Samuel Moreno (con Claude)
- **Estado:** Aprobado (diseño conversacional aprobado el 2026-10-04)
- **Contexto:** Proyecto académico — Ingeniería de Software, Universidad Cooperativa de Colombia (Pasto)

---

## 1. Objetivo y criterios de éxito

Aplicación de escritorio, local y monousuario, para gestionar el alquiler de equipos (inventario, clientes, contratos, devoluciones, mantenimiento, reportes) con un núcleo analítico que **asiste** decisiones mediante estimaciones explicables.

El proyecto se considera exitoso cuando:

1. Un administrador puede iniciar sesión, registrar equipos y clientes, crear un alquiler, registrar su devolución con retraso y daños, y ver el cambio de estado del equipo y los cargos calculados automáticamente.
2. Cada rol (Administrador, Empleado, Cliente) solo ve y ejecuta lo que le permite la matriz RBAC (§5).
3. Con los datos de demostración, los cuatro módulos de IA producen resultados con **valor + confianza + indicadores + justificación + advertencia** — nunca una certeza sin respaldo.
4. Las consultas en lenguaje natural funcionan con clave API (Text-to-SQL con Claude, solo lectura) y degradan a consultas predefinidas sin ella.
5. La suite `pytest` pasa completa; cada regla de negocio de §4 tiene al menos una prueba que falla si la regla cambia.

## 2. Asunciones explícitas

| # | Asunción | Consecuencia |
|---|----------|--------------|
| A1 | Uso local, un solo puesto, sin red | SQLite en archivo; sin servidor ni concurrencia multiusuario |
| A2 | El rol **Cliente** solo consulta | Ve catálogo, su perfil, historial y alquileres activos; no crea alquileres |
| A3 | "Reservado" = alquiler con `fecha_inicio` futura | La acción **Entregar** pasa el alquiler a `activo` y el equipo a `Alquilado` |
| A4 | Moneda COP en pesos enteros | Montos como `INTEGER`; redondeo *half-up* al peso |
| A5 | Mora = días de retraso × tarifa diaria × `FACTOR_MORA` (1,5 configurable) | Ver §4.4 |
| A6 | Granularidad diaria | Fechas de alquiler como `DATE`, no `DATETIME` |

## 3. Stack y arquitectura

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python ≥ 3.11 |
| UI | PySide6 (Qt 6) + QtCharts |
| ORM / DB | SQLAlchemy 2.x (estilo `Mapped`) + SQLite |
| Migraciones | Alembic |
| Hash de contraseñas | `bcrypt` |
| LLM | SDK oficial `anthropic` ≥ 1.11 (Claude, salida estructurada) |
| Pruebas | `pytest`, `pytest-qt` ≥ 4.5 (UI con `QT_QPA_PLATFORM=offscreen`) |

**Monolito en capas** — cada capa solo depende de las de abajo:

```
ui  ──►  services  ──►  models / db
 │           ▲
 └──►  ai  ──┘ (lee vía Session; funciones puras sobre datos)
```

```
AlquilerEquipos/
├── alquiler/
│   ├── __init__.py
│   ├── __main__.py          # python -m alquiler → lanza la UI
│   ├── config.py            # Config desde variables de entorno
│   ├── db.py                # engine, SessionLocal, PRAGMA foreign_keys, init_db
│   ├── models.py            # 9 entidades + enums
│   ├── auth.py              # hash, autenticación, matriz RBAC
│   ├── errors.py            # ReglaNegocioError, CredencialesInvalidas, PermisoDenegado
│   ├── seed.py              # python -m alquiler.seed → datos demo
│   ├── migrations/          # Alembic (env.py, versions/)
│   ├── services/            # equipos, clientes, alquileres, devoluciones, mantenimiento, reportes
│   ├── ai/                  # resultado, demanda, mantenimiento, retrasos, consultas
│   └── ui/                  # login, main_window, views/
├── tests/                   # espejo de alquiler/
├── docs/
├── alembic.ini
├── pyproject.toml
└── README.md
```

**Contrato de servicios:** funciones de módulo con firma `def operacion(session: Session, actor: Usuario, ...)`. Verifican permiso (`requerir_permiso`), validan reglas, modifican y hacen `session.commit()`. Ante una violación lanzan `ReglaNegocioError` con mensaje en español apto para mostrar al usuario; la sesión se revierte.

## 4. Modelo de datos y reglas de negocio

### 4.1 Enumeraciones (se guardan como texto)

| Enum | Valores |
|------|---------|
| `Rol` | `administrador`, `empleado`, `cliente` |
| `EstadoEquipo` | `Disponible`, `Alquilado`, `En mantenimiento`, `Reservado`, `Fuera de servicio` |
| `EstadoAlquiler` | `reservado`, `activo`, `finalizado`, `cancelado` |
| `TipoMantenimiento` | `preventivo`, `correctivo` |
| `ConceptoPago` | `alquiler`, `mora`, `danos` |
| `MetodoPago` | `efectivo`, `tarjeta`, `transferencia` |
| `TipoRecomendacion` | `mantenimiento`, `demanda`, `retraso` |
| `EstadoRecomendacion` | `pendiente`, `atendida`, `descartada` |
| `Nivel` (prioridad/confianza) | `baja`, `media`, `alta` |

### 4.2 Entidades

| Entidad | Campos principales | Restricciones |
|---------|-------------------|---------------|
| **Usuario** | `id, username, password_hash, nombre_completo, rol, activo, cliente_id?, creado_en` | `username` único; `cliente_id` único, FK→Cliente; rol `cliente` ⇔ `cliente_id` no nulo (validado en `auth.crear_usuario`) |
| **Cliente** | `id, documento, nombre, email?, telefono, direccion?, fecha_registro, activo` | `documento` único |
| **Categoria** | `id, nombre, descripcion?, intervalo_mant_usos, intervalo_mant_dias` | `nombre` único; intervalos > 0 (por defecto 20 usos / 90 días) |
| **Equipo** | `id, codigo, nombre, descripcion?, categoria_id, estado, tarifa_diaria, usos_acumulados, horas_uso_acumuladas, fecha_adquisicion` | `codigo` único; `tarifa_diaria > 0`; contadores ≥ 0; estado por defecto `Disponible` |
| **Alquiler** | `id, cliente_id, equipo_id, registrado_por_id?, fecha_inicio, fecha_fin_prevista, tarifa_diaria, costo_estimado, estado, creado_en` | `fecha_fin_prevista ≥ fecha_inicio`; `tarifa_diaria` es una copia al momento del contrato |
| **Devolucion** | `id, alquiler_id, fecha_devolucion, dias_retraso, recargo_mora, horas_uso, con_danos, descripcion_danos?, penalizacion_danos, total, registrado_por_id?` | `alquiler_id` único (1:1); montos ≥ 0 |
| **Pago** | `id, alquiler_id, monto, fecha, metodo, concepto` | `monto > 0`; N:1 con Alquiler |
| **Mantenimiento** | `id, equipo_id, tipo, fecha_inicio, fecha_fin?, descripcion, costo, usos_al_momento` | `costo ≥ 0`; `usos_al_momento` = `equipo.usos_acumulados` al abrir (base de "usos desde el último servicio"); `fecha_fin` nulo = en curso |
| **RecomendacionIA** | `id, tipo, equipo_id?, cliente_id?, categoria_id?, puntaje, prioridad, confianza, resumen, justificacion (JSON lista), datos_respaldo (JSON), estado, creada_en` | `0 ≤ puntaje ≤ 100` |

Relaciones: Categoria 1–N Equipo · Cliente 1–N Alquiler · Equipo 1–N Alquiler · Alquiler 1–1 Devolucion · Alquiler 1–N Pago · Equipo 1–N Mantenimiento · Usuario 0..1–1 Cliente · Usuario 1–N Alquiler (registrado_por). SQLite con `PRAGMA foreign_keys=ON` en cada conexión. Las eliminaciones son lógicas (`activo=False`) para Cliente y Usuario; un Equipo con alquileres no se elimina, se pasa a `Fuera de servicio`.

### 4.3 Máquina de estados del Equipo

| Desde \ Hacia | Disponible | Alquilado | Reservado | En mantenimiento | Fuera de servicio |
|---|---|---|---|---|---|
| **Disponible** | — | ✔ | ✔ | ✔ | ✔ |
| **Reservado** | ✔ (cancelación) | ✔ (entrega) | — | ✘ | ✘ |
| **Alquilado** | ✔ (devolución) | — | ✘ | ✔ (devolución con daños) | ✘ |
| **En mantenimiento** | ✔ (cierre) | ✘ | ✘ | — | ✔ |
| **Fuera de servicio** | ✘ | ✘ | ✘ | ✔ (rehabilitación) | — |

Cualquier transición ✘ lanza `ReglaNegocioError("Transición no permitida: X → Y")`.

### 4.4 Cálculos

- `dias_contratados = max(1, (fecha_fin_prevista − fecha_inicio).days)`
- `costo_estimado = dias_contratados × tarifa_diaria`
- `dias_retraso = max(0, (fecha_devolucion − fecha_fin_prevista).days)`
- `recargo_mora = round_half_up(dias_retraso × tarifa_diaria × FACTOR_MORA)`
- `total = costo_estimado + recargo_mora + penalizacion_danos`
- Al devolver: `equipo.usos_acumulados += 1`, `equipo.horas_uso_acumuladas += horas_uso`.
- Devolución con daños ⇒ equipo `En mantenimiento` + `Mantenimiento` correctivo abierto automáticamente.
- Crear alquiler exige equipo `Disponible`; si `fecha_inicio > hoy` ⇒ alquiler `reservado` y equipo `Reservado`, si no ⇒ `activo` y `Alquilado`.
- No se permite registrar un alquiler a un cliente inactivo.

## 5. Autenticación y RBAC

- Contraseñas con `bcrypt` (mínimo 8 caracteres). Nunca se guardan ni se registran en texto plano.
- `autenticar(session, username, password)` devuelve el `Usuario` o lanza `CredencialesInvalidas` con un mensaje genérico (no revela si falló el usuario o la contraseña). Usuarios inactivos no pueden entrar.
- `asegurar_admin_inicial(session)` crea `admin` si no existe ningún administrador; la contraseña viene de `ALQUILER_ADMIN_PASSWORD` (por defecto `admin1234`, documentado en el README como credencial de demo).

| Permiso | Admin | Empleado | Cliente |
|---------|:-----:|:--------:|:-------:|
| `catalogo.ver` | ✔ | ✔ | ✔ |
| `perfil.propio` | ✔ | ✔ | ✔ |
| `equipos.gestionar` | ✔ | ✔ | |
| `equipos.eliminar` | ✔ | | |
| `clientes.ver` / `clientes.gestionar` | ✔ | ✔ | |
| `alquileres.ver` / `alquileres.gestionar` | ✔ | ✔ | |
| `devoluciones.registrar` | ✔ | ✔ | |
| `mantenimiento.ver` / `mantenimiento.gestionar` | ✔ | ✔ | |
| `ia.ver` (alertas y análisis) | ✔ | ✔ | |
| `ia.consultas` (lenguaje natural) | ✔ | | |
| `reportes.ver` | ✔ | | |
| `usuarios.gestionar` | ✔ | | |

`tiene_permiso(usuario, permiso)` es una consulta a esta tabla; `requerir_permiso` lanza `PermisoDenegado`. La UI oculta lo no permitido, pero **la autorización real vive en los servicios**.

## 6. Módulo de IA (explicable)

Todas las funciones devuelven:

```python
@dataclass(frozen=True)
class Resultado:
    resumen: str               # frase corta, redactada como estimación
    valor: float | None        # número principal (puntaje, demanda esperada, tasa)
    confianza: Nivel           # baja / media / alta, según cantidad y dispersión de datos
    indicadores: dict          # cifras de respaldo (n, tasas, contribuciones…)
    justificacion: list[str]   # pasos legibles del razonamiento
    advertencia: str           # límites de la estimación
```

La UI siempre muestra la etiqueta **"Estimación"**, la confianza y un desplegable con indicadores y justificación. Las recomendaciones de mantenimiento y retraso se persisten en `RecomendacionIA`.

### 6.1 Predicción de demanda (por categoría)
1. Serie mensual de alquileres iniciados por categoría.
2. Índice estacional `I_m = media(mes m) / media global` (si hay ≥ 12 meses; si no, `I_m = 1`).
3. Pronóstico del próximo mes = media de los últimos 3 meses desestacionalizados × `I_{mes siguiente}`.
4. Rango = pronóstico ± 1,28 × desviación de residuos (~80 %).
5. Picos: meses con `I_m ≥ 1,25`.
6. Confianza: `baja` < 6 meses de datos; `media` 6–11 o coeficiente de variación de residuos > 0,5; `alta` en otro caso.

### 6.2 Recomendador de mantenimiento preventivo (por equipo)
Factores normalizados en [0, 1] (recortados a 1):

| Factor | Cálculo | Peso |
|--------|---------|-----:|
| Usos desde el último servicio | `(usos_acumulados − usos_al_momento_último) / intervalo_mant_usos` | 35 % |
| Tiempo desde el último servicio | `días / intervalo_mant_dias` (sin servicio: desde `fecha_adquisicion`) | 25 % |
| Intensidad de uso reciente | alquileres en 30 días / máximo de la categoría | 15 % |
| Historial de fallas | correctivos en 12 meses / 3 | 25 % |

`puntaje = 100 × Σ peso·factor`. Prioridad `alta` ≥ 75, `media` ≥ 50; por debajo no genera alerta. La justificación lista cada factor con su valor bruto y su aporte en puntos. Equipos `Fuera de servicio` o ya `En mantenimiento` se excluyen. Confianza `baja` si el equipo tiene < 3 alquileres registrados.

### 6.3 Análisis de retrasos
- Tasa global `p` = devoluciones con retraso / devoluciones.
- Tasa suavizada por cliente: `(r + k·p) / (n + k)`, con `k = 5` (evita señalar a alguien por un solo retraso).
- Igual por categoría de equipo.
- Se marca un cliente si su tasa suavizada > 2·p **y** n ≥ 3. Se reportan `n`, retrasos, tasa observada, tasa suavizada, días promedio de retraso y la categoría más asociada.
- Confianza por `n`: < 5 baja, 5–14 media, ≥ 15 alta.

### 6.4 Consultas en lenguaje natural (Text-to-SQL) — revisado 2026-10-04 (Fase 3)

> **Revisado — Fase 6:** el proveedor pasa de Anthropic (Claude) a **Groq** (`ClienteGroq`,
> modelo por defecto `openai/gpt-oss-20b`, `response_format` `json_schema` estricto). El protocolo
> `ClienteLLM`, los prompts, las tres barreras de seguridad y el flujo de dos llamadas no cambian.
> Detalle: `2026-10-04-mejoras-ui-groq-design.md` §4.

**Cliente del modelo.** SDK oficial `anthropic` (≥ 1.11).
- Modelo por defecto: `claude-sonnet-5-5`, verificado el 2026-10-04 en platform.claude.com/docs/en/models/overview como el de mejor equilibrio velocidad/inteligencia, a $2/$10 por MTok.
- Salida estructurada con `output_config.format = {"type": "json_schema", ...}`, sin cabecera beta.
- `timeout` (por defecto 30 s) y `max_retries` (por defecto 2, con backoff exponencial del SDK ante 429/5xx/errores de red) son configurables (§9).
- Los errores del SDK se traducen a `ErrorIA` con un mensaje en español; la aplicación nunca se cae por un fallo del modelo.

**Paso 1 — Generación.**
- El prompt de sistema contiene:
  - el esquema, generado desde `Base.metadata` para que no se desincronice: tablas, columnas, tipos y FK; excluye `usuario` y `alembic_version`;
  - los valores exactos de los enums;
  - reglas de negocio (montos en pesos enteros, fechas ISO, estados del equipo, mora, alquiler "activo");
  - restricciones: solo `SELECT`/`WITH`, una sentencia, sin datos inventados;
  - la fecha de hoy.
- El modelo responde, con un JSON validado por esquema: `{"tipo": "sql"|"aclaracion"|"no_resoluble", "sql", "pasos": [..], "mensaje", "sugerencias": [..]}`.

**Paso 2 — Seguridad (defensa en profundidad).** La consulta se rechaza antes de tocar la base si no pasa estas tres barreras:
1. **Validador estático** (`validar_sql`) sobre el texto sin comentarios ni literales:
   - una sola sentencia que empiece por `SELECT` o `WITH`;
   - ninguna palabra prohibida: `INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE` (salvo la función `replace(`), `ATTACH, DETACH, PRAGMA, VACUUM, REINDEX, ANALYZE, TRUNCATE, BEGIN, COMMIT, ROLLBACK, SAVEPOINT, RELEASE`;
   - ni `load_extension`, ni referencias a `usuario`/`password_hash`.
2. **Conexión de solo lectura:** URI `file:…?mode=ro` construida con `Path.as_uri()` (soporta espacios y tildes en la ruta), más `PRAGMA query_only=ON`.
3. **`set_authorizer`:** solo permite `SELECT`, `READ` (excepto `usuario` y `alembic_version`), `FUNCTION` (excepto `load_extension`) y `RECURSIVE`.

**Ejecución.**
- Se usa `fetchmany(201)`: se devuelven como máximo 200 filas y se marca `truncado`.
- Tiempo máximo de 3 s con `set_progress_handler`.
- Si el SQL falla en validación o en ejecución, se hace **un único intento de corrección**: se devuelve el error al modelo. Si vuelve a fallar, la respuesta tiene estado `error` y se muestra el SQL.

**Paso 3 — Explicabilidad.** Se devuelve `RespuestaConsulta(estado, pregunta, respuesta, pasos, sql, columnas, filas, truncado, advertencia, sugerencias)`, con este protocolo:

| Estado | Cuándo | Contenido |
|---|---|---|
| `ok` | hay filas | **(1) respuesta directa** redactada por el modelo en una segunda llamada, solo a partir de las primeras 50 filas; **(2) pasos** de qué tablas, filtros y por qué |
| `sin_datos` | la consulta no devuelve filas | mensaje determinista (sin segunda llamada) + pasos + sugerencia de reformular |
| `aclaracion` | la pregunta es ambigua | pregunta de aclaración + sugerencias de reformulación |
| `no_resoluble` | los datos no permiten responder | motivo + sugerencias |
| `sin_api` | sin `ANTHROPIC_API_KEY` | aviso + las 6 consultas predefinidas |
| `error` | fallo del modelo, de la red o del SQL tras la corrección | mensaje claro; nunca un traceback |

- Advertencia fija: "Respuesta generada por IA a partir de los datos consultados: verifique el SQL y las cifras antes de tomar decisiones."
- Si el resultado está truncado, la advertencia lo indica.
- Las preguntas vacías o de más de 500 caracteres se rechazan sin llamar a la API.

**Consultas predefinidas** (siempre disponibles, pasan por el mismo ejecutor seguro):
- top equipos del mes;
- ingresos del mes;
- alquileres activos;
- clientes con más retrasos;
- equipos a revisar (usa §6.2);
- equipos por estado.

**Privacidad.** Los nombres de clientes de las filas resultantes se envían a la API en el paso 3. El README lo documenta; la tabla `usuario` nunca se expone.

## 7. Reportes
Ingresos por período (suma de `Pago` por concepto), uso de flota (% de días alquilados por equipo/categoría en el período), morosidad (alquileres vencidos sin devolver + recargos de mora cobrados). Gráficos con QtCharts.

## 8. Interfaz — revisado 2026-10-04 (Fase 4)

**Arquitectura**

- **Lógica de presentación sin Qt.** `alquiler/ui/logica/` es la única capa de la interfaz que importa servicios, IA, modelos o SQLAlchemy. Devuelve datos planos (listas de dict, dataclasses).
- **Vistas Qt.** `alquiler/ui/vistas/`, `login.py`, `ventana.py`, `widgets.py` y `trabajador.py` solo importan PySide6, la biblioteca estándar, `alquiler.ui.*` y `alquiler.errors`. Una prueba de arquitectura lo verifica.
- **`Contexto.ejecutar(fn)`:**
  - abre una sesión nueva por operación y recarga al usuario;
  - hace rollback ante cualquier excepción y siempre cierra la sesión;
  - si el usuario fue desactivado mientras tenía la sesión abierta, falla con un mensaje claro.
- **Concurrencia.**
  - Pasan por `QThreadPool` + `QRunnable`: las consultas a Claude, las consultas predefinidas, los analizadores y los reportes.
  - Los resultados vuelven al hilo de la interfaz mediante señales.
  - Mientras una tarea está en curso, su botón queda deshabilitado (protege del doble clic).
  - Al cerrar la ventana se esperan las tareas pendientes.
- **Errores.** `ReglaNegocioError` se muestra tal cual; cualquier otro error se muestra como "Error inesperado: …". Nunca se muestra un traceback.

**Navegación.**
- Inicio de sesión → `QMainWindow` con una barra lateral que solo muestra las secciones permitidas (tabla RBAC §5).
- Secciones: Equipos (catálogo), Mantenimiento, Clientes, Alquileres, Reservas, Reportes, Análisis IA, Consola IA, Usuarios y Mi perfil.
- Las vistas se crean al visitarlas por primera vez. Hay botón "Cerrar sesión".

**Módulos**

| Sección | Contenido |
|---|---|
| Equipos | Catálogo con filtros (categoría, estado, texto) y estado coloreado. Panel con la **máquina de estados visual**: estado actual y transiciones posibles. Crear, editar, dar de baja y eliminar (este último solo admin). Los clientes ven el catálogo en solo lectura. |
| Mantenimiento | Mantenimientos abiertos e historial por equipo. Abrir preventivo/correctivo y cerrar con costo y notas. |
| Clientes | Búsqueda (incluye inactivos), alta, edición, desactivación e historial. |
| Alquileres | Listado por estado. **Nuevo alquiler** solo ofrece clientes activos y equipos disponibles, con vista previa del costo en vivo. **Devolución** con vista previa en vivo de retraso, mora y total. **Pago** con el saldo pendiente visible. |
| Reservas | Reservas no entregadas, clasificadas como *pendiente* (inicia en el futuro), *lista para entregar* o *vencida*. Acciones: entregar y cancelar. |
| Reportes | Rango de fechas, indicadores de ingresos, gráfico de ingresos por mes, uso de flota por equipo y categoría, morosidad (en segundo plano). |
| Análisis IA | Pestañas Demanda / Mantenimiento / Retrasos con tarjetas: resumen, insignia "Estimación", confianza, justificación e indicadores desplegables. |
| Consola IA | Pregunta libre, 6 botones de consultas predefinidas, historial de la sesión (clic para volver a ver) y respuesta en dos partes: **respuesta directa** y **cómo se obtuvo** (pasos). También muestra el SQL, la tabla de datos, la advertencia y las sugerencias clicables. Sin API muestra un aviso. |
| Usuarios | Solo admin: alta, activar/desactivar y restablecer contraseña. |
| Mi perfil | Cambio de contraseña. El cliente también edita su contacto y ve su historial. |

**Primer arranque.** `python -m alquiler`:
1. migra la base y crea el admin;
2. si la base no tiene equipos, ofrece cargar los datos de demostración;
3. muestra el inicio de sesión.

**Datos de demostración.** `alquiler/seed.py`, también disponible como `python -m alquiler.seed`.
- Simulación determinista (semilla 42) de 18 meses día por día, **a través de los servicios reales**, para que cumplan todas las reglas de negocio.
- Contenido:
  - estacionalidad: picos en diciembre y a mitad de año para andamios;
  - clientes puntuales y algunos morosos, y clientes inactivos;
  - daños que generan correctivos, y preventivos que se realizan solo a veces, para que haya alertas;
  - pagos parciales, alquileres activos y vencidos;
  - reservas pendientes, listas para entregar y vencidas;
  - equipos en mantenimiento y fuera de servicio.
- Usuarios de demo: `admin` (contraseña de la configuración), `empleado` / `empleado123` y `cliente` / `cliente123`.

## 9. Configuración (variables de entorno) — revisado Fase 6

Los valores pueden venir de variables de entorno o del archivo `alquiler.env` junto al programa
(el entorno gana). Ver `2026-10-04-mejoras-ui-groq-design.md` §4.2–§4.3.

| Variable | Por defecto |
|----------|-------------|
| `ALQUILER_DB_PATH` | `~/.alquiler_equipos/alquiler.db` |
| `ALQUILER_ADMIN_PASSWORD` | `admin1234` |
| `ALQUILER_FACTOR_MORA` | `1.5` |
| `GROQ_API_KEY` | — (sin ella, modo consultas predefinidas) |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `GROQ_TIMEOUT` | `30` (segundos por llamada) |
| `GROQ_MAX_RETRIES` | `2` |

## 10. Estrategia de pruebas
- `pytest` con SQLite en memoria (`StaticPool`) y fixture de sesión por prueba.
- **Fase 1:** restricciones de modelo (unicidad, FK activas, CHECK), migración Alembic = modelos (`compare_metadata` sin diferencias), hash/autenticación y matriz RBAC completa.
- **Fase 2:** cada regla de §4.3–4.4, incluidos casos límite (mismo día, retraso 0, transición inválida).
- **Fase 3:** datos sintéticos con patrón conocido (pico en diciembre, equipo desgastado, cliente moroso) y aserciones sobre el resultado **y** sobre la presencia de justificación/confianza; validador SQL con intentos de `DELETE`, `ATTACH`, `PRAGMA`, varias sentencias y lectura de `usuario`; LLM falso.
- **Fase 4:** pruebas de humo con `pytest-qt` (login por rol, navegación visible por permisos).

## 11. Fases
1. Estructura, configuración, DB, modelos, Alembic, autenticación/RBAC.
2. Servicios de dominio + pruebas.
3. Motor de IA + pruebas.
4. UI PySide6 + integración + semilla de datos demo.
5. Suite completa, README, índice del proyecto (`PROJECT_INDEX.md`) y registro en memoria.

## 12. Fuera de alcance
Multiusuario en red, facturación electrónica, notificaciones por correo, instalador (solo instrucciones de PyInstaller en el README), internacionalización.
