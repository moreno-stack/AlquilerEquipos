# Sistema Inteligente de Alquiler de Equipos

Aplicación de escritorio (Python + PySide6) para gestionar el alquiler de equipos: inventario con
máquina de estados, clientes, alquileres, devoluciones con cálculo de mora, pagos, reservas,
mantenimiento y reportes. Incluye un **núcleo de IA explicable**:

- predicción de demanda;
- recomendador de mantenimiento preventivo;
- análisis de retrasos;
- consola de consultas en lenguaje natural (Text-to-SQL con Groq, de solo lectura).

Todo resultado de IA se presenta como **estimación**, acompañado de su nivel de confianza, sus
indicadores y la justificación paso a paso.

La interfaz usa el tema **"Pizarra y cian"** (fondo azul pizarra, acento cian y detalles violeta, menú lateral con iconos, un color fijo por estado de equipo y contraste verificado WCAG AA) y abre en una pantalla de
**Inicio** con indicadores según el rol: disponibilidad de la flota, alquileres activos y
vencidos, reservas por entregar, mantenimientos abiertos, ingresos del mes y la alerta de
mantenimiento de la IA; los clientes ven sus alquileres activos y su saldo.

> Proyecto académico — Ingeniería de Software, Universidad Cooperativa de Colombia (Pasto).
> Diseño: [`docs/superpowers/specs/2026-10-04-alquiler-equipos-design.md`](docs/superpowers/specs/2026-10-04-alquiler-equipos-design.md) ·
> Plan por fases: [`docs/superpowers/plans/2026-10-04-alquiler-equipos.md`](docs/superpowers/plans/2026-10-04-alquiler-equipos.md) ·
> Mapa del código: [`PROJECT_INDEX.md`](PROJECT_INDEX.md)

---

## 1. Requisitos

| | |
|---|---|
| Sistema operativo | Windows 10/11, macOS o Linux con escritorio |
| Python | 3.11 o superior (solo para ejecutar desde el código; el ejecutable empaquetado no lo necesita) |
| Base de datos | SQLite (incluida en Python; no requiere servidor) |
| IA (opcional) | Clave gratuita de Groq para la consola en lenguaje natural (ver §3.1) |

Dependencias (`requirements.txt`): SQLAlchemy, Alembic, bcrypt, groq, PySide6, pytest y
pytest-qt.

## 2. Instalación

**Obtener el código.** Elija una de estas opciones:

```bash
# desde un repositorio remoto (si lo publicó)
git clone <url-del-repositorio> AlquilerEquipos

# desde el archivo de historial entregado (no necesita internet)
git clone -b main historial-git.bundle AlquilerEquipos
```

**Crear el entorno virtual e instalar las dependencias:**

```bash
cd AlquilerEquipos
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell o cmd)
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

**Comprobar la instalación.** El primer comando muestra la versión. El segundo, sin abrir ventanas,
crea una base **temporal** con datos de prueba y recorre todas las pantallas; debe terminar con
`AUTOPRUEBA OK`. No toca su base de datos real.

```bash
python -m alquiler --version
python -m alquiler --autoprueba
```

## 3. Configuración

Todo es opcional. Cada valor se puede dar de dos formas:

- en el archivo **`alquiler.env`** (recomendado en Windows: no hay que tocar variables del sistema);
- como **variable de entorno**, que tiene prioridad sobre el archivo.

| Variable | Por defecto | Descripción |
|---|---|---|
| `ALQUILER_DB_PATH` | `~/.alquiler_equipos/alquiler.db` | Archivo SQLite. La carpeta se crea si no existe. Admite espacios y tildes. |
| `ALQUILER_ADMIN_PASSWORD` | `admin1234` | Contraseña del usuario `admin` que se crea en el primer arranque. |
| `ALQUILER_FACTOR_MORA` | `1.5` | Recargo por día de retraso = días × tarifa diaria × factor. Acepta coma decimal (`1,5`). Debe ser > 0. |
| `GROQ_API_KEY` | *(vacía)* | Clave de la API de Groq. Sin ella, la Consola IA funciona solo con las 6 consultas predefinidas y los análisis de IA (locales) siguen disponibles. |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Modelo de Groq para el Text-to-SQL. Debe admitir salida JSON estricta (`json_schema` con `strict`); `openai/gpt-oss-120b` también sirve. Verificado en la documentación de Groq el 2026-10-04. |
| `GROQ_TIMEOUT` | `30` | Tiempo máximo por llamada a la API, en segundos (> 0). |
| `GROQ_MAX_RETRIES` | `2` | Reintentos automáticos ante límite de uso, errores 5xx o fallos de red (de 0 a 10). |

Un valor inválido (por ejemplo `GROQ_TIMEOUT=0`) detiene el arranque con un mensaje que nombra la
variable.

### 3.1 Activar la IA con Groq (3 pasos)

1. Cree una clave gratuita en <https://console.groq.com/keys> (empieza por `gsk_`).
2. En la carpeta del programa (la raíz del proyecto o la carpeta del ejecutable), copie
   `alquiler.env.ejemplo` con el nombre `alquiler.env` y pegue la clave:
   ```ini
   GROQ_API_KEY=gsk_su_clave_aqui
   ```
   El archivo también se busca en `~/.alquiler_equipos/alquiler.env`. Acepta comentarios con `#`,
   comillas y el formato que deja el Bloc de notas. **No lo comparta ni lo suba a git** (ya está
   en `.gitignore`).
3. Verifique la conexión:
   ```bash
   python -m alquiler --probar-ia          # desde el código
   AlquilerEquipos.exe --probar-ia         # con el ejecutable
   ```
   | Código | Significado |
   |---|---|
   | `0` | `IA OK`: Groq respondió; se muestran el modelo, los 4 últimos caracteres de la clave y su origen (archivo o entorno). |
   | `1` | Groq no respondió o rechazó la clave; el mensaje explica la causa (clave inválida, límite de uso, modelo inexistente, sin conexión). |
   | `2` | No hay clave configurada; se imprimen estos mismos pasos. |

Al abrir la aplicación, la barra de estado muestra **"IA: Groq conectada"** o **"IA: sin clave
(consultas predefinidas)"**.

**Con variables de entorno** (alternativa al archivo):

Windows, para la sesión actual de PowerShell:
```powershell
$env:GROQ_API_KEY     = "gsk_..."
$env:ALQUILER_DB_PATH = "C:\Users\moren\Documents\alquiler.db"
```

Windows, de forma permanente (abra una terminal nueva después):
```powershell
setx GROQ_API_KEY "gsk_..."
```

macOS / Linux:
```bash
export GROQ_API_KEY="gsk_..."
```

## 4. Inicio rápido

```bash
python -m alquiler
```

**Primer arranque:**

1. Se crea la base de datos y se aplican las migraciones (Alembic).
2. Se crea el usuario `admin` con la contraseña de `ALQUILER_ADMIN_PASSWORD`.
3. Si no hay equipos registrados, la aplicación **ofrece cargar los datos de demostración**. Son
   18 meses de operación simulada a través de las reglas de negocio reales:
   - ≈1100 alquileres, 37 equipos en 6 categorías y 60 clientes (incluye morosos e inactivos);
   - reservas pendientes, listas y vencidas;
   - equipos en mantenimiento y fuera de servicio.

   La carga tarda unos segundos.
4. Aparece el inicio de sesión.

Los datos demo también se pueden cargar desde la terminal en una base vacía:
`python -m alquiler.seed [--hoy AAAA-MM-DD] [--semilla 42] [--meses 18]`.

**Credenciales de prueba:**

| Usuario | Contraseña | Rol | Qué puede hacer |
|---|---|---|---|
| `admin` | `admin1234` | Administrador | Todo: incluye eliminar equipos, Reportes, Consola IA y Usuarios |
| `empleado` | `empleado123` | Empleado | Equipos, mantenimiento, clientes, alquileres, devoluciones, reservas y Análisis IA |
| `cliente` | `cliente123` | Cliente | Catálogo de equipos disponibles y Mi perfil (sus datos de contacto y su historial) |

**Crear una cuenta propia.** En la portada, el enlace *¿No tiene cuenta? Regístrese como cliente* abre el formulario *Crear cuenta* (nombre, documento, teléfono, correo opcional, usuario y contraseña). Al terminar, la persona entra directo con rol **Cliente**. Solo se crean cuentas de cliente; las de empleado y administrador las crea un administrador en *Usuarios*. Si el documento ya pertenece a un cliente registrado por el personal, el sistema no deja reclamarlo: el personal le crea el usuario.

> **Seguridad.** Estas credenciales son de demostración. En un uso real:
> - defina `ALQUILER_ADMIN_PASSWORD` antes del primer arranque o cambie la contraseña en *Mi perfil*;
> - desactive las cuentas `empleado` y `cliente` desde *Usuarios*.

## 5. Uso por secciones

| Sección | Qué hace |
|---|---|
| **Equipos** | Catálogo con filtros y panel del **ciclo de vida**: estado actual y estados alcanzables (Disponible → Alquilado / Reservado / En mantenimiento / Fuera de servicio). Permite crear, editar, dar de baja y abrir un mantenimiento. |
| **Mantenimiento** | Mantenimientos abiertos, cierre con costo y notas, e historial por equipo. |
| **Clientes** | Alta, edición, desactivación (también bloquea su usuario) e historial con saldo pendiente. |
| **Alquileres** | **Nuevo alquiler**: solo clientes activos y equipos disponibles, con costo en vivo; un inicio futuro crea una reserva. **Devolución**: vista previa de días de retraso, mora y total; los daños abren un correctivo. **Pago**: el máximo es el saldo. Las filas rojas son devoluciones vencidas. |
| **Reservas** | Reservas *pendientes*, *listas para entregar* y *vencidas*. Una reserva vencida no se puede entregar: debe cancelarse. |
| **Reportes** | Indicadores de ingresos por concepto, ingresos por mes (* = mes parcial), uso de la flota por categoría y por equipo, y alquileres vencidos. |
| **Análisis IA** | Tarjetas de **Demanda**, **Mantenimiento preventivo** y **Retrasos**. Cada una muestra "Estimación", la confianza y un desplegable con la justificación y los indicadores. |
| **Consola IA** | Preguntas en lenguaje natural con la respuesta en dos partes: **(1) respuesta directa** y **(2) cómo se obtuvo** (pasos, SQL ejecutado y datos). Incluye historial de la sesión y 6 consultas rápidas que no usan IA. |
| **Usuarios** | Alta de cuentas, activar/desactivar y restablecer contraseña (solo administradores). |
| **Mi perfil** | Cambio de contraseña. El cliente también edita su contacto y ve su historial. |

Las consultas a la IA, los análisis y los reportes se ejecutan en segundo plano: la ventana nunca
se congela y el botón queda deshabilitado mientras termina la tarea.

## 6. Privacidad y gobierno de datos

La aplicación trabaja **localmente**: la base SQLite está en su equipo y nada sale de él, **salvo
cuando se usa la Consola IA con una clave de Groq**.

| Funcionalidad | ¿Envía datos a Groq? | Qué se envía |
|---|---|---|
| Equipos, clientes, alquileres, reportes, usuarios | No | — |
| Análisis IA (demanda, mantenimiento, retrasos) | **No**: los cálculos son locales | — |
| Consultas rápidas predefinidas | No | — |
| Consola IA, paso 1 (generar el SQL) | **Sí** | Su pregunta, la fecha de hoy y la **estructura** de la base: nombres de tablas y columnas y valores posibles de los estados. No incluye registros. |
| Consola IA, paso 3 (redactar la respuesta) | **Sí** | Su pregunta, el SQL ejecutado y **hasta 50 filas del resultado**. Según la pregunta, pueden incluir **datos personales de clientes** (nombres, documentos, teléfonos, correos), **registros de alquileres** (fechas, equipos), montos y pagos. |

Nunca se envían:
- la tabla `usuario`;
- las contraseñas (están cifradas con bcrypt);
- el esquema interno de SQLite.

Esto lo garantizan tres barreras: validador, conexión de solo lectura y autorizador de SQLite.

**Recomendaciones:**
- **Sin `GROQ_API_KEY` no sale ningún dato del equipo.** Todo lo demás funciona igual.
- `--probar-ia` solo envía un mensaje de prueba fijo; ningún dato de la base.
- Formule preguntas agregadas ("¿cuántos alquileres por categoría…?") en lugar de pedir listados
  con datos personales cuando no los necesite.
- Revise las condiciones de uso y la política de datos de Groq vigentes para su cuenta.
- En Colombia, el tratamiento de datos personales se rige por la Ley 1581 de 2012. Si usará la
  consola con datos reales de clientes, verifique con su institución o un asesor que cuenta con la
  autorización y el aviso de privacidad que exige enviarlos a un proveedor externo. Esta nota es
  informativa, no una asesoría legal.
- Las respuestas de la IA se muestran junto al SQL y los datos reales. Verifique las cifras antes
  de tomar decisiones.

## 7. Pruebas

```bash
pytest                          # suite completa (~550 pruebas, ~80 s)
pytest tests/services           # reglas de negocio
pytest tests/ai                 # IA: analizadores, seguridad SQL, cliente de Groq, consola
pytest tests/ui                 # interfaz (pytest-qt, sin pantalla)
pytest tests/ai/test_sql_seguro.py -k rechaza   # una prueba concreta
```

**Aislamiento de red.**
- Es automático: `tests/conftest.py` bloquea toda conexión de red durante las pruebas.
- La API de Groq se sustituye por clientes falsos o por un transporte HTTP simulado, así que la
  suite no consume créditos ni necesita internet.
- `tests/test_aislamiento_red.py` verifica el bloqueo.

Las pruebas de interfaz se ejecutan sin pantalla (`QT_QPA_PLATFORM=offscreen`, configurado en
`tests/ui/conftest.py`). Para más detalle por módulo, vea [`PROJECT_INDEX.md`](PROJECT_INDEX.md#guía-de-pruebas).

## 8. Empaquetado (ejecutable sin Python)

```bash
pip install pyinstaller
python scripts/empaquetar.py         # Linux / macOS
scripts\empaquetar_windows.bat       # Windows
```

El script:
1. construye `dist/AlquilerEquipos/` (formato *onedir*, ≈215 MB, ≈90 MB comprimido);
2. lo copia a una carpeta temporal;
3. comprueba que `alquiler.env.ejemplo` quedó **junto al ejecutable**;
4. lo ejecuta con `--autoprueba` en un entorno limpio, con un `PATH` sin Python y una ruta de base
   con espacio y tilde;
5. (Linux/macOS) ejecuta `--probar-ia` sin clave y espera el código 2 con las instrucciones.

Debe terminar con `AUTOPRUEBA OK` y código 0.

- **Distribución:** copie la carpeta completa `dist/AlquilerEquipos` y ejecute
  `AlquilerEquipos.exe` (Windows) o `AlquilerEquipos` (Linux). No se necesita Python instalado.
- **PyInstaller no compila de forma cruzada:** el `.exe` de Windows se construye en Windows con el
  mismo `AlquilerEquipos.spec`.
- **Comprobar el `.exe` en Windows.** En Windows la aplicación no tiene consola, así que la prueba se
  lanza con:
  ```bat
  start /wait "" dist\AlquilerEquipos\AlquilerEquipos.exe --autoprueba
  echo %ERRORLEVEL%
  ```
  El resultado debe ser `0`.
- **Activar la IA en el `.exe`:** copie `dist\AlquilerEquipos\alquiler.env.ejemplo` como
  `alquiler.env` en esa misma carpeta, pegue la clave y ejecute
  `AlquilerEquipos.exe --probar-ia`. Como no hay consola, el resultado aparece en un **cuadro de
  diálogo** (y el código de salida queda en `%ERRORLEVEL%` si se lanza con `start /wait`).
- El spec incluye las migraciones de Alembic como datos (`alquiler/migrations/**`) y excluye los
  módulos de Qt que no se usan.

## 9. Estructura del proyecto

```
alquiler/          código de la aplicación
  config.py, db.py, models.py, auth.py, errors.py, seed.py
  migrations/      Alembic (esquema inicial)
  services/        reglas de negocio (equipos, clientes, alquileres, devoluciones, …)
  ai/              IA explicable (demanda, mantenimiento, retrasos, Text-to-SQL)
  ui/              interfaz PySide6 (logica/ sin Qt + vistas/ Qt)
tests/             ~460 pruebas (espejo de alquiler/)
docs/superpowers/  especificación y plan por fases
scripts/           empaquetado
```

El detalle de cada archivo está en [`PROJECT_INDEX.md`](PROJECT_INDEX.md).

## 10. Limitaciones conocidas

- Uso local y monousuario: una base SQLite por equipo, sin sincronización en red.
- Un equipo reservado para una fecha futura no se puede alquilar antes, aunque el alquiler termine
  a tiempo.
- La mora de un alquiler vencido aparece en *Reportes → Alquileres vencidos*. En *Alquileres*, el
  saldo solo la incluye cuando se registra la devolución.
- Las categorías con tildes en mayúscula ("ÁRBOLES" frente a "árboles") no se detectan como
  duplicadas.
- Si un reporte se genera mientras se guarda otra operación, SQLite puede esperar hasta 5 s por el
  bloqueo.
- La carga de datos demo en el primer arranque bloquea la ventana unos segundos (muestra un aviso).
- El tema visual es claro; no hay modo oscuro.
