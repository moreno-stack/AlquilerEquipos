# Fase 6 — Tema "Taller industrial", Inicio y Groq — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:**

- Sustituir Anthropic por Groq, de modo que el usuario solo tenga que pegar su clave.
- Dar a la interfaz la paleta "Taller industrial".
- Añadir una pantalla de Inicio con indicadores por rol.

**Arquitectura:**

- **Groq:** entra detrás del protocolo existente `ClienteLLM`. Nada aguas abajo cambia.
- **Configuración:** `config.py` aprende a leer `alquiler.env`.
- **Tema:** la paleta vive en `ui/tema.py`, que genera la QSS. Ningún otro archivo de `ui/` escribe colores.
- **Inicio:** es una sección más. Su lógica sin Qt (`logica/inicio.py`) solo compone servicios existentes.

**Stack:** Python 3.11+, PySide6 6.11 (QtWidgets/QtCharts), SDK `groq>=1.7` (usa `httpx`), pytest y pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-04-mejoras-ui-groq-design.md` (contiene los tokens de color, los textos de error y las reglas de `alquiler.env`; léala junto al plan).

## Restricciones globales

- Toda la interfaz y los mensajes van en español. Los mensajes de error se copian literalmente de la spec §4.1.
- Modelo por defecto `openai/gpt-oss-20b`. Variables: `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_TIMEOUT` (por defecto 30, > 0) y `GROQ_MAX_RETRIES` (por defecto 2, entre 0 y 10).
- `response_format` usa `json_schema` con `strict: True`, `temperature=0` y `max_completion_tokens=4096`.
- Ninguna prueba toca la red: el fixture `sin_red` de `tests/conftest.py` sigue activo.
- La regla AST de `tests/ui/test_arquitectura.py` no cambia. Las vistas solo importan `logica`, `widgets`, `tema` y `trabajador`.
- No se tocan modelos, servicios ni migraciones.
- `PROJECT_INDEX.md` debe listar todo módulo y prueba nuevos (`tests/test_documentacion.py` lo exige).
- Cada tarea termina con la suite completa en verde: `QT_QPA_PLATFORM=offscreen pytest -q`.
- Los mensajes de commit terminan con las líneas `Co-Authored-By` y `Claude-Session` de la sesión.
- El progreso se registra en `.superpowers/sdd/2026-10-04-alquiler-equipos/progress.md`.

## Puntos a vigilar en la revisión

1. **`alquiler.env` editado en el Bloc de notas de Windows** (BOM + finales CRLF + comillas) → la clave se lee igual. La prueba va en la Tarea 1.
2. **Variable de entorno `GROQ_API_KEY` definida pero vacía** → no anula la clave del archivo; se usa la del archivo. La prueba va en la Tarea 1.
3. **Abrir Inicio muchas veces** → no crea registros `RecomendacionIA` (se llama con `persistir=False`). La prueba va en la Tarea 6.
4. **Base recién creada sin equipos ni alquileres** → Inicio muestra ceros y "Sin equipos registrados", sin división por cero. Las pruebas van en las Tareas 5 y 7.
5. **Groq devuelve `content=None` (rechazo) o un JSON que no es objeto** → `ErrorIA` "formato inesperado", nunca una excepción cruda. La prueba va en la Tarea 2.

---

### Tarea 1: Configuración Groq y archivo `alquiler.env`

**Archivos:**
- Modificar: `alquiler/config.py`
- Crear: `alquiler.env.ejemplo`
- Modificar: `.gitignore` (añadir `alquiler.env`)
- Pruebas: `tests/test_config.py` (se reescriben las de `ANTHROPIC_*`)

**Interfaces:**
- Produce:
  - `MODELO_POR_DEFECTO = "openai/gpt-oss-20b"`.
  - `Config(db_path, admin_password, factor_mora, groq_api_key: str | None, groq_model: str, groq_timeout: float, groq_max_retries: int, origen_clave: str | None)`, donde `origen_clave` vale `"entorno"`, `"archivo"` o `None`.
  - `Config.__repr__` enmascara la clave como `'…' + últimos 4`.
  - `leer_archivo_env(ruta: Path) -> dict[str, str]`.
  - `buscar_archivo_env() -> Path | None`.
  - `cargar_config(env: Mapping | None = None, archivo: Path | None | Literal[False] = None) -> Config`: `None` busca el archivo y `False` no usa ninguno.

- [ ] **Paso 1: Escribir las pruebas que fallan** en `tests/test_config.py`:
  - `test_valores_por_defecto_groq`: `cargar_config({}, archivo=False)` da `groq_api_key is None`, `groq_model == "openai/gpt-oss-20b"`, `groq_timeout == 30.0`, `groq_max_retries == 2` y `origen_clave is None`.
  - `test_variables_groq` (`GROQ_TIMEOUT="12,5"` → 12.5) y las validaciones parametrizadas `match="GROQ_TIMEOUT"` / `match="GROQ_MAX_RETRIES"`, con los mismos valores inválidos que las pruebas actuales.
  - `test_archivo_env_formato(tmp_path)`: el archivo se escribe en bytes como `b'\xef\xbb\xbf# comentario\r\nGROQ_API_KEY = "gsk_abc123"\r\n\r\nOTRA=1\r\nlinea sin igual\r\nGROQ_MODEL=\'llama-3.3-70b-versatile\'\r\n'`. El resultado debe ser `leer_archivo_env(r) == {"GROQ_API_KEY": "gsk_abc123", "GROQ_MODEL": "llama-3.3-70b-versatile"}`.
  - `test_archivo_aporta_clave`: `cargar_config({}, archivo=r)` da `groq_api_key == "gsk_abc123"` y `origen_clave == "archivo"`.
  - `test_entorno_gana_al_archivo`: con `{"GROQ_API_KEY": "gsk_env"}` y el archivo, la clave es `"gsk_env"` y el origen `"entorno"`.
  - `test_entorno_vacio_no_anula_archivo`: con `{"GROQ_API_KEY": "  "}` y el archivo, la clave es `"gsk_abc123"` y el origen `"archivo"`.
  - `test_archivo_aporta_variables_alquiler`: `ALQUILER_FACTOR_MORA=2` en el archivo da `factor_mora == 2.0`.
  - `test_repr_enmascara_clave`: `"gsk_abc123" not in repr(cfg)` y `"…c123" in repr(cfg)`.
  - `test_buscar_archivo_env`: `buscar_archivo_env()` devuelve la ruta junto al proyecto si existe. Monkeypatch de `config._CARPETAS_ENV` a `[tmp_path / "a", tmp_path / "b"]`; solo existe `b/alquiler.env` → se devuelve esa ruta. Sin ninguno → `None`.
  - Las pruebas existentes que llaman a `cargar_config({...})` deben pasar `archivo=False`, para no depender del disco del desarrollador.

- [ ] **Paso 2: Ejecutar** `pytest tests/test_config.py -q`. Se espera que FALLE (`groq_api_key` no existe).

- [ ] **Paso 3: Implementar** en `alquiler/config.py`:
  - `_CARPETAS_ENV`: la carpeta de `sys.executable` si `getattr(sys, "frozen", False)`, si no la raíz del proyecto (`Path(__file__).resolve().parent.parent`); después `Path.home() / ".alquiler_equipos"`.
  - **Combinación:** `{**archivo_filtrado, **{k: v for k, v in env.items() if v.strip()}}`. Las claves del archivo se filtran por los prefijos `GROQ_` y `ALQUILER_`.
  - **Origen:** `"entorno"` si la clave vino de `env` no vacío, `"archivo"` si vino del archivo.
  - **Lectura:** `encoding="utf-8-sig"` y `splitlines()`. Una línea sin `=` emite `warnings.warn`.
  - **Mensajes de validación:** con los nombres `GROQ_TIMEOUT` y `GROQ_MAX_RETRIES`.
  - **`__repr__`:** se define explícitamente; `dataclass(frozen=True, repr=False)`.

- [ ] **Paso 4: Crear `alquiler.env.ejemplo`.** Lleva comentarios en español:
  - qué es el archivo;
  - "copie este archivo como alquiler.env";
  - obtener la clave en https://console.groq.com/keys;
  - "no comparta este archivo".

  Contenido: `GROQ_API_KEY=`, `# GROQ_MODEL=openai/gpt-oss-20b`, `# GROQ_TIMEOUT=30` y `# GROQ_MAX_RETRIES=2`. Añadir `alquiler.env` a `.gitignore`.

- [ ] **Paso 5: Ejecutar** `pytest tests/test_config.py -q` → PASA. (El resto de la suite puede fallar en `llm.py` hasta la Tarea 2; ambas tareas se fusionan en un solo commit si hace falta para mantener la suite verde.)

---

### Tarea 2: `ClienteGroq` sustituye a `ClienteClaude`

**Archivos:**
- Modificar: `alquiler/ai/llm.py`, `alquiler/ai/consultas.py:179` (texto `sin_api`), `alquiler/ui/vistas/consola_ia.py:70` (`aviso_sin_api`), `requirements.txt`, `pyproject.toml`
- Pruebas: `tests/ai/test_llm.py` (reescrita), `tests/ai/test_consultas.py:107`, `tests/ui/test_vistas_ia.py` (texto del aviso), docstrings de `tests/test_aislamiento_red.py` y `tests/ui/conftest.py`

**Interfaces:**
- Consume: `Config.groq_*` (Tarea 1).
- Produce:
  - `ClienteGroq(api_key: str, modelo: str, timeout: float, max_retries: int, http_client: httpx.Client | None = None)` con `.modelo` y `.generar_json(sistema, mensajes, esquema) -> dict`.
  - `crear_cliente(config) -> ClienteLLM | None`.
  - `ErrorIA` y `ClienteLLM` sin cambios.

- [ ] **Paso 1:** `pip install "groq>=1.7" --break-system-packages`. En `requirements.txt` y `pyproject.toml`, sustituir `anthropic>=1.11` por `groq>=1.7`.

- [ ] **Paso 2: Escribir las pruebas que fallan** en `tests/ai/test_llm.py`, con un ayudante `cliente_con(manejador)` que construye `ClienteGroq("gsk_test", "openai/gpt-oss-20b", 5, 0, http_client=httpx.Client(transport=httpx.MockTransport(manejador)))`. Las respuestas simuladas siguen el formato OpenAI: `{"id":"x","object":"chat.completion","created":0,"model":"m","choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"{\"a\":1}"}}]}`.
  - `test_peticion_estructurada`: URL que termina en `/openai/v1/chat/completions`; cabecera `authorization == "Bearer gsk_test"`; en el cuerpo, `model`, `messages[0] == {"role":"system","content":"SYS"}`, `messages[1:] == mensajes`, `response_format["type"] == "json_schema"`, `response_format["json_schema"]["strict"] is True`, `response_format["json_schema"]["schema"] == esquema`, `temperature == 0` y `max_completion_tokens == 4096`. Devuelve `{"a": 1}`.
  - `test_respuesta_truncada`: `finish_reason "length"` → `ErrorIA` con `match="incompleta"`.
  - `test_contenido_invalido`, parametrizada sobre `content` igual a `None`, `"no json"` y `"[1,2]"` → `ErrorIA` con `match="formato inesperado"`.
  - `test_traduccion_de_errores`, parametrizada sobre el estado HTTP y el mensaje esperado de spec §4.1: 401 → "clave de Groq no es válida", 403 → idem, 429 → "límite de uso de Groq", 404 → "GROQ_MODEL", 400 → "Groq rechazó", 503 → "código 503". Cuerpo de error: `{"error":{"message":"x","type":"t"}}`.
  - `test_sin_conexion`: el manejador lanza `httpx.ConnectError("x")` → `match="Sin conexión con Groq"`.
  - `test_la_clave_no_aparece_en_errores`: para 401, `"gsk_test" not in str(error)`.
  - `test_esquemas_compatibles_con_modo_estricto`: en `prompts.ESQUEMA_GENERACION` y `prompts.ESQUEMA_RESPUESTA`, `set(required) == set(properties)` y `additionalProperties is False`.
  - `test_crear_cliente`: sin clave da `None`; con clave da un `ClienteGroq` con `.modelo == cfg.groq_model`.
  - En `test_consultas.py:107` el texto esperado pasa a `"GROQ_API_KEY"`. En `test_vistas_ia.py` se espera `"GROQ_API_KEY"` y `"alquiler.env"` en el texto de `aviso_sin_api`.

- [ ] **Paso 3: Ejecutar** `pytest tests/ai tests/ui/test_vistas_ia.py -q` → FALLA.

- [ ] **Paso 4: Implementar** `ClienteGroq` con `groq.Groq(api_key=, timeout=, max_retries=, http_client=)` y `chat.completions.create(...)`, según la spec §4.1.
  - El orden de los `except` importa (las subclases van primero): `AuthenticationError`/`PermissionDeniedError`, `RateLimitError`, `NotFoundError`, `BadRequestError`, `APIConnectionError` y `APIStatusError`.
  - Todo `raise ... from None`.
  - Texto `sin_api` de consultas: `"La IA no está configurada (falta GROQ_API_KEY en alquiler.env o en el entorno). Use las consultas rápidas."`.
  - `aviso_sin_api`: `"Sin GROQ_API_KEY: la IA no está configurada (agregue la clave en alquiler.env). Las consultas rápidas sí funcionan."`.
  - Sustituir "Claude" y "Anthropic" en los docstrings.

- [ ] **Paso 5: Ejecutar** la suite completa → PASA. Comprobar que no queda nada: `grep -rniI "anthropic\|claude" alquiler tests` debe salir vacío.

- [ ] **Paso 6: Commit** de las Tareas 1 y 2: `feat: proveedor de IA Groq y archivo alquiler.env`.

---

### Tarea 3: Comando `--probar-ia`

**Archivos:**
- Modificar: `alquiler/ui/app.py` (`main`)
- Crear: `alquiler/probar_ia.py`
- Pruebas: `tests/test_probar_ia.py`

**Interfaces:**
- Consume: `cargar_config`, `crear_cliente`, `ErrorIA`.
- Produce: `probar_ia(config: Config, crear=crear_cliente, imprimir=print) -> int`. Devuelve 0 si la IA responde, 1 ante un `ErrorIA` y 2 sin clave. `main(["--probar-ia"])` devuelve `probar_ia(cargar_config())`.

- [ ] **Paso 1: Escribir las pruebas que fallan**, con un `ClienteFalso` local cuyo `modelo` es `"openai/gpt-oss-20b"`:
  - `test_sin_clave`: devuelve 2 y la salida contiene `"alquiler.env.ejemplo"` y `"GROQ_API_KEY"`.
  - `test_ok`: el cliente devuelve `{"ok": True}` → código 0. La salida contiene `"IA OK"`, el modelo, `"…c123"` y `"origen: archivo"`, y no contiene la clave completa. El esquema enviado exige `"ok"` en modo estricto, con `additionalProperties: False`.
  - `test_error_ia`: el cliente lanza `ErrorIA("La clave de Groq no es válida…")` → código 1 y se imprime el mensaje.
  - `test_respuesta_sin_ok`: el cliente devuelve `{"ok": False}` → código 1.
  - `test_main_bandera`: con monkeypatch de `app.probar_ia` → `main(["--probar-ia"])` devuelve lo que devuelva el doble. No debe crear `QApplication`.

- [ ] **Paso 2: Ejecutar** → FALLA. **Paso 3:** implementar, sin importar Qt en `probar_ia.py`. **Paso 4:** la suite pasa.

- [ ] **Paso 5: Commit** `feat: --probar-ia verifica la clave de Groq`.

---

### Tarea 4: Tema "Taller industrial"

**Archivos:**
- Crear: `alquiler/ui/tema.py`
- Modificar:
  - `alquiler/ui/widgets.py`: `TONOS` desde el tema; `ESTILO = tema.hoja_de_estilo()`; `boton()` con el rol `"peligro"` relleno; hex de `TarjetaResultado` → tokens.
  - `alquiler/ui/vistas/consola_ia.py:36,111`, `alquiler/ui/vistas/alquileres.py:56` y `alquiler/ui/vistas/reportes.py:38-40` (series por token y gráfico de estados con `COLOR_ESTADO`).
  - `alquiler/ui/login.py`: franja de marca `#franjaMarca`.
  - `alquiler/ui/ventana.py`: marca con cuadrado ámbar; `etiqueta_ia` "IA: Groq conectada" / "IA: sin clave (consultas predefinidas)" como `widgets.Insignia`.
- Pruebas: `tests/ui/test_tema.py`, `tests/ui/test_ventana.py` (texto "Groq conectada")

**Interfaces:**
- Produce:
  - `PALETA: dict[str, str]` (claves exactas de la spec §2.1, incluida `ambar_texto`).
  - `COLOR_ESTADO: dict[str, tuple[str, str, str]]` (las 5 etiquetas de estado de equipo, por ejemplo `"En mantenimiento"`).
  - `TONOS: dict[str, tuple[str, str]]` con los tonos `ok`, `info`, `aviso`, `reserva`, `peligro`, `neutro` y `marca`. `ok`/`info`/`reserva`/`aviso`/`peligro` reutilizan los pares de estado; `neutro` es (`#ECEAE4`, `texto`); `marca` es (`ambar_suave`, `ambar_texto`).
  - `COLOR_TONO: dict[str, str]`, el color fuerte por tono, para franjas de tarjetas.
  - `contraste(a: str, b: str) -> float` (WCAG 2.x).
  - `hoja_de_estilo() -> str`.

- [ ] **Paso 1: Escribir las pruebas que fallan** en `tests/ui/test_tema.py`:
  - `test_cinco_estados_con_color`: `set(COLOR_ESTADO) == {"Disponible","Alquilado","Reservado","En mantenimiento","Fuera de servicio"}`.
  - `test_contraste_minimo`, parametrizada sobre los pares `(texto, superficie)`, `(texto, arena)`, `(texto_secundario, arena)`, `(grafito, ambar)`, `(grafito, ambar_hover)`, `("#FFFFFF", acero)`, `("#FFFFFF", peligro)`, `(texto_lateral, grafito)`, todos los `TONOS` (texto sobre fondo) y todos los `COLOR_ESTADO` (texto sobre fondo) → `contraste >= 4.5`.
  - `test_contraste_referencia`: `round(contraste("#000000", "#FFFFFF"), 1) == 21.0`.
  - `test_hoja_usa_tokens`: `PALETA["ambar"]`, `PALETA["grafito"]` y `PALETA["arena"]` están en `hoja_de_estilo()`, y `"#2563EB"` no está.
  - `test_sin_colores_fuera_del_tema`: ningún archivo de `alquiler/ui/**/*.py` salvo `tema.py` coincide con la expresión regular `#[0-9A-Fa-f]{6}\b`.
  - `test_widgets_estilo_es_el_tema`: `widgets.ESTILO == tema.hoja_de_estilo()`.

- [ ] **Paso 2: Ejecutar** → FALLA.

- [ ] **Paso 3: Implementar.**
  - **QSS** según la spec §2.3:
    - el selector activo de `#barraLateral::item:selected` lleva `border-left: 3px solid ambar`, fondo `grafito_claro` y `border-radius: 0`;
    - botón `#primario` con fondo ámbar y texto grafito;
    - `#peligro` con fondo `peligro` y texto blanco;
    - selección de tabla en `acero`/blanco;
    - foco de los campos en `acero` con 2 px;
    - `#tarjeta` y `#kpi`;
    - las nuevas `#tarjetaKpi`, `#kpiFranja` y `#franjaMarca`;
    - QWidget base de 10 pt.
  - **Gráficos de Reportes:** sin borde de marco y con fondo `superficie`.
  - **Revisar los botones primarios:** como máximo uno por barra de acciones; al resto se le quita `"primario"`.

- [ ] **Paso 4: Ejecutar** → PASA y la suite completa en verde.

- [ ] **Paso 5: Verificación visual.** Con `scratchpad/captura.py`, capturar login, equipos, alquileres, reportes, consola y análisis IA. Revisar con Read que no haya texto ilegible ni bordes rotos.

- [ ] **Paso 6: Commit** `feat: tema visual Taller industrial`.

---

### Tarea 5: Widgets `TarjetaKPI` y `BarraEstados`

**Archivos:**
- Modificar: `alquiler/ui/widgets.py`
- Pruebas: `tests/ui/test_widgets_inicio.py`

**Interfaces:**
- Consume: `tema.COLOR_TONO`, `tema.COLOR_ESTADO`.
- Produce:
  - `class TarjetaKPI(QFrame)`, con constructor `TarjetaKPI(datos: dict)` y claves `titulo`, `valor`, `detalle`, `tono` y `destino`.
    - Señal `activada = Signal(str)`, que emite el destino al hacer clic izquierdo, solo si `destino` existe.
    - Atributos: `etiqueta_titulo`, `etiqueta_valor`, `etiqueta_detalle`, `destino`.
    - `objectName "tarjetaKpi"`. La franja superior es un `QFrame#kpiFranja` de 3 px del color del tono.
  - `class BarraEstados(QWidget)`, con método `cargar(conteos: list[tuple[str, int]])`.
    - `segmentos() -> list[tuple[str, int, str]]` devuelve (estado, conteo, color fuerte) y omite los ceros.
    - `etiqueta_vacia: QLabel` muestra "Sin equipos registrados" y es visible cuando el total es 0.
    - `paintEvent` pinta rectángulos proporcionales con `QPainter`. La leyenda es un `QLabel` con el texto `"Disponible 19 · Alquilado 12 · …"`.

- [ ] **Paso 1: Escribir las pruebas que fallan:**
  - `test_tarjeta_emite_destino`: clic con `qtbot.mouseClick` → `activada` emite `"alquileres"`.
  - `test_tarjeta_sin_destino_no_emite`.
  - `test_tarjeta_textos`.
  - `test_barra_segmentos`: `[("Disponible",3),("Alquilado",0),("Reservado",1)]` → `[("Disponible",3,COLOR_ESTADO["Disponible"][0]),("Reservado",1,…)]`.
  - `test_barra_vacia`: con todos los conteos en 0, `etiqueta_vacia.isVisibleTo(barra)` y `segmentos() == []`.
  - `test_barra_pinta_sin_error`: `barra.grab()` con datos y vacía.

- [ ] **Pasos 2–4:** fallar, implementar y pasar. **Paso 5: Commit** `feat: widgets TarjetaKPI y BarraEstados`.

---

### Tarea 6: Lógica de Inicio

**Archivos:**
- Crear: `alquiler/ui/logica/inicio.py`
- Pruebas: `tests/ui/logica/test_inicio.py`

**Interfaces:**
- Consume: `svc_equipos.listar_equipos(s, a)`, `svc_alquileres.listar_alquileres(s, a, estado=…)`, `svc_alquileres.saldo_pendiente(alq)`, `svc_mant.mantenimientos_abiertos(s, a)`, `svc_reportes.ingresos(s, a, desde, hasta).total`, `ai.mantenimiento.recomendar_mantenimiento(s, a, hoy=, persistir=False)`, `svc_clientes.historial_cliente(s, a, cliente_id)`, `formato.pesos`, `formato.fecha`, `ctx.puede`, `ctx.hoy` y `ctx.usuario.rol` / `.cliente_id` / `.nombre`.
- Produce:
  - `resumen(ctx, ahora: Callable[[], datetime] = datetime.now) -> dict` con las claves de la spec §3.2. Los bloques sin permiso **no aparecen**. Formas:
    - `saludo: {"texto": str, "fecha": str}`.
    - `flota: {"conteos": [(estado, n)×5 en orden Disponible, Alquilado, Reservado, En mantenimiento, Fuera de servicio], "total": int, "disponibles": int}`.
    - `operacion: {"activos", "vencidos", "vencen_hoy", "reservas_pendientes"}` (enteros).
    - `mantenimiento: {"abiertos": int}`.
    - `ingresos_mes: {"valor": int, "texto": str}`.
    - `alerta_ia: {"equipos": int, "confianza": str, "texto": str}`.
    - `mis_alquileres: {"activos": int, "proximo": str | None, "saldo": int, "saldo_texto": str}`.
  - `fecha_larga(d: date) -> str` (por ejemplo "Domingo 4 de octubre de 2026"; tablas propias de días y meses, sin depender del `locale`).
  - `saludo_para(hora: int) -> str`: 5–11 "Buenos días", 12–18 "Buenas tardes", el resto "Buenas noches".
  - `tarjetas_kpi(resumen: dict, visibles: set[str]) -> list[dict]`, con dicts `{"clave","titulo","valor","detalle","tono","destino"}`. Si el destino no está en `visibles`, vale `None`.

- [ ] **Paso 1: Escribir las pruebas que fallan** (fixtures `ctx_factory` y `datos_base`, con `HOY = 2026-03-10`):
  - `test_fecha_larga`: `fecha_larga(date(2026,10,4)) == "Domingo 4 de octubre de 2026"`.
  - `test_saludo_para`: `[saludo_para(h) for h in (4, 5, 11, 12, 18, 19)] == ["Buenas noches","Buenos días","Buenos días","Buenas tardes","Buenas tardes","Buenas noches"]`.
  - `test_admin_ve_todos_los_bloques`: el conjunto de claves es `{"saludo","flota","operacion","mantenimiento","ingresos_mes","alerta_ia"}`.
  - `test_empleado_sin_ingresos_ni_ia`: el empleado tiene `ia.ver`, así que `alerta_ia` **sí** aparece; `ingresos_mes` no. Las claves son `{"saludo","flota","operacion","mantenimiento","alerta_ia"}`.
  - `test_cliente_solo_lo_suyo`: las claves son `{"saludo","mis_alquileres"}`. Un usuario cliente sin `cliente_id` produce solo `{"saludo"}`.
  - `test_conteos_operacion`: alquileres insertados directamente: activo con fin el 2026-03-09 (vencido), activo con fin el 2026-03-10 (vence hoy), activo con fin el 2026-03-15 y reservado → `{"activos":3,"vencidos":1,"vencen_hoy":1,"reservas_pendientes":1}`.
  - `test_flota_incluye_fuera_de_servicio`: un equipo en `FUERA_DE_SERVICIO` cuenta en `total` y en su conteo.
  - `test_ingresos_del_mes`: un pago del 2026-03-02 de 50.000 y otro del 2026-02-27 de 10.000 → `valor == 50_000` y `texto == "$50.000"`.
  - `test_inicio_no_persiste_recomendaciones`: llamar 3 veces a `resumen(admin)` deja `RecomendacionIA` en 0 filas.
  - `test_base_vacia`: sin `datos_base`, la flota da `total == 0` y la operación da todo 0, sin excepciones.
  - `test_tarjetas_destino_solo_visible`: `tarjetas_kpi(r, {"equipos"})` da destino `"equipos"` en la tarjeta de disponibles y `None` en la de alquileres.
  - `test_tarjeta_vencidos_tono`: con `vencidos > 0`, `tono == "peligro"`; con 0, `"neutro"`.
  - `test_mis_alquileres`: un alquiler activo del cliente con pago parcial da `activos == 1`, `proximo == formato.fecha(fin)` y `saldo` correcto.

- [ ] **Paso 2: Ejecutar** → FALLA. **Paso 3: Implementar** con un único `ctx.ejecutar`.
  - **Tarjetas, en orden:**
    1. Disponibles (`"19 / 37"`, ok → `equipos`);
    2. Alquileres activos (info → `alquileres`);
    3. Vencidos (peligro|neutro → `alquileres`);
    4. Vencen hoy (aviso|neutro → `alquileres`);
    5. Reservas por entregar (reserva → `reservas`);
    6. En mantenimiento (aviso → `mantenimiento`);
    7. Ingresos del mes (marca → `reportes`);
    8. Para el cliente: "Mis alquileres activos" y "Saldo pendiente" (→ `perfil`).
  - **Confianza predominante:** la moda de los niveles de los resultados del recomendador; con un empate gana la más baja. `texto = "Estimación: {n} equipos a revisar"` (singular "1 equipo").

- [ ] **Paso 4:** PASA. **Paso 5: Commit** `feat: lógica de la pantalla de Inicio`.

---

### Tarea 7: Vista de Inicio y navegación

**Archivos:**
- Crear: `alquiler/ui/vistas/inicio.py`
- Modificar:
  - `alquiler/ui/logica/navegacion.py`: `Seccion("inicio", "Inicio", "perfil.propio")` primero.
  - `alquiler/ui/ventana.py`: si la vista tiene la señal `navegar`, conectarla a `ir_a`.
  - `alquiler/ui/app.py`: `fabricas_de_vistas` con 11 entradas.
- Pruebas: `tests/ui/test_vista_inicio.py`, `tests/ui/test_ventana.py` y `tests/ui/test_app.py` (número de secciones de la autoprueba y de las fábricas)

**Interfaces:**
- Consume: `logica.inicio.resumen`, `tarjetas_kpi`, `widgets.TarjetaKPI`, `widgets.BarraEstados`, `trabajador.ejecutar_en_segundo_plano(fn, al_terminar, al_fallar, dueno)` (firma exacta en `trabajador.py`).
- Produce: `class VistaInicio(QWidget)` con:
  - `navegar = Signal(str)`;
  - atributos `etiqueta_saludo`, `etiqueta_fecha`, `tarjetas: list[TarjetaKPI]`, `barra_estados: BarraEstados | None`, `panel_alerta: QFrame | None`, `boton_ver_analisis` y `ocupado: bool`;
  - métodos `recargar()` y `al_volver()`.

- [ ] **Paso 1: Escribir las pruebas que fallan** (esperar con `qtbot.waitUntil(lambda: not v.ocupado)`):
  - `test_inicio_es_la_primera_seccion`: para los tres roles, `secciones_para(ctx)[0].clave == "inicio"`.
  - `test_ventana_abre_en_inicio`: `VentanaPrincipal(ctx, app.fabricas_de_vistas()).clave_actual() == "inicio"`.
  - `test_vista_admin`: hay ≥ 6 tarjetas; `barra_estados.segmentos()` no está vacío con `datos_base`; `panel_alerta is not None`.
  - `test_vista_cliente`: no hay `barra_estados` ni `panel_alerta`; hay tarjetas de "Mis alquileres".
  - `test_clic_tarjeta_navega`: la ventana completa; clic en la tarjeta de alquileres → `ventana.clave_actual() == "alquileres"`.
  - `test_ver_analisis_navega`: `boton_ver_analisis.click()` → `"analisis_ia"`.
  - `test_recarga_al_volver`: crear un equipo con `catalogo.crear_equipo`, llamar a `al_volver()` → el total de la flota sube en 1.
  - `test_error_se_muestra`: monkeypatch de `inicio.resumen` para que lance `ReglaNegocioError("x")`; capturar `widgets.mostrar_error` → se recibe "x" y `ocupado` vuelve a `False`.
  - Actualizar las pruebas que fijaban 10 secciones a 11 (`autoprueba` imprime "11 secciones").

- [ ] **Paso 2: Ejecutar** → FALLA. **Paso 3: Implementar.**
  - **Disposición:**
    - saludo arriba;
    - un `QGridLayout` de tarjetas de 4 columnas;
    - debajo, una fila con la tarjeta "Estado de la flota" (estiramiento 3) y la tarjeta "Alertas de IA" (estiramiento 2);
    - todo dentro de un `QScrollArea` sin marco.
  - **Recarga:** borra y reconstruye las tarjetas.

- [ ] **Paso 4:** la suite completa PASA.

- [ ] **Paso 5: Capturas** de Inicio con admin, empleado y cliente (base demo, 1280×800). Revisar con Read.

- [ ] **Paso 6: Commit** `feat: pantalla de Inicio con indicadores por rol`.

---

### Tarea 8: Documentación, empaquetado y cierre

**Archivos:**
- Modificar: `README.md`, `PROJECT_INDEX.md`, `docs/superpowers/specs/2026-10-04-alquiler-equipos-design.md` (§6.4 y §9 con la nota "revisado — Fase 6"), `AlquilerEquipos.spec` y `scripts/empaquetar.py` (copiar `alquiler.env.ejemplo` junto al ejecutable).
- Pruebas: `tests/test_documentacion.py` (existente) y `tests/test_empaquetado.py` (si existe; si no, una prueba en `tests/test_documentacion.py`).

- [ ] **Paso 1: Prueba que falla:**
  - `test_readme_documenta_groq`: el README contiene `GROQ_API_KEY`, `alquiler.env`, `--probar-ia` y `openai/gpt-oss-20b`, y no contiene `ANTHROPIC`.
  - `test_spec_pyinstaller_incluye_plantilla`: `"alquiler.env.ejemplo"` aparece en `AlquilerEquipos.spec` o en `scripts/empaquetar.py`.

- [ ] **Paso 2: Actualizar el README:**
  - tabla de variables;
  - sección "Activar la IA con Groq" en 3 pasos: crear la clave en console.groq.com/keys, copiar `alquiler.env.ejemplo` como `alquiler.env` y pegar la clave, y ejecutar `python -m alquiler --probar-ia` (o `AlquilerEquipos.exe --probar-ia`);
  - privacidad, con "Groq" en lugar de "Anthropic";
  - mención de la pantalla de Inicio y del tema.

- [ ] **Paso 3: Actualizar `PROJECT_INDEX.md`** con `tema.py`, `probar_ia.py`, `logica/inicio.py`, `vistas/inicio.py` y las pruebas nuevas, y sustituir `httpx2` por `httpx`.

- [ ] **Paso 4: Empaquetado.**
  - En el spec de PyInstaller: `hiddenimports` para `groq` si el análisis no lo encuentra, y `datas`/copia de `alquiler.env.ejemplo`.
  - Construir en Linux: `python scripts/empaquetar.py`.
  - Ejecutar `dist/AlquilerEquipos/AlquilerEquipos --autoprueba` en el entorno limpio (sin python en PATH). Se espera `AUTOPRUEBA OK: 11 secciones` y código 0.
  - Ejecutar `--probar-ia` sin clave. Se espera código 2 y las instrucciones.

- [ ] **Paso 5: Suite completa.** `QT_QPA_PLATFORM=offscreen pytest -q`, todo en verde. Anotar el total.

- [ ] **Paso 6: Capturas finales** de las 11 secciones con admin y de Inicio con empleado y cliente. Revisión visual.

- [ ] **Paso 7: Commits** `docs: Groq, alquiler.env e Inicio` y `build: plantilla alquiler.env en el ejecutable`. Fusión *fast-forward* a `main`.

- [ ] **Paso 8: Entrega.**
  - Copiar el proyecto actualizado a la carpeta del usuario (`C:\Users\moren\Music\Nueva carpeta\AlquilerEquipos`), sin `alquiler.env` real.
  - Regenerar `historial-git.bundle` (`git bundle create f HEAD main`).
  - Actualizar la memoria `/areas/alquiler-equipos.md`.
