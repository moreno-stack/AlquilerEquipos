# Fase 6 — Interfaz "Taller industrial", pantalla de Inicio y proveedor Groq

- **Fecha:** 2026-10-04
- **Estado:** diseño aprobado en conversación; pendiente revisión del documento
- **Base:** especificación principal `2026-10-04-alquiler-equipos-design.md` (Fases 1–5, 463 pruebas)
- **Rama:** `fase-6-ui-groq`

## 1. Objetivo y criterios de éxito

El usuario pidió dos mejoras:

1. "Una interfaz más agradable para el usuario. La que tenemos está muy básica (genérica)."
2. "Para el caso de la API, vamos a utilizar la API de Groq. Que dejes todo listo para que al final yo agregue la API."

Decisiones del usuario:

- Paleta congruente con un negocio de alquiler de equipos (elegida por el arquitecto).
- Único elemento nuevo de interfaz: **pantalla de Inicio**. No se añaden iconos, login a dos columnas ni notificaciones tipo *toast*.
- Modelo por defecto: `openai/gpt-oss-20b`.

La fase está terminada cuando se cumple todo lo siguiente:

- La aplicación usa la paleta "Taller industrial" en todas las vistas, diálogos, login y gráficos, con capturas de cada sección revisadas.
- Tras iniciar sesión se abre **Inicio**, con indicadores reales según el rol.
- Sin clave, la aplicación funciona igual que hoy: análisis de IA local y consultas predefinidas.
- Con `GROQ_API_KEY` en el entorno o en `alquiler.env`, la consola Text-to-SQL usa Groq sin cambiar ninguna otra línea.
- `python -m alquiler --probar-ia` (y el `.exe`) confirma con una llamada real si la clave funciona.
- No quedan referencias a Anthropic en el código, la configuración ni la documentación de uso. Se exceptúa el historial de especificaciones anteriores.
- La suite completa pasa con la red bloqueada. Las pruebas existentes se adaptan; ninguna se elimina sin sustituirla.

## 2. Paleta y tema visual

### 2.1 Tokens "Taller industrial"

| Token | Valor | Uso |
|-------|-------|-----|
| `grafito` | `#1E2630` | Barra lateral, texto sobre ámbar |
| `grafito_claro` | `#2A3440` | Elemento activo/hover de la barra lateral |
| `texto_lateral` | `#C9D1D9` | Texto de la barra lateral |
| `ambar` | `#F2A900` | Marca, botón primario, indicador de sección activa |
| `ambar_hover` | `#D99700` | Hover del botón primario |
| `ambar_suave` | `#FFF4D6` | Fondo de avisos de marca |
| `ambar_texto` | `#7A5300` | Texto sobre `ambar_suave` |
| `acero` | `#2F5D86` | Foco, enlaces, selección de tabla |
| `arena` | `#F5F3EE` | Fondo de la aplicación |
| `superficie` | `#FFFFFF` | Tarjetas, tablas, campos |
| `borde` | `#E4E1D9` | Bordes finos |
| `texto` | `#1F2933` | Texto principal |
| `texto_secundario` | `#5F6B76` | Etiquetas, ayudas |
| `peligro` | `#B23A3A` | Botón de acción destructiva, errores |

Cada estado de equipo tiene un color fuerte (barras y gráficos) y un par fondo/texto (insignias):

| Estado | Fuerte | Fondo | Texto |
|--------|--------|-------|-------|
| Disponible | `#2E7D4F` | `#E3F1E8` | `#1F5C3A` |
| Alquilado | `#2F6DB5` | `#E2ECF7` | `#244F80` |
| Reservado | `#7A5AA6` | `#EEE8F6` | `#5A3F85` |
| En mantenimiento | `#C46A10` | `#FBEBD9` | `#8A4A0B` |
| Fuera de servicio | `#B23A3A` | `#F6E1E1` | `#8A2B2B` |

Los tonos semánticos que ya existen en `widgets.TONOS` (`ok`, `aviso`, `peligro`, `info`, `neutro`) se reasignan a esta paleta. Se conserva su API: `tono_para`, `TONO_PRIORIDAD`.

### 2.2 Módulo `alquiler/ui/tema.py` (nuevo, sin dependencias de backend)

- `PALETA: dict[str, str]` con los tokens de §2.1.
- `COLOR_ESTADO: dict[str, tuple[str, str, str]]`, que asigna a cada estado su terna (fuerte, fondo, texto).
- `hoja_de_estilo() -> str` genera la QSS a partir de los tokens. Ningún color aparece escrito a mano fuera de `tema.py`.
- `widgets.ESTILO` pasa a ser `tema.hoja_de_estilo()` (alias de compatibilidad).
- **Prueba de contraste:** el texto principal sobre la superficie, el texto sobre el ámbar y el texto de cada insignia sobre su fondo deben alcanzar **≥ 4,5:1** (WCAG AA) según la fórmula de luminancia relativa.

### 2.3 Lineamientos de estilo (QSS)

- **Tipografía:**
  - Base de 10 pt.
  - Título de sección de 18 pt seminegrita; subtítulos en `texto_secundario`.
  - Familia del sistema: Segoe UI en Windows; en Linux se usa la que el sistema provea.
- **Tarjetas** (`QFrame#tarjeta`): fondo `superficie`, borde de 1 px `borde`, radio de 10 px, relleno de 16 px.
- **Botones:**
  - Primario (`#primario`): ámbar con texto grafito. Por defecto es secundario: fondo blanco con borde.
  - Peligro (`#peligro`): contorno rojo con texto rojo (5,9:1 sobre blanco) que se rellena de rojo con texto blanco al pasar el cursor. *Ajuste tras la revisión visual: dos botones rojos rellenos juntos («Dar de baja», «Eliminar») recargaban la barra.*
  - Radio de 6 px y altura mínima de 32 px.
  - `widgets.boton(texto, tipo="primario"|"secundario"|"peligro")` asigna el `objectName`. Se revisan las vistas para que haya un solo botón primario por barra de acciones.
- **Tablas:**
  - Filas alternas.
  - Cabecera sin bordes verticales, en `texto_secundario`.
  - Selección en `acero` con texto blanco.
  - Altura de fila de 30 px.
- **Barra lateral:**
  - Fondo grafito.
  - Elemento activo en `grafito_claro` con borde izquierdo ámbar de 3 px.
  - Marca con un cuadrado ámbar.
  - Sin rectángulo de foco.
- **Insignias:** forma de pastilla (radio 10 px) con el par fondo/texto del estado o tono.
- **Campos de formulario:** borde `borde` y foco en `acero` con borde de 2 px.
- **Gráficos de Reportes:** las series usan `COLOR_ESTADO` y los tokens; fondo `superficie` y sin borde de marco.
- **Login:** conserva su estructura y añade una franja grafito de marca arriba (nombre de la aplicación en blanco y cuadrado ámbar).
- **Insignia de IA en la cabecera:**
  - Con clave: "IA: Groq conectada", en ámbar suave.
  - Sin clave: "IA: sin clave (consultas predefinidas)", en tono neutro.

## 3. Pantalla de Inicio

### 3.1 Navegación

- Nueva sección `Seccion("inicio", "Inicio", "perfil.propio")`, primera en `SECCIONES`. Los tres roles tienen `perfil.propio`.
- `VentanaPrincipal` abre `inicio` al arrancar. Antes abría la primera sección visible, que ahora es esa misma.
- `fabricas_de_vistas()` pasa a 11 vistas; `autoprueba` recorre las 11.

### 3.2 Lógica `alquiler/ui/logica/inicio.py` (sin Qt)

`resumen(ctx) -> dict` reutiliza servicios existentes dentro de una única llamada `ctx.ejecutar`. Cada bloque se incluye solo si el actor tiene el permiso, de modo que nunca se provoca un `PermisoDenegado`.

| Bloque | Permiso | Contenido |
|--------|---------|-----------|
| `saludo` | — | "Buenos días/tardes/noches, {nombre}" según la hora del reloj del contexto, y la fecha larga en español ("Domingo 4 de octubre de 2026") |
| `flota` | `equipos.gestionar` (sin él, `listar_equipos` solo devuelve los disponibles) | Conteo por estado (los 5, en orden fijo), total y disponibles |
| `operacion` | `alquileres.ver` | Alquileres activos, vencidos (activos con fecha prevista < hoy), que vencen hoy y reservas pendientes de entregar |
| `mantenimiento` | `mantenimiento.ver` | Mantenimientos abiertos |
| `ingresos_mes` | `reportes.ver` | Ingresos del mes en curso (del día 1 a hoy), formateados en pesos |
| `alerta_ia` | `ia.ver` | Número de equipos sobre el umbral del recomendador y la confianza predominante, redactado como estimación ("Estimación: 6 equipos a revisar") |
| `mis_alquileres` | cliente vinculado | Alquileres activos propios, próximo vencimiento y saldo pendiente total |

`tarjetas_kpi(resumen) -> list[dict]` convierte el resumen en tarjetas `{clave, titulo, valor, detalle, tono, destino}`, donde `destino` es la sección a la que navega el clic. La tarjeta solo se crea si esa sección es visible para el rol.

### 3.3 Vista `alquiler/ui/vistas/inicio.py`

- **Cabecera:** saludo y fecha.
- **Rejilla de tarjetas KPI** (`widgets.TarjetaKPI`): título en `texto_secundario`, valor de 22 pt, detalle opcional y una franja superior de 3 px con el color del tono.
  - Al hacer clic se emite `navegar(destino)`; la ventana conecta esa señal con `ir_a`.
  - El cursor cambia a mano solo si la tarjeta tiene destino.
- **"Estado de la flota":**
  - `widgets.BarraEstados` es una barra apilada pintada con `QPainter` y los colores de `COLOR_ESTADO`, más una leyenda con conteos.
  - Expone `segmentos()` para las pruebas.
  - Si el total es 0, muestra "Sin equipos registrados".
- **"Alertas de IA"** (solo si existe `alerta_ia`): texto de estimación con su insignia de confianza y el botón primario "Ver análisis", que navega a `analisis_ia`.
- **Cliente:** tarjetas de sus alquileres y un acceso a "Mi perfil".
- **Carga:**
  - Usa el trabajador existente (`QThreadPool`) con el estado "Cargando…".
  - Se recarga con `al_volver()`.
  - Los errores se muestran con `mostrar_error`, igual que el resto de vistas.

## 4. Proveedor de IA: Groq

### 4.1 Cliente `ClienteGroq` (en `alquiler/ai/llm.py`)

- Sustituye a `ClienteClaude`. El protocolo `ClienteLLM.generar_json(sistema, mensajes, esquema) -> dict` **no cambia**, por lo que `consultas.py`, `prompts.py`, `sql_seguro.py` y la lógica de la interfaz no se modifican.
- Usa el SDK oficial `groq>=1.7`: `Groq(api_key, timeout, max_retries, http_client=None)`. `http_client` es un `httpx.Client` inyectable para las pruebas con `httpx.MockTransport`.
- Petición:
  ```python
  chat.completions.create(
      model=modelo,
      messages=[{"role": "system", "content": sistema}, *mensajes],
      response_format={"type": "json_schema",
                       "json_schema": {"name": "respuesta", "strict": True, "schema": esquema}},
      temperature=0,
      max_completion_tokens=4096,
  )
  ```
  Los esquemas actuales (`ESQUEMA_GENERACION`, `ESQUEMA_RESPUESTA`) ya cumplen el modo estricto: todos los campos son `required` y llevan `additionalProperties: false`. Una prueba fija esta propiedad para cualquier esquema futuro.
- **Lectura de la respuesta:** se toma `choices[0].message.content`. Si `finish_reason == "length"`, se lanza `ErrorIA("La respuesta de la IA quedó incompleta; intente con una pregunta más concreta.")`. Si el contenido está vacío, no es JSON o no es un objeto, se lanza `ErrorIA("La IA devolvió una respuesta con formato inesperado.")`.
- **Traducción de errores** (mensajes en español; la clave nunca aparece en ellos):

| Excepción `groq` | Mensaje |
|------------------|---------|
| `AuthenticationError` / `PermissionDeniedError` | "La clave de Groq no es válida o no tiene permisos; revise GROQ_API_KEY." |
| `RateLimitError` | "Se alcanzó el límite de uso de Groq; espere un momento o use las consultas predefinidas." |
| `NotFoundError` | "El modelo configurado en GROQ_MODEL no existe o no está disponible." |
| `BadRequestError` | "Groq rechazó la solicitud (formato o modelo no compatible)." |
| `APIConnectionError` (incluye *timeout*) | "Sin conexión con Groq o tiempo agotado; puede usar las consultas predefinidas." |
| `APIStatusError` (resto) | "El servicio de IA respondió con un error (código {n})." |

- `crear_cliente(config) -> ClienteLLM | None` devuelve `None` sin clave, como hasta ahora.

### 4.2 Configuración (`alquiler/config.py`)

| Variable | Por defecto | Validación |
|----------|-------------|------------|
| `GROQ_API_KEY` | — (sin ella, modo consultas predefinidas) | Se recorta; vacía equivale a ausente |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | No vacía |
| `GROQ_TIMEOUT` | `30` | > 0 |
| `GROQ_MAX_RETRIES` | `2` | 0–10 |

- Los campos de `Config` pasan a `groq_api_key`, `groq_model`, `groq_timeout` y `groq_max_retries`. Desaparecen `ANTHROPIC_*` y `anthropic_*`.
- `__repr__` de `Config` enmascara la clave: muestra solo sus 4 últimos caracteres.

### 4.3 Archivo `alquiler.env` (para "agregar la API al final")

- **Formato:** `CLAVE=valor` por línea.
  - Se ignoran las líneas vacías y las que empiezan por `#`.
  - Se recortan los espacios y las comillas simples o dobles que rodean el valor.
  - Se tolera el BOM UTF-8 que añade el Bloc de notas.
  - Una línea sin `=` produce un aviso, no un error.
- **Claves aceptadas:** solo las que empiezan por `GROQ_` o `ALQUILER_`; las demás se ignoran.
- **Búsqueda,** en este orden; se usa el primer archivo que exista:
  1. la carpeta del ejecutable cuando la app está empaquetada (`sys.frozen`) o la raíz del proyecto cuando se ejecuta desde el código;
  2. `~/.alquiler_equipos/alquiler.env`.
- **Precedencia:** una variable de entorno real **gana** sobre el archivo.
- `cargar_config(env=None, archivo=None)` permite inyectar ambos en las pruebas. `config.origen_clave` vale `"entorno"`, `"archivo"` o `None`; la cabecera y `--probar-ia` lo usan para decir de dónde salió la clave.
- **Plantillas y repositorio:** se entrega `alquiler.env.ejemplo`, con `GROQ_API_KEY=` vacío y comentarios en español sobre cómo obtener la clave en console.groq.com. `alquiler.env` se añade a `.gitignore`. El spec de PyInstaller copia la plantilla junto al `.exe`.

### 4.4 Comando `--probar-ia`

- `python -m alquiler --probar-ia` carga la configuración y procede así:
  - **Sin clave:** imprime cómo configurarla (archivo y variable) y sale con código **2**.
  - **Con clave:** llama a `generar_json` con un esquema mínimo `{"ok": boolean}`.
    - Si la llamada funciona, imprime `IA OK: Groq responde con el modelo X (clave …abcd, origen: archivo)` y sale con código **0**.
    - Si se produce un `ErrorIA`, imprime el mensaje traducido y sale con código **1**.
- Es el único camino con red real. Las pruebas inyectan un cliente falso.

### 4.5 Textos y documentación

- La consola de IA (`aviso_sin_api`) y la respuesta `sin_api` mencionan `GROQ_API_KEY` y `alquiler.env`.
- **README:**
  - tabla de variables;
  - sección "Activar la IA con Groq" en 3 pasos: crear la clave, copiar `alquiler.env.ejemplo` como `alquiler.env` y ejecutar `--probar-ia`;
  - nota de privacidad: la pregunta, el esquema de tablas (sin la tabla `usuario`) y hasta 50 filas de resultado se envían a Groq.
- **PROJECT_INDEX.md:** nuevos módulos y pruebas.
- **`requirements.txt`:** `groq>=1.7` en lugar de `anthropic`.
- **PyInstaller:** se revisa si `groq` necesita *hidden imports*.
- **Especificación principal:** se actualizan §6.4 y §9 con una nota "revisado — Fase 6".

## 5. Arquitectura y límites

- **Archivos nuevos:** `ui/tema.py`, `ui/logica/inicio.py` y `ui/vistas/inicio.py`. Los widgets nuevos (`TarjetaKPI`, `BarraEstados`) van en `ui/widgets.py`.
- **Capas:** la regla de la prueba AST de arquitectura no cambia. `vistas/inicio.py` solo importa `logica`, `widgets` y `tema`. `tema.py` no importa nada del backend.
- **Fuera de `ui/`** solo cambian `config.py`, `ai/llm.py`, `ai/consultas.py` (texto `sin_api`) y `__main__`/`app.py` (bandera `--probar-ia`). Modelos, servicios y migraciones **no se tocan**.

## 6. Estrategia de pruebas (TDD)

- **`tests/ui/test_tema.py`:**
  - todos los estados tienen color;
  - contraste ≥ 4,5:1 en los pares de §2.2;
  - la QSS contiene los tokens;
  - no quedan hex sueltos en `widgets.py` ni en las vistas, salvo `tema.py`.
- **`tests/ui/logica/test_inicio.py`:**
  - bloques por rol (admin, empleado, cliente);
  - conteos con datos controlados;
  - vencidos frente a "vencen hoy";
  - ingresos del mes;
  - sin permiso, el bloque está ausente y no se lanza excepción;
  - saludo según la hora;
  - destino de las tarjetas solo hacia secciones visibles.
- **`tests/ui/test_vista_inicio.py`** (pytest-qt):
  - las tarjetas se renderizan;
  - el clic navega;
  - `BarraEstados.segmentos()`;
  - caso sin equipos;
  - recarga al volver;
  - la ventana abre en Inicio.
- **`tests/ai/test_llm.py`** (reescrita con `httpx.MockTransport`):
  - el cuerpo de la petición contiene `model`, `messages[0].role == "system"`, `response_format.json_schema.strict == True`, `temperature == 0` y la cabecera `Authorization: Bearer`;
  - el JSON se interpreta;
  - `finish_reason == "length"`;
  - contenido no JSON;
  - cada fila de la tabla de errores;
  - `max_retries=0` en las pruebas para que sean rápidas.
- **`tests/test_config.py`:**
  - valores por defecto de `GROQ_*` y sus validaciones;
  - análisis de `alquiler.env` (comentarios, comillas, BOM, línea inválida, claves ajenas ignoradas);
  - precedencia del entorno;
  - `origen_clave`;
  - `repr` enmascarado.
- **`--probar-ia`:** códigos de salida 0, 1 y 2 con un cliente falso.
- **Interfaz:** se actualizan los textos que mencionaban Anthropic (ventana, consola de IA).
- **Verificación visual:** capturas *offscreen* de las 11 secciones con los tres roles y de los diálogos principales y el login.
- **Aislamiento de red:** el fixture que bloquea la red sigue activo y ninguna prueba toca la red.

## 7. Fuera de alcance

- Tema oscuro e interruptor de tema.
- Iconos en el menú, login a dos columnas y notificaciones *toast* (no elegidos).
- Varios proveedores de IA a la vez o un selector de proveedor.
- Respuestas en *streaming*.
- Guardar la clave desde la interfaz: se hace editando `alquiler.env`.
