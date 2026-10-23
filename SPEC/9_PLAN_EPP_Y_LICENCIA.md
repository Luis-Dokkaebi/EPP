# 9. PLAN: Migración de licencia del motor de IA + Módulo de verificación de EPP

**Estado:** Borrador para revisión humana
**Revisión:** 1
**Fecha:** 2026-10-21
**Preparado para:** Luis (dueño del producto)
**¿Requiere aprobación antes del trabajo riesgoso?:** Sí. El plan toca licencias, datos personales
(imágenes y rostros), el esquema de la base de datos, el formato de zonas y el build del ejecutable.
Las decisiones de la §4 deben resolverse antes de empezar las fases marcadas como bloqueadas.

## Registro de revisiones

| Rev | Fecha | Cambios | Motivo |
|-----|-------|---------|--------|
| 1 | 2026-10-21 | — | Borrador inicial a partir del análisis del video de referencia y del código actual |

---

## Índice

0. [Resumen ejecutivo](#0-resumen-ejecutivo)
1. [Qué hace el video de referencia](#1-qué-hace-el-video-de-referencia)
2. [Brecha: lo que existe y lo que falta](#2-brecha-lo-que-existe-y-lo-que-falta)
3. [Contexto: hechos, restricciones y supuestos](#3-contexto-hechos-restricciones-y-supuestos)
4. [Decisiones bloqueantes](#4-decisiones-bloqueantes)
5. [Cómo se trabaja: harness engineering + skills del repo](#5-cómo-se-trabaja-harness-engineering--skills-del-repo)
6. [Fase 0 — Harness: preparar el repo para agentes](#6-fase-0--harness-preparar-el-repo-para-agentes)
7. [Fase 1 — Migración de licencia (salir de Ultralytics)](#7-fase-1--migración-de-licencia-salir-de-ultralytics)
8. [Fase 2 — Contrato de ML y datos de EPP](#8-fase-2--contrato-de-ml-y-datos-de-epp)
9. [Fase 3 — Entrenamiento, evaluación y exportación del modelo EPP](#9-fase-3--entrenamiento-evaluación-y-exportación-del-modelo-epp)
10. [Fase 4 — Dominio de cumplimiento de EPP](#10-fase-4--dominio-de-cumplimiento-de-epp)
11. [Fase 5 — Integración en el pipeline de cámaras](#11-fase-5--integración-en-el-pipeline-de-cámaras)
12. [Fase 6 — Persistencia de infracciones y evidencias](#12-fase-6--persistencia-de-infracciones-y-evidencias)
13. [Fase 7 — Notificaciones al responsable de seguridad](#13-fase-7--notificaciones-al-responsable-de-seguridad)
14. [Fase 8 — Interfaz gráfica y reportes](#14-fase-8--interfaz-gráfica-y-reportes)
15. [Fase 9 — Build, piloto, operación y reversión](#15-fase-9--build-piloto-operación-y-reversión)
16. [Criterios de aceptación](#16-criterios-de-aceptación)
17. [Plan de PRs y orden de ejecución](#17-plan-de-prs-y-orden-de-ejecución)
18. [Riesgos](#18-riesgos)
19. [Plan de verificación](#19-plan-de-verificación)
20. [Fuentes](#20-fuentes)

---

## 0. Resumen ejecutivo

**Meta:** que nuestro sistema haga lo mismo que el video de AuraVision ("Aura EPP"). Una sola cámara
verifica, en tiempo real y por persona, si cada operario lleva su equipo de protección personal (EPP:
casco, chaleco o ropa reflectiva, guantes, gafas, barbijo). Si a alguien le falta un elemento, o
entra a una zona sin el EPP que esa zona exige, el sistema genera una alerta con la imagen del evento
y avisa al responsable de seguridad e higiene, sin que nadie tenga que mirar las cámaras.

**Por qué hay que cambiar la licencia primero:** hoy el motor de detección es Ultralytics (YOLOv8),
con licencia AGPL-3.0. Según la propia Ultralytics, tanto su código como **los modelos entrenados con
él** quedan bajo AGPL. Si no se publica todo el código del producto, hace falta su licencia
Enterprise, que es de pago. Entrenar un modelo EPP nuevo con Ultralytics agravaría el problema. Por eso
el plan primero migra el motor a una alternativa Apache-2.0 y después construye el EPP sobre esa base.

**Motor recomendado:** **RF-DETR** de Roboflow, solo en los tamaños con licencia Apache-2.0 (Nano,
Small, Medium y Large). Se entrena con su librería `rfdetr`, se exporta a ONNX y en el ejecutable
corre con **ONNX Runtime** (licencia MIT), sin PyTorch ni Ultralytics dentro del `.exe`. Las
alternativas, que se comparan en un benchmark, son **YOLOX** (Apache-2.0; muy liviano en CPU, pero
sin actividad desde 2023) y **D-FINE** (Apache-2.0; ojo con sus checkpoints de Objects365).

**Orden de trabajo (resumen):**

| Fase | Qué | Skills principales | Tamaño relativo |
|------|-----|--------------------|-----------------|
| 0 | Harness: puertas de calidad automáticas, hooks, CI, gate de licencias | `verify-and-stop`, `python-testing`, `update-config`, `session-start-hook` | M |
| 1 | Migrar el motor de IA a Apache/MIT detrás de un puerto | `migration`, `hexagonal-architecture`, `safe-refactor`, `benchmark-optimization-loop` | L |
| 2 | Contrato de ML y datos de EPP (taxonomía, licencias de datasets, etiquetado) | `mle-workflow`, `intent-driven-development` | M (más el tiempo de etiquetado) |
| 3 | Entrenar, evaluar y exportar el modelo EPP | `mle-workflow`, `benchmark-optimization-loop` | L |
| 4 | Dominio de cumplimiento EPP (puro, TDD, Gherkin) | `lean-build`, `hexagonal-architecture`, `python-testing`, `python-patterns` | M |
| 5 | Integración en el pipeline de cámaras | `safe-refactor`, `lean-build` | S |
| 6 | Persistencia de infracciones y evidencias | `migration`, `python-testing` | S |
| 7 | Notificaciones (outbox, reintentos) | `hexagonal-architecture`, `error-handling` | M |
| 8 | UI y reportes | `lean-build`, `windows-desktop-e2e` | M |
| 9 | Build, piloto en modo sombra, operación | `verify-and-stop`, `mle-workflow` | M |

Las fases 2 y 3 (datos y modelo) corren **en paralelo** con las fases 4 a 7. El dominio se construye
y prueba con dobles de prueba, sin modelo real, como exige `CLAUDE.md` §16.

---

## 1. Qué hace el video de referencia

Análisis cuadro por cuadro del video (`WhatsApp_Video_2026-10-21_at_2.59.12_PM.mp4`, 52 s, vertical
576×1280, publicación de `auravision_int`), en un sitio de perforación petrolera:

| # | Capacidad observada | Evidencia en el video |
|---|---------------------|-----------------------|
| C1 | Detecta y sigue a varias personas a la vez con una sola cámara | "8 personas, 5 elementos de protección, una sola cámara"; "monitorear hasta ocho operarios al mismo tiempo" |
| C2 | Detecta cada elemento de EPP como objeto propio | Cajas etiquetadas `Persona`, `Casco`, `Ropa`, `Guante` (más gafas y barbijo según la narración) |
| C3 | Verifica **por persona** qué elementos lleva | "verificar individualmente si cada persona está utilizando todos sus elementos de protección. Casco, chaleco reflectivo, barbijo, gafas, guantes" |
| C4 | Marca visualmente a quien incumple | La caja de la persona cambia de color (rojo o rosa) cuando falta un elemento |
| C5 | Detecta el **evento** "se quitó un elemento" | "Si un trabajador se quita un elemento…" |
| C6 | Reglas por zona: EPP exigido según el área | "…o ingresa a una zona sin el EPP correspondiente, Aura lo detecta automáticamente" |
| C7 | Genera una alerta con la imagen del evento | "puede generar una alerta con la imagen del evento" |
| C8 | Avisa en tiempo real al responsable, sin vigilancia humana | "sin que una persona tenga que estar mirando cámaras todo el día… darle al responsable de seguridad e higiene información en tiempo real" |

Propuesta de valor que repite el video: prevenir accidentes y mejorar el cumplimiento de las normas
de seguridad.

---

## 2. Brecha: lo que existe y lo que falta

### 2.1 Lo que ya existe y se reutiliza

| Pieza | Dónde | Cómo se reutiliza |
|-------|-------|-------------------|
| Captura multi-cámara (USB/RTSP), reconexión, descarte de frames sin fuga de memoria | `src/tracking/camera_worker.py` | Se conserva; solo se le inyecta un detector neutral (Fase 1) |
| Seguimiento con ID por persona (ByteTrack de `supervision`, licencia MIT) | `src/tracking/person_tracker.py` | Es la base para asociar el EPP a cada persona (C3) |
| Pipeline de negocio compartido entre la GUI y el modo headless (CR-04) | `src/tracking/tracking_pipeline.py` | Punto de integración del caso de uso EPP (Fase 5) |
| Zonas poligonales con Shapely y evento "entra a zona" con snapshot | `src/zones/zone_checker.py`, `tracking_pipeline.py:121` | Base de C6; se amplía el formato de zonas (Fase 6) |
| Base de datos SQLite cifrada y multi-tenant | `src/storage/database_manager.py`, `src/security/db_crypto.py` | Nueva tabla de infracciones (Fase 6) |
| Reconocimiento facial | `src/recognition/face_recognizer.py` | Mejora sobre el video: "Juan entró sin casco" en vez de "persona sin casco" |
| Verificación de integridad del modelo (SHA-256) | `src/models/model_verifier.py` | Se generaliza a un manifiesto de modelos (Fase 1) |
| Reportes Excel asíncronos | `src/analysis/` | Nuevo reporte de cumplimiento de EPP (Fase 8) |

### 2.2 Lo que falta

| # | Brecha | Detalle | Fase |
|---|--------|---------|------|
| B1 | **Infraestructura de calidad** | No existen `requirements-dev.txt`, `pyproject.toml` ni `features/`. `CLAUDE.md` exige TDD, Gherkin, cobertura y mutación, pero nada lo hace cumplir de forma automática | 0 |
| B2 | **Motor de IA con licencia AGPL** | `ultralytics==8.1.15` en `requirements.txt`; `YOLO(...)` en `src/main_ui.py:100`, `src/detection/person_detector.py:19` y `src/detection/people_detector.py:22`; `results[0].plot()` en `src/tracking/camera_worker.py:122`; `collect_all('ultralytics')` en `gui_app.spec:73` | 1 |
| B3 | **Modelo que entienda de EPP** | `yolov8n.pt` es un modelo COCO: conoce "persona" (clase 0) y "celular" (clase 67), pero no cascos, chalecos, guantes, gafas ni barbijos. Los IDs de clase de COCO están fijos en el código (`camera_worker.py:138`) | 2, 3 |
| B4 | **Asociar EPP a persona** | No existe lógica que diga "este casco pertenece a la persona #7" | 4 |
| B5 | **Ventana temporal contra falsas alarmas** | `StateManager` solo maneja actividad, celular y almuerzo. No hay máquina de estados de EPP con tolerancia a oclusiones | 4 |
| B6 | **EPP exigido por zona** | `zonas.json` es `{nombre: [puntos]}`, sin metadatos | 4, 6, 8 |
| B7 | **Eventos de infracción y evidencia anotada** | Solo se guarda un snapshot crudo al entrar a una zona | 6 |
| B8 | **Notificaciones externas** | No hay email, Telegram, WhatsApp ni webhook. Solo toasts de la UI para exportaciones | 7 |
| B9 | **UI de EPP** | No hay overlay por elemento, panel de alertas, configuración de EPP por zona ni reporte de cumplimiento | 8 |
| B10 | **Otras licencias a revisar** | `tkcalendar` es GPLv3 (`src/gui_app.py:42`). `face_recognition.face_landmarks` (`src/gui_app.py:707`) usa el modelo de 68 puntos de dlib, cuyo dataset de origen (iBUG 300-W) excluye el uso comercial (verificar en la auditoría). Hay que confirmar también la licencia comercial de PyArmor | 1 |

---

## 3. Contexto: hechos, restricciones y supuestos

Siguiendo la skill `intent-driven-development`, se separa lo verificado de lo que solo el negocio
puede decidir.

### 3.1 Hechos descubiertos (verificados en el repo o en fuentes oficiales)

- La aplicación es de escritorio para Windows, en Python 3.11, con GUI en customtkinter, DRM, base
  cifrada y multi-tenant (`CLAUDE.md` §16, `SPEC/1_SPECIFICATIONS.md`).
- El hardware objetivo declarado son máquinas Core i3/i5 sin GPU dedicada, con tope de 15 FPS por
  cámara (`SPEC/3_TASKS.md`, TASK-1.1.3).
- El SPEC exige operar de 1 a 16 cámaras (`SPEC/1_SPECIFICATIONS.md`).
- La inferencia ocurre una vez por frame en `CameraWorker.run()`, y el pipeline reutiliza ese
  resultado (`camera_worker.py:121-145`).
- Hoy se parchea `torch.load` para forzar `weights_only=False` al cargar YOLO (`src/main_ui.py:80-108`,
  CR-05). Es una superficie de deserialización insegura (pickle) que desaparece al pasar a ONNX.
- `src/detection/people_detector.py` solo aparece en `hiddenimports` de `gui_app.spec`; parece código
  muerto (confirmar en la Fase 1).
- Licencias verificadas en las fuentes oficiales (ver §20):
  - Ultralytics: AGPL-3.0; los modelos entrenados con su código también son AGPL; el uso comercial
    cerrado requiere la licencia Enterprise.
  - RF-DETR: la librería `rfdetr` y los tamaños Nano, Small, Medium y Large son Apache-2.0. Atto,
    Femto, Pico, XL y 2XL (detección) son **PML 1.0**: no usarlos.
  - D-FINE: Apache-2.0, pero los checkpoints entrenados con Objects365 pueden tener términos propios.
  - YOLOX: Apache-2.0, con exportación a ONNX y OpenVINO.
  - SH17 (dataset público de EPP, 8.099 imágenes, 17 clases): **CC BY-NC-SA 4.0, no comercial**.
    No sirve para entrenar un modelo que se vende.
  - tkcalendar 1.6.1: GPLv3.

### 3.2 Restricciones de producto o negocio (las tiene que dar el usuario; no se infieren del código)

- Ninguna suministrada todavía. Ver las decisiones de la §4.

### 3.3 Supuestos (a confirmar)

- S1: El EPP se ofrece como un módulo nuevo del mismo ejecutable. Si fuera un producto aparte, ver D10.
- S2: El primer cliente es industrial (petróleo, construcción o planta), con cámaras fijas a una
  distancia parecida a la del video.
- S3: Se puede acceder a cámaras reales de un cliente piloto para capturar y etiquetar imágenes.
- S4: Se acepta una latencia de alerta de algunos segundos (la ventana de confirmación), no instantánea.
- S5: La conectividad a internet del sitio puede ser intermitente.

---

## 4. Decisiones bloqueantes

Ninguna fase marcada como **[BLOQUEADA por Dx]** debe empezar sin la respuesta correspondiente.

| ID | Decisión | Opciones | Bloquea | Recomendación |
|----|----------|----------|---------|---------------|
| D1 | Canal de notificación al responsable | Email (SMTP), Telegram, WhatsApp Business Cloud API, webhook genérico | Fase 7 | Empezar con **email + webhook**, o Telegram (gratis y simple). WhatsApp después: exige verificación del negocio, plantillas aprobadas y costo por conversación |
| D2 | Hardware real de los sitios | Solo CPU (i3/i5), CPU Intel con OpenVINO, GPU NVIDIA | Fase 1 (benchmark), Fase 3 (tamaño del modelo) | Medir en el equipo real del piloto antes de elegir el tamaño del modelo |
| D3 | Elementos de EPP del piloto y reglas por zona | Los 5 del video u otro subconjunto | Fase 2 | Empezar con **casco + chaleco** (objetos grandes y más fáciles); sumar guantes, gafas y barbijo en una segunda iteración |
| D4 | Presupuesto de errores | ¿Qué es peor: una falsa alarma o una infracción no detectada? ¿Cuántos segundos de confirmación se aceptan? | Fases 3 y 4 (umbrales) | Lo decide el negocio; ver §9.3 |
| D5 | Privacidad y retención de las evidencias | Días de retención, difuminado de rostros, quién accede, consentimiento, jurisdicción | Fases 2, 6 y 7 | Lo decide el negocio, con asesoría legal |
| D6 | Origen y presupuesto de los datos de entrenamiento | Cámaras del cliente, datasets con licencia comercial, quién etiqueta, herramienta | Fase 2 | Datos propios del cliente piloto + CVAT o Label Studio autoalojados |
| D7 | Confirmar la migración frente a comprar Ultralytics Enterprise | Migrar (este plan) o pagar la licencia | Fase 1 | Migrar: sin costo recurrente y con un `.exe` más chico. Pedir de todos modos una cotización a Ultralytics como dato |
| D8 | Autorización para tocar el build y borrar binarios | `gui_app.spec`, `compilar_exe.bat`, `obfuscate.py`, `setup_oficina.iss`, `yolov8n.pt` | Fases 1.10 y 9 | `CLAUDE.md` §14.12 y §16 exigen instrucción explícita |
| D9 | Revisión legal de licencias antes del release | Abogado propio o externo | Fase 9 (release) | Obligatoria; este plan no es asesoría legal |
| D10 | ¿El EPP es un módulo del producto de oficina o un producto industrial aparte? | Mismo `.exe` con módulo activable o un producto separado | Fases 8 y 9 | Mismo código base con el módulo activable por licencia DRM |

---

## 5. Cómo se trabaja: harness engineering + skills del repo

### 5.1 Qué es harness engineering y por qué aplica aquí

"Harness engineering" es la disciplina de diseñar el **entorno** donde trabajan los agentes de
código (instrucciones, herramientas, pruebas, linters, hooks, CI, documentación) para que puedan
producir código confiable sin que un humano lo lea línea por línea. OpenAI lo describió en
"Harness engineering: leveraging Codex in an agent-first world" (febrero de 2026): los humanos
dirigen y los agentes ejecutan, la documentación del repo es la fuente de verdad, y la arquitectura se
hace cumplir con reglas mecánicas y pruebas estructurales, no con prosa. La idea de Mitchell
Hashimoto lo resume: **cada vez que un agente se equivoca, se invierte tiempo en que el entorno haga
imposible repetir ese error.**

Es exactamente la premisa de nuestro `CLAUDE.md` ("el humano no va a leer el código; la confianza se
gana superando todas las puertas"). Pero hoy esa constitución es **prosa sin dientes**: no hay
`pyproject.toml`, ni `requirements-dev.txt`, ni hooks, ni CI que la hagan cumplir. La Fase 0 le pone
dientes.

### 5.2 Principios de harness que sigue este plan

| # | Principio | Cómo se materializa en este repo |
|---|-----------|----------------------------------|
| H1 | El repo es el sistema de registro | `SPEC/` (este plan), `docs/adr/` (decisiones), `docs/ml/` (contratos y bitácora del modelo), `docs/quality/` (waivers, mutantes equivalentes, lecciones). `CLAUDE.md` funciona como mapa, no como enciclopedia: se agrega `docs/README.md` como índice |
| H2 | Reglas mecánicas antes que prosa | Toda regla de `CLAUDE.md` que una herramienta pueda verificar, la verifica una herramienta: ruff, mypy, import-linter (capas), gate de licencias, chequeo de gemelos `CLAUDE.md`/`Agents.md`, bloqueo de archivos protegidos |
| H3 | Errores que enseñan | Los checks propios imprimen **cómo arreglar** el problema (por ejemplo: "`src/ppe/domain` no puede importar `cv2`: recibe la imagen a través de `AlmacenEvidenciasPort`"), para que el agente se autocorrija |
| H4 | Bucle de retroalimentación rápido | Hook de Claude Code que formatea y lintea cada archivo editado; subconjunto de pruebas rápidas de menos de 60 s; un único comando `scripts/quality_gate.sh` que corre la §10 de `CLAUDE.md` completa |
| H5 | Legibilidad para el agente | Logs estructurados (`logging`, no `print`) en los módulos nuevos; herramienta de *replay* que corre el pipeline headless sobre un clip grabado y emite eventos JSON; frames anotados guardados como artefactos de CI |
| H6 | Error del agente → mejora del harness | `docs/quality/lecciones_agentes.md`: cada error recurrente se convierte en un lint, un test o un hook |
| H7 | Recolección de entropía | Tarea programada semanal (un agente) que busca código muerto, docs desactualizadas, waivers vencidos y regresiones de métricas; el trinquete de métricas vive en `docs/quality/metricas.json`, actualizado por CI |
| H8 | Entornos aislados y reproducibles | Hook `SessionStart` para sesiones en la nube que instala las dependencias compatibles con Linux; lo exclusivo de Windows queda detrás de adaptadores, así el dominio se prueba en Linux |

### 5.3 Mapa de skills del repo (`.claude/skills/`) por fase

| Skill | Para qué se usa en este plan | Fases |
|-------|------------------------------|-------|
| `intent-driven-development` | Criterios de aceptación observables (AC-NNN), separación de hechos y supuestos, decisiones bloqueantes. Ya aplicada en este documento | Todas |
| `lean-build` | Construir cada rebanada de funcionalidad completa pero sin sobre-ingeniería; no-objetivos explícitos y condición de parada | 4, 5, 7, 8 |
| `migration` | Migración del motor y del formato de zonas: expandir → migrar → verificar → contraer, con ruta de reversión | 1, 6, 8 |
| `safe-refactor` | Extraer el puerto `DetectorPort` de `CameraWorker` sin cambiar el comportamiento, con pruebas de caracterización antes | 1, 5 |
| `hexagonal-architecture` | Puertos y adaptadores: detector, notificador, almacén de evidencias, reloj, repositorio. Raíz de composición única | 1, 4, 7 |
| `benchmark-optimization-loop` | Comparar motores y tamaños de modelo con una bitácora de variantes y una puerta de promoción | 1, 3 |
| `mle-workflow` | *Iteration Compact*, contrato de datos, splits sin fuga, puertas de promoción, bitácora de observaciones, modelo en modo sombra, monitoreo | 2, 3, 9 |
| `python-testing` | TDD con pytest, fixtures, parametrize, mocks de colaboradores (nunca de la unidad bajo prueba) | Todas las de código |
| `python-patterns` | Tipado, dataclasses inmutables, `Protocol` para los puertos | 1, 4 |
| `error-handling` | Excepciones tipadas por dominio, reintentos con backoff, circuit breaker para notificaciones | 7 |
| `windows-desktop-e2e` | E2E de la GUI con pywinauto. Ojo: la skill apunta a WPF, WinForms, Win32 y Qt; customtkinter (Tk) expone poco árbol de UI Automation, así que el E2E será de humo y la lógica vivirá en presentadores probados con pytest | 8, 9 |
| `investigate-first` | Diagnosticar antes de editar (por ejemplo, caídas de FPS o falsas alarmas en el piloto) | 3, 9 |
| `surgical-patch` | Corregir bugs encontrados durante la migración en la capa más angosta, con un test de regresión | 1, 9 |
| `verify-and-stop` | Cierre de cada fase: demostrar los AC con la evidencia mínima suficiente y parar | Todas |
| `cavecrew` + subagentes `cavecrew-investigator` / `cavecrew-reviewer` | Localizar código y revisar diffs sin gastar contexto del hilo principal | Todas |
| `caveman-review` | Revisión compacta del diff antes de abrir cada PR | Todas |

Skills de entorno (no del repo, disponibles en Claude Code) que también se usan: `update-config`
(hooks en `.claude/settings.json`), `session-start-hook` (preparar sesiones en la nube),
`security-review` (cambios en `src/security/` y notificaciones) y `code-review`.

### 5.4 Reglas de ejecución para cualquier agente

1. Una subtarea = un ciclo TDD (§2 de `CLAUDE.md`): rojo (pegar la salida) → verde → refactor → gate → commit.
2. Cada PR mide 400 líneas de diff o menos (§13) y lleva la plantilla de PR con la evidencia real del gate.
3. `CLAUDE.md` y `Agents.md` se cambian juntos y quedan idénticos byte a byte.
4. Nada de `skip`, `noqa`, `type: ignore` ni `pragma: no cover` sin waiver aprobado (§15).
5. Los archivos de build y los binarios no se tocan sin la autorización D8.
6. Al cerrar cada fase se aplica `verify-and-stop` y se marca la casilla en este documento.

---

## 6. Fase 0 — Harness: preparar el repo para agentes

**Objetivo:** que toda regla verificable de `CLAUDE.md` se haga cumplir de forma automática en local,
en los hooks del agente y en CI, antes de escribir código de producto.

**No-objetivos:** arreglar todo el código heredado. Se mide una línea base y la deuda se gestiona con
waivers aprobados por un humano.

### 0.1 Dependencias de desarrollo fijadas

- Crear `requirements-dev.txt` con las versiones del Apéndice A de `CLAUDE.md`, más:
  - `pip-licenses` (gate de licencias),
  - `import-linter` (contratos de capas),
  - `diff-cover` (cobertura del diff ≥ 95 %),
  - `pytest-bdd` (ya está en el Apéndice A).
- Marcar las dependencias exclusivas de Windows en `requirements.txt` con marcadores de entorno
  (`wmi==1.5.1; sys_platform == "win32"`), para que el CI en Linux pueda instalar.
- Fijar las dependencias sin versión que hoy tiene `requirements.txt` (`face_recognition`, `numpy`,
  `pillow`, `matplotlib`, `seaborn`, `tkcalendar`). §14.11 prohíbe dependencias sin fijar.
- Correr `pip-audit` sobre ambos archivos.
- **Commit:** `build(deps): fijar dependencias de desarrollo y marcadores de plataforma`.

### 0.2 Configuración de herramientas (`pyproject.toml`)

- Crear `pyproject.toml` con la configuración del Apéndice A (ruff, mypy, pytest, coverage).
- Registrar los marcadores de pytest: `unit`, `bdd`, `integration` (I/O real en `tmp_path`), `slow`
  y `windows` (solo en Windows).
- **Línea base:** correr ruff, mypy y radon sobre el código actual y guardar el resultado en
  `docs/quality/linea_base_2026-10.md`. **No se agregan exclusiones**: si el código heredado no pasa,
  se proponen waivers por archivo en `docs/quality/waivers.md` (§15) y **se esperan las aprobaciones**.
  Mientras tanto, el gate se aplica estricto a los paquetes nuevos y al diff de cada PR (`diff-cover`,
  ruff sobre los archivos cambiados).
- **Commit:** `build(calidad): añadir pyproject con configuración de ruff, mypy, pytest y coverage`.

### 0.3 Un único comando para el Quality Gate

- `scripts/quality_gate.sh` (Linux/CI) y `scripts/quality_gate.ps1` (Windows) corren los pasos 0 a 8
  de la §10 en orden, se detienen al primer fallo y guardan cada salida en `reports/gate/<paso>.txt`
  (ignorado por git), lista para pegar en el PR.
- Opción `--changed` que limita la mutación a los archivos tocados (`mutmut run --paths-to-mutate`).
- Test del script: un test de humo que verifica que el script devuelve un código distinto de 0 cuando
  un paso falla (con una herramienta falsa en el `PATH`).

### 0.4 Arquitectura verificada por máquina (import-linter)

Archivo `.importlinter` con contratos que hacen cumplir la §16 de `CLAUDE.md`:

```ini
[importlinter]
root_packages = src

[importlinter:contract:dominio-sin-detalles]
name = El dominio no importa GUI, visión ni motores de IA
type = forbidden
source_modules =
    src.zones
    src.analysis
    src.storage
    src.ppe.domain
    src.ppe.application
    src.alerts.domain
forbidden_modules =
    cv2
    ultralytics
    torch
    onnxruntime
    rfdetr
    customtkinter
    src.gui

[importlinter:contract:capas]
name = Las dependencias apuntan hacia adentro
type = layers
layers =
    src.gui
    src.tracking
    src.ppe.application | src.alerts.application
    src.ppe.domain | src.alerts.domain
```

- **Prerrequisito:** unificar los imports con el prefijo `src.`. Hoy `src/main.py` importa
  `from zones.zone_checker import ...` y `tests/conftest.py` agrega `src/` al `sys.path`, así que
  import-linter no vería esas dependencias. Se hace en un commit de refactor aparte, con la suite en
  verde antes y después.
- El primer resultado sobre el código actual va a la línea base. Ejemplo: `tracking_pipeline.py`
  importa `cv2` dentro de `_save_snapshot_event`; ver si viola el contrato o queda en la capa de
  adaptadores.
- Un script envoltorio `scripts/check_architecture.py` traduce cada violación a un mensaje con la
  corrección sugerida (H3).

### 0.5 Gate de licencias (impide que vuelva la AGPL)

- `scripts/check_licenses.py`, con su test:
  - Corre `pip-licenses --format=json` sobre el entorno de **runtime** (no el de desarrollo ni el de
    entrenamiento).
  - **Lista permitida:** MIT, BSD-2/3-Clause, Apache-2.0, ISC, PSF, BSL-1.0, HPND, CC0, Unlicense,
    Zlib.
  - **Revisión humana obligatoria:** LGPL, MPL-2.0, licencias desconocidas o vacías.
  - **Lista prohibida:** AGPL, GPL (cualquier versión), SSPL, CC-BY-NC*, PML, "Commercial" sin
    contrato registrado.
- **Manifiesto de modelos:** `models/manifest.json`. Por cada artefacto de modelo: nombre, versión,
  sha256, licencia de los pesos, licencia del código de entrenamiento, datasets usados con su licencia,
  clases y tamaño de entrada. El gate falla si un archivo `.onnx`/`.pt` en `models/` no está en el
  manifiesto, si el hash no coincide o si alguna licencia está en la lista prohibida.
- Corre en pre-commit y en CI.

### 0.6 Hooks de Claude Code (`.claude/settings.json`, skill `update-config`)

| Evento | Matcher | Acción | Por qué |
|--------|---------|--------|---------|
| `PostToolUse` | `Edit\|Write` sobre `*.py` | `ruff format <archivo>` + `ruff check --fix <archivo>` y devolver los hallazgos restantes | Bucle rápido (H4) |
| `PreToolUse` | `Bash` | Bloquear `git commit --no-verify`, `git push --force` (sin `--force-with-lease`) y `pip install` de paquetes sin versión | §12 y §14.9/§14.11 |
| `PreToolUse` | `Edit\|Write` | Bloquear `gui_app.spec`, `compilar_exe.bat`, `obfuscate.py`, `setup_oficina.iss`, `*.pt`, `*.onnx`, `*.xlsx` y `*.whl` salvo autorización explícita en la sesión | §14.12 y §16 |
| `Stop` | — | `cmp CLAUDE.md Agents.md` + pruebas rápidas (`pytest -q -m "unit and not slow" -x`) | §14.13 y Ley Cero |
| `SessionStart` | sesiones en la nube (skill `session-start-hook`) | Instalar Python 3.11 (vía `uv`) y `requirements-ci.txt` (sin dependencias de Windows ni del build) | H8 |

- Mantener el plugin habilitado actual (`superpowers@claude-plugins-official`).
- Los hooks deben terminar en pocos segundos; las pruebas pesadas van a CI, no al hook.

### 0.7 pre-commit (`.pre-commit-config.yaml`)

- ruff format, ruff check, detect-secrets, chequeo de gemelos (`cmp CLAUDE.md Agents.md`), gate de
  licencias, import-linter y chequeo de tamaño de archivo (500 líneas o menos en los módulos nuevos).
- `pre-commit install` documentado en el README de desarrollo.

### 0.8 CI en GitHub Actions (`.github/workflows/quality-gate.yml`)

- **Matriz:** `windows-latest` y `ubuntu-latest`, ambos con Python 3.11.
- **Jobs:**
  1. `gate`: el script de la §0.3 (sin mutación) más `diff-cover coverage.xml --fail-under=95`.
  2. `licencias`: gate de licencias en un entorno limpio con solo `requirements.txt`.
  3. `mutacion`: mutmut sobre los archivos cambiados en el PR, y nocturno sobre los módulos críticos.
  4. `replay` (desde la Fase 5): corre la herramienta de replay sobre los clips dorados y compara los
     eventos con los esperados.
- Artefactos: `coverage.xml`, los reportes del gate y los frames anotados del replay.
- Rama `main` protegida: merge solo con CI en verde.

### 0.9 Documentación como sistema de registro

- `docs/README.md`: índice de toda la documentación (mapa para el agente).
- `docs/adr/`: plantilla de ADR. Las primeras son ADR-001 "Motor de IA Apache/MIT" y ADR-002
  "Asociación EPP–persona por anclas corporales".
- `docs/quality/`: `waivers.md`, `mutantes_equivalentes.md`, `lecciones_agentes.md` y `metricas.json`.
- Proponer (en un PR aparte, porque modifica la constitución) actualizar la §16 de `CLAUDE.md` y
  `Agents.md` con los paquetes nuevos (`src/inference/`, `src/ppe/`, `src/alerts/`), y la §6/§7 para
  declarar `src/ppe/` como módulo crítico (el trinquete solo permite subir exigencias).

### 0.10 Arnés de pruebas para visión (sin modelos reales)

- `tests/fixtures/vision/`: frames sintéticos pequeños (numpy generado en la fixture) y detecciones
  pregrabadas en JSON.
- `tools/replay.py`: corre `TrackingPipeline` y el caso de uso EPP en modo headless sobre un video
  más un archivo de detecciones pregrabadas. Emite los eventos en JSON Lines. Sirve para regresión de
  punta a punta sin cargar modelos (§16: "un test unitario jamás carga un modelo").
- "Eventos dorados": por cada clip de referencia, un archivo `*.expected.jsonl` revisado por un humano.

### DoD de la Fase 0

- [ ] `scripts/quality_gate.sh` corre de punta a punta en CI (Linux y Windows) y su salida queda como artefacto.
- [ ] El gate de licencias **falla hoy** sobre `requirements.txt` porque detecta `ultralytics` (AGPL) y `tkcalendar` (GPLv3). Esto demuestra que el gate muerde; la Fase 1 lo pone en verde.
- [ ] import-linter corre, y sus violaciones actuales están en la línea base con un waiver propuesto.
- [ ] Hooks de Claude Code activos y probados: un intento de `git commit --no-verify` queda bloqueado.
- [ ] Waivers del código heredado propuestos y **aprobados por un humano**.

---

## 7. Fase 1 — Migración de licencia (salir de Ultralytics)

**Objetivo:** que el ejecutable detecte personas (y celulares) con un motor de licencia Apache/MIT,
sin Ultralytics ni PyTorch en runtime, y con una precisión no peor que la actual.

**Skills:** `migration` (expandir → migrar → verificar → contraer), `safe-refactor`,
`hexagonal-architecture`, `benchmark-optimization-loop`, `surgical-patch`.

**No-objetivos:** detectar EPP (Fase 3), cambiar el tracker (se mantiene ByteTrack de `supervision`,
licencia MIT) y cambiar el reconocimiento facial salvo por su licencia.

### 1.1 Auditoría completa de licencias

- En un Windows limpio con `requirements.txt`, correr `pip-licenses --with-urls --format=markdown`.
- Guardar el resultado en `docs/legal/licencias_dependencias.md` con una columna "acción".
- Puntos ya identificados, a confirmar con la auditoría:

| Componente | Licencia | Acción |
|------------|----------|--------|
| `ultralytics` + `yolov8n.pt` | AGPL-3.0 | **Reemplazar** (esta fase) |
| `tkcalendar` | GPLv3 | **Reemplazar** (§1.11) |
| Modelo de 68 puntos de dlib (vía `face_recognition.face_landmarks`, `src/gui_app.py:707`) | Dataset iBUG 300-W con exclusión de uso comercial (verificar) | Evaluar usar el modelo de 5 puntos o eliminar esa función |
| `pyarmor` | Comercial | Confirmar que existe una licencia comprada para uso comercial |
| `pyinstaller` | GPL con excepción del bootloader | Permitido para distribuir binarios (verificar la versión) |
| `supervision`, `customtkinter`, `face_recognition`, `openpyxl`, `wmi` | MIT | Ok |
| `opencv-python-headless`, `cryptography` | Apache-2.0 (cryptography también BSD) | Ok; conservar los avisos (NOTICE) |
| `shapely`, `numpy`, `pandas`, `seaborn` | BSD | Ok |
| `dlib` | BSL-1.0 | Ok |
| `onnxruntime` (nuevo) | MIT | Ok |
| `rfdetr` (solo entrenamiento, fuera del `.exe`) | Apache-2.0 | Ok; usar solo los tamaños Apache |

### 1.2 ADR-001: elección del motor

- Documentar en `docs/adr/001-motor-ia.md`:
  - el contexto (AGPL, el ejecutable cerrado, la CPU i3/i5),
  - las opciones (Ultralytics Enterprise, RF-DETR, YOLOX, D-FINE),
  - la decisión **provisional** (RF-DETR + ONNX Runtime) a confirmar con el benchmark de la §1.5,
  - las consecuencias y la reversión.

### 1.3 EXPANDIR: introducir un puerto de detección (sin cambiar el comportamiento)

**1.3.1 Pruebas de caracterización primero** (`safe-refactor`):

- `tests/test_camera_worker_characterization.py`. Con un modelo falso (doble del colaborador), fijar
  lo que hoy hace `CameraWorker.run()`:
  - encola un frame anotado por frame leído,
  - llama a `pipeline.process` con las detecciones de clase 0 y los celulares de clase 67,
  - descarta frames cuando la cola está llena,
  - aborta si el modelo no pasó la verificación.
- Estas pruebas deben pasar **antes y después** de cada paso de la migración.

**1.3.2 Tipos neutrales** en `src/inference/types.py`:

```python
@dataclass(frozen=True)
class Caja:
    x1: float
    y1: float
    x2: float
    y2: float  # se valida en __post_init__: x2 > x1, y2 > y1


class ClaseObjeto(StrEnum):
    PERSONA = "persona"
    CELULAR = "celular"
    # Se amplía en la Fase 3: CABEZA, MANOS, CASCO, CHALECO, GUANTES, GAFAS, BARBIJO


@dataclass(frozen=True)
class Deteccion:
    clase: ClaseObjeto
    confianza: float  # entre 0 y 1, validado
    caja: Caja
```

- **Por qué nombres semánticos y no IDs:** hoy el código usa los IDs de COCO (0 = persona,
  67 = celular). El modelo EPP tendrá IDs distintos. Un catálogo de clases por modelo
  (`ClassCatalog`, leído del manifiesto) traduce de ID a `ClaseObjeto`, y el resto del sistema deja de
  depender del orden de clases de un dataset.

**1.3.3 Puerto** en `src/inference/ports.py`:

```python
class DetectorPort(Protocol):
    def detectar(self, frame: np.ndarray) -> list[Deteccion]: ...
```

**1.3.4 Adaptador temporal** `src/inference/adapters/ultralytics_detector.py`:

- Envuelve el `YOLO` actual y traduce sus resultados a `Deteccion`.
- Permite migrar los consumidores sin cambiar de motor todavía.
- Pruebas: con un doble del modelo de Ultralytics (colaborador), verificar el mapeo de IDs a clases y
  el filtro por confianza.

**1.3.5 Refactor de consumidores** (un commit por consumidor, con las pruebas de caracterización en verde):

- `CameraWorker` recibe un `DetectorPort` en lugar del `model` crudo.
- `results[0].plot()` se reemplaza por un `AnotadorDeFrames` propio en `src/tracking/annotator.py`
  (dibujo con cv2 en la capa de adaptadores).
- La conversión `Deteccion` → `sv.Detections` para ByteTrack vive en `src/tracking/person_tracker.py`.
- `src/main.py` y `src/detection/person_detector.py` pasan a usar el puerto.
- `src/detection/people_detector.py`: si se confirma que es código muerto, se elimina en un commit
  aparte (`refactor(detection): eliminar PeopleDetector sin uso`). Quitarlo de `hiddenimports`
  requiere la autorización D8.

**1.3.6 Raíz de composición única** en `src/composition.py`:

- Una función `crear_detector(config) -> DetectorPort` que usan tanto `main_ui.py` como `main.py`.
- Es la lección de CR-04: nunca dos caminos divergentes.

### 1.4 Adaptador ONNX Runtime

- `src/inference/adapters/onnx_detector.py`:
  - Carga `InferenceSession` con proveedores configurables: `CPUExecutionProvider` por defecto;
    `DmlExecutionProvider` (onnxruntime-directml) u `OpenVINOExecutionProvider` según D2.
  - **Preprocesamiento:** BGR → RGB, redimensión al tamaño de entrada del manifiesto, normalización
    con la media y desviación declaradas en el manifiesto, NCHW float32.
  - **Postprocesamiento:** salida del modelo (cajas + logits para RF-DETR/D-FINE; cajas + objectness
    para YOLOX) → umbral de confianza → reescalado a coordenadas del frame → `Deteccion`. Los
    detectores tipo DETR no requieren NMS; YOLOX sí.
- **Pruebas unitarias:** `InferenceSession` es colaborador y se reemplaza por un doble que devuelve
  tensores sintéticos conocidos. Se verifican el reescalado, los umbrales, las cajas degeneradas, la
  salida vacía y el mapeo de clases.
- **Prueba de integración** (`@pytest.mark.slow`, solo en CI): un modelo ONNX diminuto generado en la
  fixture (no un modelo real de varios MB) para validar el contrato de entrada y salida.

### 1.5 Benchmark de motores (`benchmark-optimization-loop`)

- Script `tools/bench_detectores.py`: corre cada variante sobre el **mismo** clip de validación del
  cliente y mide:
  - FPS sostenidos por cámara, latencia p50/p95 y RAM;
  - recall y precisión de **persona** sobre un set de validación etiquetado (de 200 a 500 frames del
    sitio piloto);
  - tamaño del `.exe` resultante (estimado).
- Bitácora en `docs/benchmarks/motor_ia.md`:

```text
Variante          | Hipótesis                       | Hardware | FPS | p95 ms | RAM | Recall persona | ¿Pasa? | Notas
baseline-yolov8n  | estado actual (AGPL)            | i5 CPU   |     |        |     |                | ref    |
rfdetr-nano-onnx  | más preciso en objetos chicos   | i5 CPU   |     |        |     |                |        |
rfdetr-small-onnx | equilibrio                      | i5 CPU   |     |        |     |                |        |
yolox-tiny-onnx   | el más liviano en CPU           | i5 CPU   |     |        |     |                |        |
yolox-s-onnx      | YOLO clásico Apache             | i5 CPU   |     |        |     |                |        |
dfine-n-onnx      | DETR en tiempo real (pesos COCO)| i5 CPU   |     |        |     |                |        |
```

- **Puerta de promoción** (valores a fijar con D2 y D4, **antes** de correr el benchmark):
  - recall de persona mayor o igual al del baseline;
  - FPS de al menos 10 por cámara con N cámaras simultáneas en el hardware objetivo;
  - p95 por debajo del presupuesto por frame.
- Los números se publican solo si vienen de corridas reales; no se redondean ni se inventan.

### 1.6 Modelo de personas con el motor nuevo

- Mientras no exista el modelo EPP, usar los pesos COCO preentrenados del motor ganador (RF-DETR
  Nano/Small, Apache-2.0), que incluyen persona y celular.
- Exportarlos a ONNX (`pip install "rfdetr[onnx]"`, `model.export()`) y registrarlos en
  `models/manifest.json`.

### 1.7 MIGRAR: interruptor de motor durante la transición

- `config.DETECTION_ENGINE = "onnx" | "ultralytics"`. Por defecto `"onnx"` después de pasar la
  puerta de la §1.5. Sirve **solo** como ruta de reversión durante la transición y se elimina en la
  §1.10.
- Prueba: la raíz de composición devuelve el adaptador correcto para cada valor y falla ruidosamente
  (excepción tipada) ante un valor desconocido.

### 1.8 Verificador de modelos generalizado

- `src/models/model_verifier.py` pasa de un hash fijo (`EXPECTED_MODEL_SHA256`) a validar contra
  `models/manifest.json`.
- El manifiesto se firma o se embebe en bytecode ofuscado, igual que hoy, para conservar el
  anti-tamper de TASK-5.2.
- Pruebas: manifiesto ausente, hash distinto, modelo no listado y manifiesto manipulado. Todas fallan
  cerrado (el tracking no arranca), como hoy.
- Ampliar `tests/test_model_verifier.py`; es un módulo de seguridad: mutación de al menos 90 %.

### 1.9 Retirar el parche inseguro de `torch.load`

- Con ONNX no hay deserialización pickle. Eliminar el bloque de CR-05 en `src/main_ui.py:80-108` y la
  precarga de `torch` en `src/gui_app.py:27-33`.
- Prueba de regresión: arrancar la composición de la GUI con un detector falso no importa `torch`
  (verificar que `"torch" not in sys.modules`).

### 1.10 CONTRAER (requiere D8)

- Quitar `ultralytics` de `requirements.txt`; agregar `onnxruntime` con versión fijada y pasar
  `pip-audit`.
- Eliminar el adaptador de Ultralytics y el interruptor `DETECTION_ENGINE`.
- Borrar `yolov8n.pt` (raíz) y `models/yolov8/yolov8n.pt`. Son binarios: requieren instrucción
  explícita.
- `gui_app.spec`: quitar `ultralytics` (`hiddenimports` y `collect_all`) y `torch`; agregar
  `onnxruntime` y el modelo `.onnx` como `datas`. Documentar la prueba de humo del ejecutable en el PR.
- El gate de licencias pasa a verde.

### 1.11 Reemplazar `tkcalendar` (GPLv3)

- Opción preferida: un selector de fecha propio y mínimo con customtkinter (MIT), con validación de
  formato y pruebas del presentador.
- Alternativa: otro componente con licencia permisiva verificada.
- Un solo PR, con prueba de humo manual de la vista de reportes.

### 1.12 Avisos de terceros

- `docs/legal/THIRD_PARTY_NOTICES.txt` generado por script desde `pip-licenses` más el manifiesto de
  modelos. Apache-2.0 exige conservar los avisos de atribución.
- Se incluye en el instalador (`setup_oficina.iss`, requiere D8).

### Ruta de reversión de la Fase 1

- Hasta la §1.10, cambiar `DETECTION_ENGINE` a `"ultralytics"` revierte sin redeploy de código.
- Después de la §1.10, reinstalar la versión anterior del instalador (se conserva el artefacto de la
  versión 1.3.0).

### DoD de la Fase 1

- [ ] Las pruebas de caracterización de `CameraWorker` pasan antes y después.
- [ ] La bitácora del benchmark tiene números reales y el ganador pasa la puerta.
- [ ] `pip-licenses` sobre el runtime: 0 paquetes AGPL o GPL. Gate en verde.
- [ ] El ejecutable arranca, detecta personas y persiste el tracking sin `ultralytics` ni `torch` instalados (prueba de humo documentada).
- [ ] `models/manifest.json` declara origen, licencia y hash del modelo distribuido.
- [ ] ADR-001 cerrada con la decisión final.

---

## 8. Fase 2 — Contrato de ML y datos de EPP

**Skills:** `mle-workflow` (Iteration Compact y contrato de datos), `intent-driven-development`.
**[BLOQUEADA por D3, D5 y D6]**

### 2.1 Iteration Compact (borrador, a completar con el usuario)

```text
Goal: detectar, por persona y en tiempo real, la ausencia de cada elemento de EPP exigido.
Who cares: responsable de seguridad e higiene; operarios; dirección (cumplimiento legal).
Decision owner: responsable de seguridad e higiene del sitio.
User or system action changed by the model: se genera una alerta y se registra una infracción.
Success metric: recall de infracciones reales a nivel evento (ver §9.3), medido en los videos dorados.
Guardrail metrics: falsas alarmas por cámara y por hora; FPS por cámara; latencia de la alerta.
Mistake budget: POR DEFINIR (D4).
Unacceptable mistakes: no alertar a alguien sin casco en una zona de riesgo durante más de T segundos.
Acceptable mistakes: estado "no verificable" cuando la cabeza o las manos no se ven.
Assumptions: cámaras fijas; operarios a una distancia parecida a la del video; luz diurna.
Constraints: CPU i3/i5 (por confirmar con D2); ejecutable cerrado; licencias permisivas.
Labels and data snapshot: dataset propio del piloto, versión v0.1 (por crear).
Baseline: RF-DETR Small, ajuste fino solo sobre casco y chaleco.
Candidate signals: cajas de EPP + anclas corporales (cabeza, manos) + track_id + zona.
Threshold or config plan: umbral por clase elegido en validación, nunca en test.
Eval slices: distancia (persona chica o grande), iluminación, oclusión, cámara, color del EPP.
Known risks: oclusión, casco en la mano, EPP de colores raros, aglomeraciones.
Next experiment: medir el recall de casco por slice de distancia.
Rollback or fallback: modelo anterior del manifiesto; módulo EPP desactivable.
```

### 2.2 Taxonomía de clases

| Clase | Uso | Nota |
|-------|-----|------|
| `persona` | Seguimiento y dueño del EPP | Ya existe |
| `cabeza` | **Ancla** para casco, gafas y barbijo | Permite afirmar "sin casco" solo cuando la cabeza se ve |
| `manos` | **Ancla** para guantes | Ídem |
| `casco` | EPP | Con casco en la cabeza, no en la mano (ver la guía de etiquetado) |
| `chaleco` | EPP (chaleco o ropa reflectiva; el video lo llama "Ropa") | Decidir con D3 si chaleco y mameluco reflectivo son una clase o dos |
| `guantes` | EPP | Objeto chico: exige resolución |
| `gafas` | EPP | Objeto chico y transparente: el más difícil |
| `barbijo` | EPP | Barbijo o mascarilla |

**Decisión de diseño (ADR-002): detectar anclas corporales en lugar de clases "sin-X".**
Entrenar clases negativas ("cabeza sin casco") duplica las clases y confunde al modelo con cabezas
parcialmente visibles. Con anclas, la ausencia se **deduce**: si la cabeza se ve y ningún casco la
cubre, falta el casco. Si la cabeza no se ve, el estado es `NO_VERIFICABLE` y **no se alerta**. Esto
reduce falsas alarmas por oclusión, el principal riesgo de fatiga de alertas.

### 2.3 Fuentes de datos y licencias

- **SH17: no apto para el producto** (CC BY-NC-SA 4.0, no comercial; además, sus imágenes vienen de
  Pexels, con términos propios). Solo podría servir para experimentos internos que **no** producen
  pesos distribuidos. Para evitar contaminar los artefactos, se recomienda no usarlo.
- Datasets de Roboflow Universe u otros: aceptar **solo** los que tengan una licencia comercial
  verificada (CC BY 4.0, CC0, MIT). Registrar cada uno en el manifiesto, con su atribución en
  THIRD_PARTY_NOTICES.
- **Fuente principal: imágenes propias de las cámaras del cliente piloto**, con autorización escrita
  del cliente y la base legal que defina D5. Es la única fuente que refleja el ángulo, la luz, los
  colores del EPP y la distancia reales.

### 2.4 Plan de captura

- Herramienta `tools/capturar_dataset.py`: muestrea frames de las cámaras del piloto cada N segundos,
  descarta duplicados casi idénticos (hash perceptual) y guarda los metadatos (cámara, fecha, hora,
  turno).
- Cubrir la diversidad: los turnos (día, tarde, noche si aplica), el clima, las distancias, las
  aglomeraciones y los casos difíciles (casco en la mano, gafas en la frente, barbijo en el cuello).
- **Split sin fuga de información:** separar por **cámara y día**, nunca por frames al azar. Los
  frames consecutivos son casi idénticos, y un split aleatorio infla las métricas.
  Train/val/test, por ejemplo, por días distintos y con una cámara reservada solo para test.

### 2.5 Guía de etiquetado (`docs/ml/guia_etiquetado.md`)

- Definiciones operativas:
  - "casco puesto" = sobre la cabeza; un casco en la mano o colgado **no** se etiqueta como `casco`
    asociado a la cabeza;
  - gafas en la frente = no puestas;
  - barbijo bajo la nariz o en el cuello = decidir con D3 (cumplimiento parcial).
- Tamaño mínimo de caja a etiquetar (por debajo, se marca como región "ignorar").
- Doble etiquetado del 10 % de las imágenes para medir el acuerdo entre etiquetadores. Las clases con
  bajo acuerdo se redefinen antes de entrenar.
- Herramienta: **CVAT** (MIT) o **Label Studio** (Apache-2.0), autoalojadas. Así las imágenes con
  rostros no salen a terceros sin control.

### 2.6 Versionado y custodia de los datos

- Las imágenes **nunca** van a git (son pesadas y contienen datos personales).
- Almacenamiento cifrado con acceso restringido; versionado con DVC (Apache-2.0) o un manifiesto con
  hashes (`ml/datasets/<version>/manifest.json`).
- Cada modelo entrenado registra la versión exacta del dataset (contrato de `mle-workflow`).

### DoD de la Fase 2

- [ ] Iteration Compact aprobado por el responsable de producto.
- [ ] Guía de etiquetado aprobada; acuerdo entre etiquetadores medido y por encima del umbral definido.
- [ ] Dataset v0.1 versionado, con un split por cámara/día documentado y las licencias de cada fuente registradas.

---

## 9. Fase 3 — Entrenamiento, evaluación y exportación del modelo EPP

**Skills:** `mle-workflow`, `benchmark-optimization-loop`, `investigate-first`.
**[BLOQUEADA por la Fase 2]**

### 3.1 Código de entrenamiento separado del producto

- Directorio `ml/`, que no se empaqueta en el `.exe`, con su propio `ml/requirements-ml.txt` fijado
  (`rfdetr[onnx]` con versión exacta y `torch`).
- `ml/train.py`: configuración en una `dataclass` inmutable (ruta del dataset, versión, tamaño del
  modelo, resolución, épocas, semilla). Registra el SHA del código, el hash de la configuración, la
  versión del dataset y las métricas. El artefacto se nombra a partir de esos hashes, como en el
  ejemplo de `mle-workflow`.
- Pruebas: la configuración se valida, el nombre del artefacto es determinista y el conversor de
  formato de etiquetas (CVAT → COCO) se prueba con fixtures pequeñas.

### 3.2 Baseline y variantes

1. **Baseline:** RF-DETR Small, ajuste fino con casco + chaleco + anclas (iteración 1 de D3).
2. Variantes (una hipótesis por variante, según `benchmark-optimization-loop`):
   - RF-DETR Nano (más rápido);
   - RF-DETR Medium (más preciso en guantes y gafas);
   - mayor resolución de entrada;
   - YOLOX-s ajustado (alternativa liviana en CPU).

### 3.3 Métricas: de la caja al evento

- **Nivel caja** (diagnóstico): AP50 y recall por clase al umbral elegido, por slice.
- **Nivel evento** (la que manda para el negocio): sobre los videos dorados, precisión y recall de las
  **infracciones** ("persona X sin casco durante al menos T segundos"), después de la asociación y la
  ventana temporal de la Fase 4.
- **Economía de errores** (D4):
  - una falsa alarma cuesta confianza, porque el responsable deja de mirar las alertas;
  - una infracción no detectada cuesta riesgo de accidente.
  - Elegir el umbral por clase y el tiempo de confirmación T según qué error absorbe el negocio.
  - Ninguna métrica se ajusta sobre el set de test.

### 3.4 Puertas de promoción automáticas (fallan cerradas)

- `ml/promotion_gates.py`, con tests, siguiendo el patrón `assert_promotion_ready` de `mle-workflow`.
- Umbrales a fijar **antes** de entrenar (D4). Ejemplo de estructura, **sin valores inventados**:

```python
PROMOTION_GATES = {
    "recall_evento_casco": ("min", None),        # definir con D4
    "falsas_alarmas_por_hora": ("max", None),    # definir con D4
    "fps_por_camara_hardware_objetivo": ("min", None),  # definir con D2
    "recall_persona_vs_baseline": ("min", None), # no peor que el modelo de producción
}
```

- Un umbral `None` hace fallar la puerta. Así nadie promueve un modelo sin haber definido los umbrales.

### 3.5 Análisis de errores y bitácora

- Después de cada entrenamiento, separar los falsos positivos, los falsos negativos y los
  "no verificables", y agruparlos por slice (distancia, luz, cámara, oclusión).
- Cada grupo se traduce en un movimiento: mejores etiquetas, más datos de ese slice, otro umbral u
  otro fallback de producto.
- Bitácora en `docs/ml/bitacora.md` con la plantilla *Observation Ledger* de `mle-workflow`.
- Cada error importante se convierte en un caso del set dorado (prueba de regresión).

### 3.6 Exportación a ONNX y paridad

- `model.export()` (RF-DETR, extra `rfdetr[onnx]`; opset 17 por defecto). La resolución de entrada
  debe ser múltiplo del tamaño de parche del modelo: verificar en su configuración.
- **Prueba de paridad:** sobre un set fijo de imágenes, comparar las detecciones de PyTorch y de ONNX
  Runtime. La tolerancia se fija **antes** de la primera corrida y se documenta. Ampliarla después
  para que pase está prohibido (§14.3).
- El adaptador de la §1.4 se reutiliza: el modelo EPP es otro artefacto del manifiesto con un catálogo
  de clases ampliado.

### 3.7 Ficha del modelo (model card) y manifiesto

- `models/cards/epp-vX.Y.md`: clases, datos de entrenamiento (versión y licencias), métricas por
  slice, limitaciones conocidas, uso previsto y no previsto.
- Entrada en `models/manifest.json` con sha256, licencias y catálogo de clases.

### DoD de la Fase 3

- [ ] El modelo pasa todas las puertas de promoción con umbrales definidos de antemano.
- [ ] La prueba de paridad PyTorch/ONNX pasa con la tolerancia documentada.
- [ ] La ficha del modelo y el manifiesto están completos; el gate de licencias está en verde.
- [ ] La bitácora registra al menos una iteración de análisis de errores.

---

## 10. Fase 4 — Dominio de cumplimiento de EPP

**Skills:** `lean-build`, `hexagonal-architecture`, `python-testing`, `python-patterns`, TDD estricto
(§2 de `CLAUDE.md`), Gherkin (§5). Se puede empezar **en paralelo** con las Fases 2 y 3, porque el
dominio se prueba con detecciones sintéticas.

### 4.0 Estructura propuesta

```text
src/ppe/
  domain/
    elementos.py         # ElementoEPP (Enum), EstadoElemento: PRESENTE / AUSENTE / NO_VERIFICABLE
    asociacion.py        # asigna detecciones de EPP y anclas a cada persona
    ventana_temporal.py  # confirma la ausencia con histéresis (por track y elemento)
    reglas.py            # EPP exigido por zona y regla global
    infracciones.py      # InfraccionIniciada / InfraccionFinalizada, enfriamiento (cooldown)
    errores.py           # excepciones tipadas del dominio
  application/
    ports.py             # RelojPort, RepositorioInfraccionesPort, AlmacenEvidenciasPort, PublicadorEventosPort
    evaluar_cumplimiento.py  # caso de uso por frame
features/
  cumplimiento_epp.feature
  alertas_epp.feature
  steps/
    test_cumplimiento_epp_steps.py
    test_alertas_epp_steps.py
tests/
  test_ppe_asociacion.py
  test_ppe_ventana_temporal.py
  test_ppe_reglas.py
  test_ppe_infracciones.py
  test_ppe_evaluar_cumplimiento.py
```

El dominio no importa `cv2`, ni motores de IA, ni la GUI; lo hace cumplir import-linter (Fase 0.4).

### 4.1 Asociación EPP–persona (`asociacion.py`)

**Entrada:** las personas seguidas (track_id + caja), las anclas (cabezas, manos) y las detecciones de
EPP de un frame. **Salida:** por persona, un `EstadoElemento` por cada elemento.

**Algoritmo:**

1. Asignar cada ancla (cabeza, manos) a la persona cuya caja la contiene con mayor IoA
   (intersección sobre el área del ancla), con un IoA mínimo configurable. Las cabezas se asignan
   además al tercio superior de la caja de la persona.
2. Asignar cada EPP a un ancla compatible:
   - casco, gafas y barbijo van a la cabeza;
   - guantes, a las manos;
   - chaleco, al torso (región central de la caja de la persona, sin ancla).
   - Cada EPP se asigna a una sola ancla: la de mayor IoA. En empate, la de centro más cercano.
3. Estado por elemento:
   - ancla visible y EPP asignado = `PRESENTE`;
   - ancla visible sin EPP = `AUSENTE`;
   - ancla no visible = `NO_VERIFICABLE`.
   - Para el chaleco, la región del torso basta como ancla si la persona se ve de la cintura hacia arriba.

**Casos obligatorios de prueba** (límites de §4 y §16):

- persona sin EPP; persona con todo; cajas que se solapan (dos operarios juntos); casco dentro de la
  caja de otra persona;
- **casco en la mano** (fuera de la región de la cabeza: no cuenta);
- cabeza fuera del cuadro (`NO_VERIFICABLE`); caja degenerada (ancho o alto cero); coordenadas
  negativas;
- lista vacía; una persona y N EPP; N personas y 0 EPP; un EPP huérfano sin persona (se ignora y se
  registra).

### 4.2 Ventana temporal con histéresis (`ventana_temporal.py`)

- Por (track_id, elemento): `AUSENTE` se **confirma** solo si se observó ausente en al menos el P %
  de los frames *verificables* de los últimos T segundos. Se **recupera** a `PRESENTE` después de
  M frames presentes seguidos.
- Los frames `NO_VERIFICABLE` no cuentan ni a favor ni en contra.
- Reloj inyectado (`RelojPort`); en las pruebas, un reloj falso. Prohibido `time.time()` y `sleep` en
  los tests (§4).
- Pruebas:
  - ausencia breve por oclusión (no confirma);
  - ausencia sostenida (confirma exactamente en T);
  - parpadeo alternado;
  - recuperación;
  - track que desaparece y vuelve (limpieza del estado después de un timeout);
  - salto del reloj hacia atrás (excepción tipada o reinicio documentado).

### 4.3 Reglas por zona (`reglas.py`)

- Una regla global opcional ("en toda la escena: casco y chaleco") más reglas por zona
  ("Boca de pozo: casco, chaleco, guantes, gafas").
- Persona en varias zonas: se exige la **unión** de los requisitos.
- Persona fuera de toda zona: solo la regla global.
- Validación de la configuración en el borde: elemento desconocido o zona sin polígono = excepción
  tipada con un mensaje claro.

### 4.4 Infracciones y enfriamiento (`infracciones.py`)

- `InfraccionIniciada` cuando un elemento exigido pasa a `AUSENTE` confirmado. `InfraccionFinalizada`
  cuando se recupera o la persona sale de la zona que lo exigía, con su duración.
- **Entrar a una zona sin EPP** (C6) es el mismo mecanismo: al entrar, cambia el conjunto de elementos
  exigidos y, si alguno está ausente y confirmado, la infracción empieza.
- **Enfriamiento:** no repetir la alerta de la misma (persona, elemento, zona) dentro de C minutos.
  Clave de enfriamiento: el nombre reconocido si existe; si no, el track_id. Así, si ByteTrack cambia
  el ID de alguien, no se duplica la alerta de un empleado reconocido.
- Cada evento lleva la versión del modelo (contrato de `mle-workflow`).

### 4.5 Caso de uso `EvaluarCumplimiento`

- Por frame: recibe las personas seguidas con su zona, las anclas y el EPP; aplica asociación →
  ventana → reglas → infracciones; publica los eventos por `PublicadorEventosPort` y devuelve el
  estado por persona (para que la UI lo dibuje).
- Pruebas con puertos falsos (repositorio en memoria, reloj falso). No se mockea la unidad bajo prueba.

### 4.6 Escenarios Gherkin (contrato con el negocio, §5)

`features/cumplimiento_epp.feature`:

```gherkin
# language: es
Característica: Verificación del EPP de cada operario
  Como responsable de seguridad e higiene
  Quiero que el sistema verifique el EPP de cada operario
  Para actuar ante los incumplimientos sin vigilar las cámaras

  Antecedentes:
    Dado una zona "Boca de pozo" que exige casco, chaleco y guantes

  Escenario: Operario con todo su EPP
    Dado un operario en "Boca de pozo" con casco, chaleco y guantes
    Cuando transcurre el tiempo de confirmación
    Entonces el operario figura como "cumple"
    Y no se genera ninguna alerta

  Esquema del escenario: Operario al que le falta un elemento
    Dado un operario en "Boca de pozo" sin <elemento>
    Cuando transcurre el tiempo de confirmación
    Entonces se genera una alerta por "<elemento>" faltante
    Y la alerta incluye la imagen del evento

    Ejemplos:
      | elemento |
      | casco    |
      | chaleco  |
      | guantes  |

  Escenario: Una oclusión breve no genera alerta
    Dado un operario en "Boca de pozo" con todo su EPP
    Y su casco deja de verse durante menos que el tiempo de confirmación
    Cuando transcurre el tiempo de confirmación
    Entonces no se genera ninguna alerta

  Escenario: Cabeza no visible
    Dado un operario en "Boca de pozo" cuya cabeza no se ve
    Cuando transcurre el tiempo de confirmación
    Entonces el casco del operario figura como "no verificable"
    Y no se genera ninguna alerta

  Escenario: Casco en la mano no cuenta como casco puesto
    Dado un operario en "Boca de pozo" que lleva el casco en la mano
    Cuando transcurre el tiempo de confirmación
    Entonces se genera una alerta por "casco" faltante

  Escenario: Entrar a una zona sin el EPP que exige
    Dado un operario sin guantes fuera de toda zona que exija guantes
    Cuando el operario entra a "Boca de pozo"
    Entonces al cumplirse el tiempo de confirmación se genera una alerta por "guantes" faltante en "Boca de pozo"
```

`features/alertas_epp.feature`:

```gherkin
# language: es
Característica: Alertas de EPP al responsable de seguridad
  Como responsable de seguridad e higiene
  Quiero recibir cada infracción una sola vez con su evidencia
  Para no perder eventos ni saturarme de avisos

  Escenario: Una infracción sostenida se notifica una sola vez
    Dado un operario identificado como "Ana" sin casco en "Boca de pozo" desde hace 10 minutos
    Cuando se evalúan las alertas pendientes
    Entonces el responsable recibió exactamente una alerta por "Ana" sin casco

  Escenario: Falla temporal del canal de aviso
    Dado una infracción registrada y el canal de aviso caído
    Cuando el canal de aviso se restablece
    Entonces el responsable recibe la alerta pendiente
    Y la infracción figura como notificada

  Escenario: Operario no identificado
    Dado un operario no identificado sin chaleco en "Boca de pozo"
    Cuando se genera la alerta
    Entonces la alerta indica "persona no identificada" y adjunta la imagen
```

### DoD de la Fase 4

- [ ] Todas las pruebas unitarias y BDD en verde. Cobertura del diff ≥ 95 % de líneas y ≥ 90 % de ramas; se propone 100 % de ramas para `src/ppe/` (módulo crítico).
- [ ] Mutación de al menos 85 % (se propone 90 % para `src/ppe/domain`).
- [ ] import-linter: `src/ppe` no importa ningún detalle prohibido.

---

## 11. Fase 5 — Integración en el pipeline de cámaras

**Skills:** `safe-refactor`, `lean-build`.

- 5.1 `TrackingPipeline.process` recibe todas las `Deteccion` del frame. Las personas pasan por
  ByteTrack como hoy, y el EPP y las anclas pasan al caso de uso `EvaluarCumplimiento` junto con los
  track_id y las zonas ya calculadas. No se duplica el cálculo de zonas.
- 5.2 **Una sola inferencia por frame:** el modelo EPP incluye `persona` y `celular`, o se compone
  (`DetectorCompuesto`) si el benchmark demuestra que dos modelos rinden mejor. Lo decide la bitácora
  de la Fase 3, no una opinión.
- 5.3 **Presupuesto de CPU:** si el hardware no sostiene la inferencia EPP en todos los frames,
  evaluarla cada k frames (configurable). La ventana temporal está diseñada para tolerar huecos.
- 5.4 **Un solo camino para GUI y headless** (lección CR-04): un test verifica que `main.py` y
  `CameraWorker` construyen el pipeline con la misma raíz de composición.
- 5.5 **Replay de regresión:** `tools/replay.py` más los clips dorados en CI (job `replay`). Los
  eventos emitidos deben coincidir con `*.expected.jsonl`.
- 5.6 Liberación de recursos: extender `tests/test_camera_worker_leaks.py`. Cada `start()` tiene su
  `stop()` y la sesión ONNX se libera (§16).

---

## 12. Fase 6 — Persistencia de infracciones y evidencias

**Skills:** `migration`, `python-testing`. `src/storage/` es un módulo crítico: 100 % de ramas y
mutación de al menos 90 %. **[BLOQUEADA por D5 para la retención]**

### 6.1 Tabla nueva (migración aditiva)

```sql
CREATE TABLE IF NOT EXISTS ppe_infracciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    employee_name TEXT,            -- NULL si no fue reconocido
    zona TEXT NOT NULL,
    elemento TEXT NOT NULL,
    inicio TEXT NOT NULL,          -- ISO 8601
    fin TEXT,                      -- NULL mientras siga abierta
    duracion_s REAL,
    evidencia_path TEXT,
    estado_notificacion TEXT NOT NULL DEFAULT 'PENDIENTE',
    intentos_notificacion INTEGER NOT NULL DEFAULT 0,
    modelo_version TEXT NOT NULL,
    reconocida_por TEXT,           -- acuse de recibo del responsable
    reconocida_en TEXT
);
```

- Solo se **expande**: no se toca ninguna tabla existente. La prueba de migración sigue el patrón de
  `tests/test_db_migration.py`: una base vieja abre sin pérdida y la tabla nueva se crea una sola vez
  (idempotente).
- Todas las consultas parametrizadas, más un **test de inyección** análogo a
  `tests/test_report_sql_injection.py` (§9).
- La base ya está cifrada (`db_crypto.py`): las infracciones heredan el cifrado.

### 6.2 Evidencia anotada

- Adaptador `AlmacenEvidenciasCv2` (implementa `AlmacenEvidenciasPort`, en la capa de adaptadores):
  - dibuja la caja de la persona en rojo y la etiqueta del elemento faltante;
  - guarda en `<tenant>/snapshots/epp/AAAA-MM-DD/<id>.jpg`.
- **Privacidad (D5):** opción de difuminar los rostros de terceros en la evidencia; los logs nunca
  llevan rostros, embeddings ni nombres en claro (§9).
- **Retención:** una tarea de purga borra la evidencia y anonimiza los registros después de N días
  (D5), reutilizando la idea de `anonymize_employee`. Prueba con un reloj falso.

### 6.3 Migración del formato de zonas (v1 → v2)

- v1 (actual): `{"Zona": [[x, y], ...]}`.
- v2:

```json
{"version": 2, "zonas": {"Boca de pozo": {"poligono": [[x, y]], "epp_requerido": ["casco", "chaleco"]}}}
```

- Según `migration`:
  - el lector acepta v1 y v2 (v1 se lee como "sin EPP exigido");
  - el escritor guarda v2 y hace una copia de seguridad del archivo v1 (`zonas_config.v1.bak.json`)
    antes de la primera escritura;
  - la reversión consiste en restaurar la copia.
- Pruebas: v1 válido, v2 válido, JSON corrupto (excepción tipada, sin pisar el archivo), elemento
  desconocido y escritura idempotente.

---

## 13. Fase 7 — Notificaciones al responsable de seguridad

**Skills:** `hexagonal-architecture` (puerto `NotificadorPort`), `error-handling` (reintentos, backoff,
circuit breaker), `security-review`. **[BLOQUEADA por D1]**

### 7.1 Patrón outbox (no perder avisos, no frenar el video)

1. La infracción se guarda primero (`estado_notificacion = PENDIENTE`).
2. Un hilo `DespachadorNotificaciones`, separado de las cámaras, toma las pendientes y llama al
   adaptador del canal.
3. Si sale bien, pasa a `ENVIADA`. Si falla, sube `intentos_notificacion` y reintenta con backoff
   exponencial y un tope. Agotados los intentos, queda en `FALLIDA`, visible en la UI. Nunca se
   descarta en silencio (P5).
4. Idempotencia: el ID de la infracción es la clave. Un reintento nunca duplica el aviso cuando el
   canal lo soporta (webhook con `Idempotency-Key`).
5. **Circuit breaker:** si el canal falla de forma repetida, se pausa X minutos para no saturar.

### 7.2 Adaptadores por canal (según D1)

| Canal | Implementación | Notas |
|-------|---------------|-------|
| Email | `smtplib` (stdlib) con TLS | Sin dependencias nuevas; la evidencia va adjunta o como enlace interno |
| Webhook | `urllib.request` (stdlib) o `httpx` fijado; cuerpo JSON firmado con HMAC-SHA256 | Permite integrar con cualquier sistema del cliente |
| Telegram | Bot API por HTTPS | Simple y gratuito; el token va al almacén de secretos |
| WhatsApp | WhatsApp Business Cloud API (Meta) | Requiere verificar el negocio, plantillas aprobadas y tiene costo por conversación: dejarlo para una segunda etapa |

### 7.3 Secretos y seguridad

- Los tokens y contraseñas van al Administrador de credenciales de Windows (vía `keyring`, licencia a
  verificar en la auditoría) o a variables de entorno. Nunca en `zonas_config.json`, ni en la base, ni
  en git (§9, detect-secrets).
- Validar las URLs de webhook (solo `https`, sin redirecciones a IPs privadas si el cliente lo exige).
- Los mensajes no incluyen datos sensibles innecesarios; el nombre del empleado solo si D5 lo permite.

### 7.4 Conectividad intermitente

- La cola persiste en la base: si no hay internet, las alertas esperan y salen cuando vuelve la
  conexión. La UI muestra la alerta **de inmediato**, haya red o no.

### 7.5 Pruebas

- Adaptadores falsos para el dominio.
- Adaptadores reales probados contra servidores locales falsos: un SMTP en un hilo local
  (`aiosmtpd` o un doble) y un HTTP local con `http.server` en `tmp_path`/localhost. **Sin red real**
  (§4).
- Inyección de fallas: timeout, HTTP 500, token inválido y respuesta lenta. Se verifica el estado
  final en la base.

---

## 14. Fase 8 — Interfaz gráfica y reportes

**Skills:** `lean-build`, `windows-desktop-e2e` (con la limitación de Tk), `python-testing`.

- **8.1 Overlay por elemento** (con el `AnotadorDeFrames` de la Fase 1):
  - caja de la persona en verde si cumple, en rojo si tiene una infracción confirmada y en gris si es
    no verificable;
  - etiquetas por EPP como en el video (`Casco`, `Chaleco`, `Guantes`…);
  - todo se puede activar o desactivar.
- **8.2 Panel "Alertas EPP":**
  - lista en vivo con miniatura, persona, zona, elemento, hora y estado de notificación;
  - botón "Recibido" (acuse de recibo del responsable, que se guarda en la base);
  - filtro por cámara y zona.
  - Toda la lógica vive en un presentador probado con pytest; la vista es delgada.
- **8.3 Editor de zonas:**
  - casillas de EPP exigido por zona (escribe el formato v2 de la §6.3);
  - validación de entradas (TASK-5.3 del SPEC).
- **8.4 Reporte Excel de cumplimiento:**
  - por turno, empleado, zona y elemento: cantidad de infracciones, duración total y % del tiempo en
    cumplimiento;
  - se genera de forma asíncrona, como los reportes actuales;
  - las pruebas verifican el contenido de celdas y hojas, no el tamaño del archivo (§16).
- **8.5 E2E:**
  - la skill `windows-desktop-e2e` usa pywinauto y UI Automation, pensados para WPF, WinForms, Win32
    y Qt; customtkinter (Tk) expone poco árbol de controles;
  - estrategia: prueba de humo E2E con el backend `win32` de pywinauto y capturas de pantalla
    (arranca, muestra el dashboard y abre el panel de alertas), más la lógica de las vistas en
    presentadores probados con pytest;
  - riesgo declarado en la §18.

---

## 15. Fase 9 — Build, piloto, operación y reversión

**Skills:** `verify-and-stop`, `mle-workflow` (sombra, canary, monitoreo), `investigate-first`.
**[BLOQUEADA por D8 y D9]**

- **9.1 Build:**
  - `gui_app.spec` sin `ultralytics` ni `torch`, con `onnxruntime` y el modelo `.onnx` más su
    manifiesto;
  - `obfuscate.py` y `compilar_exe.bat` revisados;
  - prueba de humo del ejecutable documentada en el PR (§16).
- **9.2 Instalador:** incluye THIRD_PARTY_NOTICES, las fichas de los modelos y el aviso de privacidad
  que defina D5.
- **9.3 Versión:** `VERSION` pasa de 1.3.0 a **2.0.0**. Es un cambio mayor: cambia el motor, el
  formato de zonas y llega un módulo nuevo.
- **9.4 Piloto en modo sombra:**
  - durante un período acordado, el módulo detecta y registra pero **no notifica**;
  - un humano audita una muestra de los eventos (verdaderos y falsos positivos) y de los videos (falsos
    negativos), con métricas a nivel evento;
  - recién después se activan las notificaciones (patrón sombra → canary de `mle-workflow`).
- **9.5 Monitoreo en operación:**
  - por cámara: FPS, latencia y tamaño de la cola de notificaciones;
  - **alertas por hora** (detecta la fatiga de alertas);
  - **proporción de "no verificable"** (señal de cámara mal ubicada o de deriva);
  - distribución de confianza del modelo (deriva);
  - fallas de notificación.
  - Se muestran en la UI y en los logs estructurados.
- **9.6 Criterios de reentrenamiento:** sube la proporción de no verificables, cae la confianza media,
  aparece un patrón nuevo de falsos positivos en la auditoría, o llega una cámara o un sitio nuevo. Cada
  reentrenamiento vuelve a la Fase 3 con su bitácora.
- **9.7 Reversión:**
  - el modelo anterior se conserva en el manifiesto y se puede volver a él desde la configuración;
  - el módulo EPP se puede desactivar;
  - se conserva el instalador anterior.

---

## 16. Criterios de aceptación

Formato de `intent-driven-development`. Prioridad: **R** = requerido, **I** = importante,
**O** = opcional.

### Licencia y motor

**AC-001: El runtime no contiene dependencias AGPL ni GPL** (R)
- Escenario: entorno limpio instalado solo desde `requirements.txt`.
- Acción: correr `scripts/check_licenses.py`.
- Esperado: código de salida 0 y ningún paquete con licencia AGPL, GPL, SSPL, CC-BY-NC ni PML.
- No debe: haber excepciones en la lista permitida sin un registro en `docs/legal/`.
- Verificación: job `licencias` en CI más la revisión legal (D9).

**AC-002: Todo modelo distribuido está declarado** (R)
- Escenario: cualquier archivo `.onnx` dentro de `models/`.
- Acción: correr el gate de licencias y `verify_model`.
- Esperado: el archivo figura en `models/manifest.json` con sha256 coincidente, la licencia de los
  pesos, la licencia del código de entrenamiento y los datasets con sus licencias.
- No debe: arrancar el tracking si el hash no coincide (falla cerrada).
- Verificación: pruebas de `test_model_verifier.py` más el gate.

**AC-003: El ejecutable funciona sin Ultralytics ni PyTorch** (R)
- Escenario: ejecutable compilado instalado en un Windows limpio.
- Acción: abrir la app con una cámara o un video de prueba.
- Esperado: detecta personas, persiste el tracking y genera los reportes como en la 1.3.0.
- No debe: importar `ultralytics` ni `torch` en ningún momento.
- Verificación: prueba de humo documentada más el test de `sys.modules`.

**AC-004: La detección de personas no empeora** (R)
- Escenario: set de validación del sitio piloto.
- Acción: correr `tools/bench_detectores.py`.
- Esperado: recall de persona del motor nuevo mayor o igual al de `yolov8n` actual, y FPS por cámara
  mayor o igual al umbral de D2.
- Verificación: bitácora del benchmark con números reales.

**AC-005: Ya no existe la deserialización insegura de `torch.load`** (I)
- Acción: buscar `torch.load` y `weights_only=False` en `src/`.
- Esperado: cero coincidencias.
- Verificación: test más `grep` en el gate.

### EPP

**AC-010: Asociación correcta del EPP a cada persona** (R)
- Escenario: frame sintético con N personas, sus anclas y su EPP, incluidos solapamientos.
- Acción: evaluar el cumplimiento.
- Esperado: cada elemento se asigna a la persona correcta; un casco en la mano no cuenta.
- Verificación: pruebas unitarias parametrizadas más mutación de al menos 90 %.

**AC-011: No se alerta lo que no se puede ver** (R)
- Escenario: persona cuya cabeza o manos no son visibles.
- Esperado: los elementos dependientes figuran como `NO_VERIFICABLE` y no se genera ninguna alerta.
- Verificación: escenario Gherkin "Cabeza no visible".

**AC-012: Confirmación temporal** (R)
- Escenario: elemento ausente durante un tiempo t.
- Esperado: si t < T, no hay infracción; si t ≥ T, la infracción empieza en T (con reloj falso).
- Verificación: pruebas de la ventana temporal más un escenario Gherkin.

**AC-013: EPP exigido por zona** (R)
- Escenario: un operario sin guantes entra a una zona que los exige.
- Esperado: infracción "guantes" en esa zona; fuera de la zona, ninguna (salvo la regla global).
- Verificación: escenario Gherkin "Entrar a una zona sin el EPP que exige".

**AC-014: Una alerta por infracción sostenida** (R)
- Escenario: infracción que dura más que el enfriamiento, con reidentificación de ByteTrack de un
  empleado reconocido.
- Esperado: exactamente una alerta por (persona, elemento, zona) dentro del período de enfriamiento.
- Verificación: escenario Gherkin más una prueba unitaria.

**AC-015: Evidencia anotada** (R)
- Esperado: cada infracción tiene una imagen con la persona marcada en rojo y el elemento faltante
  rotulado, guardada en la carpeta del tenant.
- No debe: guardar la imagen fuera del tenant ni escribir el nombre del empleado en los logs.
- Verificación: prueba de integración en `tmp_path` más revisión manual de una muestra.

**AC-016: Notificación confiable** (R; bloqueado por D1)
- Escenario: canal caído durante la infracción.
- Esperado: la alerta queda `PENDIENTE`, se reintenta y se entrega al volver el canal, sin duplicados.
- No debe: frenar el video ni perder la alerta en silencio.
- Verificación: pruebas con un servidor local falso e inyección de fallas.

**AC-017: Tiempo hasta la alerta** (I; umbral con D4)
- Escenario: infracción real en el sitio piloto.
- Esperado: la alerta aparece en la UI antes de T + Δ segundos desde el inicio de la infracción.
- Verificación: medición en el piloto (operacional).

**AC-018: Calidad a nivel evento en el piloto** (R; umbrales con D4)
- Escenario: videos dorados más la auditoría humana del modo sombra.
- Esperado: el recall y las falsas alarmas por hora cumplen las puertas de promoción.
- Verificación: `ml/promotion_gates.py` más el informe del piloto.

**AC-019: Retención de evidencias** (R; bloqueado por D5)
- Escenario: evidencia más antigua que N días.
- Acción: correr la purga.
- Esperado: imagen borrada y registro anonimizado.
- Verificación: prueba con un reloj falso.

### Harness

**AC-020: Las reglas de `CLAUDE.md` se verifican solas** (R)
- Escenario: PR que viola una regla (el dominio importa `cv2`, una dependencia sin fijar, gemelos
  divergentes, cobertura del diff por debajo del 95 %).
- Esperado: el CI falla con un mensaje que dice cómo corregirlo.
- Verificación: PRs de prueba que demuestran que cada check falla (tests del harness).

---

## 17. Plan de PRs y orden de ejecución

Cada PR mide 400 líneas de diff o menos, lleva la plantilla de §13 con la evidencia real del gate, y
está compuesto de commits atómicos con Conventional Commits en español (§12).

### Pista A — Harness y licencia (secuencial)

| PR | Contenido | Skill | Bloqueo |
|----|-----------|-------|---------|
| A-01 | `requirements-dev.txt`, fijar dependencias, marcadores de plataforma | `verify-and-stop` | — |
| A-02 | `pyproject.toml` + línea base + propuesta de waivers | `verify-and-stop` | Aprobación de waivers |
| A-03 | `scripts/quality_gate.sh/.ps1` + su test | `python-testing` | — |
| A-04 | import-linter + `check_architecture.py` con mensajes de corrección | `hexagonal-architecture` | — |
| A-05 | Gate de licencias + `models/manifest.json` (falla a propósito con la AGPL actual) | `migration` | — |
| A-06 | Hooks de Claude Code + `SessionStart` + pre-commit | `update-config`, `session-start-hook` | — |
| A-07 | CI de GitHub Actions (Windows + Linux) | — | — |
| A-08 | `docs/README.md`, ADR-001, `docs/quality/*`; propuesta de actualizar §16 de `CLAUDE.md`/`Agents.md` | `intent-driven-development` | Aprobación humana |
| A-09 | Pruebas de caracterización de `CameraWorker` | `safe-refactor` | — |
| A-10 | Tipos neutrales + `DetectorPort` + adaptador Ultralytics temporal | `hexagonal-architecture` | — |
| A-11 | `CameraWorker` y `main.py` usan el puerto; anotador propio; clases semánticas | `safe-refactor` | — |
| A-12 | Adaptador ONNX Runtime + pruebas | `python-testing` | — |
| A-13 | Benchmark de motores + bitácora + cierre de ADR-001 | `benchmark-optimization-loop` | D2 |
| A-14 | Verificador de modelos por manifiesto | `surgical-patch` | — |
| A-15 | Motor ONNX por defecto + retiro del parche de `torch.load` | `migration` | — |
| A-16 | CONTRAER: quitar Ultralytics y torch, borrar `.pt`, ajustar `gui_app.spec` | `migration` | **D7, D8** |
| A-17 | Reemplazar `tkcalendar` | `lean-build` | — |
| A-18 | THIRD_PARTY_NOTICES + revisión de `face_landmarks` y PyArmor | — | D9 |

### Pista B — Datos y modelo EPP (en paralelo, desde la decisión D6)

| Paso | Contenido | Bloqueo |
|------|-----------|---------|
| B-01 | Iteration Compact + contrato de datos + guía de etiquetado | D3, D4, D5 |
| B-02 | `tools/capturar_dataset.py` + captura en el piloto | D6 |
| B-03 | Etiquetado + medición de acuerdo + dataset v0.1 versionado | — |
| B-04 | `ml/train.py` + `ml/promotion_gates.py` + pruebas | — |
| B-05 | Entrenamientos, análisis de errores, bitácora | — |
| B-06 | Exportación ONNX + paridad + ficha + manifiesto | — |

### Pista C — Funcionalidad EPP (en paralelo con B; depende de A-10/A-12)

| PR | Contenido | Skill | Bloqueo |
|----|-----------|-------|---------|
| C-01 | `src/ppe/domain/elementos.py` + asociación + pruebas | `lean-build`, `python-testing` | — |
| C-02 | Ventana temporal con histéresis | `python-testing` | — |
| C-03 | Reglas por zona + infracciones + enfriamiento | `lean-build` | — |
| C-04 | Caso de uso `EvaluarCumplimiento` + `cumplimiento_epp.feature` | `hexagonal-architecture` | — |
| C-05 | Tabla `ppe_infracciones` + test de inyección + migración | `migration` | — |
| C-06 | Formato de zonas v2 (lector dual, copia de seguridad) | `migration` | — |
| C-07 | Integración en `TrackingPipeline` + replay + clips dorados | `safe-refactor` | B-06 para los clips reales |
| C-08 | Evidencia anotada + purga por retención | `lean-build` | D5 |
| C-09 | Outbox + despachador + circuit breaker | `error-handling` | — |
| C-10 | Adaptador del canal elegido + `alertas_epp.feature` | `hexagonal-architecture` | **D1** |
| C-11 | Overlay de EPP + panel de alertas | `lean-build` | — |
| C-12 | Editor de zonas con EPP exigido | `lean-build` | — |
| C-13 | Reporte Excel de cumplimiento | `python-testing` | — |
| C-14 | Build 2.0.0 + piloto en modo sombra | `verify-and-stop` | D8, D9 |

### Dependencias (resumen)

```text
A-01..A-08 (harness) ──► A-09..A-15 (puerto + ONNX) ──► A-16 (contraer, D8) ──► C-14 (release)
                              │
                              ├──► C-01..C-06 (dominio, con dobles) ──► C-07 (integración) ──► C-08..C-13
                              │
B-01..B-06 (datos y modelo EPP) ───────────────────────────────────────────┘ (modelo real para C-07)
```

---

## 18. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|--------|-------|---------|------------|
| R1 | Guantes y gafas (objetos chicos) no se detectan bien con la CPU objetivo | Alta | Alto | Empezar con casco + chaleco (D3); resolución mayor o modelo Medium solo si el benchmark lo justifica; evaluar GPU u OpenVINO (D2) |
| R2 | Fatiga de alertas por falsos positivos | Media | Alto | Anclas + `NO_VERIFICABLE` + ventana temporal + enfriamiento + piloto en sombra |
| R3 | Datos de entrenamiento insuficientes o con licencia incompatible | Media | Alto | Datos propios del piloto; gate de licencias sobre los datasets; nada de SH17 en los pesos distribuidos |
| R4 | Privacidad: imágenes con rostros y nombres | Media | Alto | D5, difuminado opcional, retención, cifrado y logs sin datos personales |
| R5 | El rendimiento en CPU de un modelo tipo DETR es menor al esperado (no hay cifras oficiales en CPU) | Media | Medio | Benchmark real antes de decidir; YOLOX como alternativa liviana |
| R6 | La migración rompe el tracking actual (regresión) | Baja | Alto | Pruebas de caracterización, interruptor de motor y contracción solo al final |
| R7 | La E2E de customtkinter no se puede automatizar del todo | Alta | Bajo | Presentadores probados con pytest + humo con pywinauto y capturas |
| R8 | ByteTrack reasigna IDs y duplica alertas | Media | Medio | Enfriamiento por nombre reconocido; métrica de duplicados en el piloto |
| R9 | La deuda de calidad heredada bloquea el gate | Alta | Medio | Línea base + waivers con fecha de caducidad aprobados por un humano; gate estricto en el código nuevo |
| R10 | Licencias "ocultas" (modelo de 68 puntos de dlib, PyArmor, tkcalendar) | Media | Alto | Auditoría completa (§1.1) + revisión legal (D9) |

---

## 19. Plan de verificación

| Criterio | Evidencia | Estado |
|----------|-----------|--------|
| AC-001 | Job `licencias` en CI + informe legal | En curso: gate y job listos (A-05, A-07); `tkcalendar` retirado (A-17); avisos de terceros y expediente legal (A-18). En rojo por diseño hasta A-16 (D8) y D9 |
| AC-002 | `tests/test_model_verifier.py` + gate | Cumplido: manifiesto validado por el gate (A-05) y verificador por manifiesto embebido que falla cerrado (A-14) |
| AC-003 | Prueba de humo del ejecutable (PR A-16) | Bloqueado (D8): checklist en `docs/runbooks/a16_contraer_motor.md` |
| AC-004 | `docs/benchmarks/motor_ia.md` | Bloqueado (D2, D6): herramienta y bitácora listas (A-13), falta la corrida con el video del piloto |
| AC-005 | Test de `sys.modules` + grep | En curso: el camino ONNX no carga torch (prueba en intérprete aparte, A-15); el parche de `torch.load` queda solo en el motor heredado hasta A-16 (D8) |
| AC-010 | `tests/test_ppe_asociacion.py` + mutmut | Pendiente |
| AC-011 | `features/cumplimiento_epp.feature` | Pendiente |
| AC-012 | `tests/test_ppe_ventana_temporal.py` + feature | Pendiente |
| AC-013 | `features/cumplimiento_epp.feature` | Pendiente |
| AC-014 | `features/alertas_epp.feature` + unitarias | Pendiente |
| AC-015 | Integración en `tmp_path` + muestra manual | Pendiente |
| AC-016 | Pruebas con un servidor local falso | Pendiente (D1) |
| AC-017 | Medición en el piloto | Pendiente (D4) |
| AC-018 | `ml/promotion_gates.py` + informe del piloto | Pendiente (D4) |
| AC-019 | Prueba de purga con un reloj falso | Pendiente (D5) |
| AC-020 | PRs de prueba que demuestran que cada check falla | En curso: cada check tiene pruebas que lo hacen fallar con mensaje de corrección (A-03..A-07); falta ver la CI real fallar en un PR |

Cada fase se cierra aplicando `verify-and-stop`: se corre la evidencia mínima que prueba sus AC, se
marca el estado aquí y se para.

---

## 20. Fuentes

- Ultralytics — licencias (AGPL-3.0 y Enterprise; los modelos entrenados también son AGPL): https://www.ultralytics.com/license
- RF-DETR — repositorio y licencias por tamaño: https://github.com/roboflow/rf-detr
- RF-DETR — exportación a ONNX: https://rfdetr.roboflow.com/latest/learn/export/
- D-FINE — licencia, tamaños y exportación: https://github.com/Peterande/D-FINE
- YOLOX — licencia y exportación ONNX/OpenVINO: https://github.com/Megvii-BaseDetection/YOLOX
- SH17 — dataset de EPP (CC BY-NC-SA 4.0): https://github.com/ahmadmughees/SH17dataset
- tkcalendar — licencia GPLv3: https://pypi.org/project/tkcalendar/
- OpenAI — "Harness engineering: leveraging Codex in an agent-first world": https://openai.com/blog/harness-engineering
- InfoQ — resumen de harness engineering: https://www.infoq.com/news/2026/02/openai-harness-engineering-codex

> **Aviso:** las conclusiones sobre licencias de este documento son técnicas, no asesoría legal. Deben
> confirmarse con un abogado antes de distribuir el producto (decisión D9).
