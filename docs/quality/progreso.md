# Progreso del plan SPEC/9 (EPP y licencia)

Bitácora para retomar el trabajo en otra sesión. Se actualiza al cerrar cada entrega.
Fuente de verdad del alcance: `SPEC/9_PLAN_EPP_Y_LICENCIA.md` (§17 para el orden, §19 para los AC).

## Decisiones del dueño del producto (§4)

| ID | Respuesta registrada | Efecto en el trabajo |
|----|----------------------|----------------------|
| D1 | Email + webhook | Se implementan ambos adaptadores (C-10) |
| D2 | Desconocido | Benchmark en CPU; proveedor de ejecución configurable |
| D3 | Casco y chaleco; guantes, gafas y barbijo en la 2.ª iteración | Taxonomía v1 con anclas `cabeza`/`manos` |
| D4 | PENDIENTE | Umbrales `None` en `ml/promotion_gates.py`: la puerta falla cerrada |
| D5 | PENDIENTE | Retención configurable sin valor por defecto; falla ruidosa si falta |
| D6 | PENDIENTE | Herramientas de captura y etiquetado sin datos reales |
| D7 | Migrar | Fase 1 completa |
| D8 | Sin respuesta (la plantilla quedó como `[SÍ / NO]`) | Se trata como **NO**: no se tocan `gui_app.spec`, `compilar_exe.bat`, `obfuscate.py`, `setup_oficina.iss` ni los `.pt` |
| D9 | PENDIENTE | `docs/legal/` preparado; release bloqueado |
| D10 | Módulo activable por licencia DRM | Mismo `.exe` |
| Waivers | Aprobados de antemano solo para código heredado, 90 días, con issue y fila en `waivers.md` | Ver `docs/quality/waivers.md` |

## Entregas

| Entrega | Estado | PR | Nota |
|---------|--------|----|------|
| A-01 | Terminada | #1 | Dependencias fijadas; pip-audit limpio |
| A-02 | Terminada | #9 | `pyproject.toml`, línea base, waivers #2–#8, 3 pruebas heredadas aisladas |
| A-03 | Terminada (4 PRs) | #11, #12, #13, #14 | Trinquete radon, caducidad de waivers, runner y puntaje de mutación, `quality_gate.sh/.ps1` |
| A-04 | Terminada | #15 | Imports con prefijo `src.`, import-linter + `check_architecture.py`, waiver #10, mutación por parche |
| A-04 (2/2) | Terminada | #19 | Escaneo de cámaras en el hilo de Tk (crash SIGSEGV/SIGILL), mutantes equivalentes descontados, caché de mutmut por objetivo |
| A-05 | Terminada (2 PRs) | #20, #21 | Gate de licencias del runtime + manifiesto de modelos; **falla a propósito** por la AGPL |
| A-06 | Terminada (6 PRs) | #22–#27 | Hooks de Claude Code (bash, archivos, pip, formato, cierre), SessionStart, pre-commit, tamaño de archivo, detect-secrets; waivers W-009 (#16) y W-010 (#17) |
| A-07 | Terminada | #28 | CI en GitHub Actions (Windows + Linux, mutación, licencias no bloqueante con W-011, #18); la corrida real se ve en el PR |
| A-08 | Terminada (2 PRs) | #29, #30 | Índice `docs/README.md`, ADR-001 provisional, lecciones de agentes; `-a08b` propone cambios a §6/§7/§16 de la constitución: **necesita aprobación humana** |
| A-09 | Terminada | #31 | Caracterización de `CameraWorker.run()` (17 casos, sin hilos ni esperas reales) |
| A-10 | Terminada (3 PRs) | #32, #33, #34 | Dobles compartidos; loggers intactos tras import-linter y gate de prueba en copia temporal; tipos neutrales, `DetectorPort` y adaptador de Ultralytics |
| A-11 | Terminada (2 PRs) | #35, #36 | Anotador propio, conversión para ByteTrack, caracterización headless; worker, GUI y headless usan el puerto y la raíz de composición |
| A-12 | Terminada (2 PRs) | #38, #39 | `onnxruntime==1.31.0` (MIT), pruebas reales de `enumerate_cameras`; adaptador ONNX Runtime tipo DETR (mutación 100 %) |
| A-13 | Herramienta terminada (3 PRs); **corrida real bloqueada** | #41, #42, #43 | Métricas, puerta que falla cerrada sin los umbrales de D2, CLI y bitácora vacía. Falta el benchmark con el video del piloto (D2, D6) |
| A-14 | Terminada | #40 | Verificador por manifiesto embebido (AC-002), falla cerrada |
| A-15 | Parcial (2 PRs) | #44, #45 | Interruptor de motor en la raíz, parche de `torch.load` confinado al motor heredado, camino ONNX sin torch. **ONNX por omisión bloqueado**: falta un modelo que pase la puerta de A-13 |
| A-16 | **Bloqueada** (D8) | — | [Runbook](../runbooks/a16_contraer_motor.md) con la prueba de humo del ejecutable (AC-003) |
| A-17 | Terminada (2 PRs) | #46, #47 | Selector de fecha propio; `tkcalendar` fuera de `requirements.txt`. Prueba de humo manual de reportes pendiente (humano) |
| A-18 | Terminada; release bloqueado por D9 | #48 | `THIRD_PARTY_NOTICES` generado en CI y [expediente legal](../legal/revision_d9.md) |
| B-01 | Terminada (3 PRs) | #49, #50, #51 | Iteration Compact, contrato de datos y guía de etiquetado; validación de taxonomía y metadatos |
| B-02 | Terminada (3 PRs) | #52, #53, #54 | Herramienta de captura del dataset (sin datos reales, D6) |
| B-03 | Terminada (6 PRs) | #55–#60 | Acuerdo entre etiquetadores, manifiesto y versionado del dataset, conversión de etiquetas, runbook de etiquetado |
| B-04 | Terminada (4 PRs) | #61–#64 | Puertas de promoción con umbrales `None` (fallan cerradas hasta D4/D2), adaptador de RF-DETR, requisitos de `ml/` |
| B-05 | Herramienta terminada; **entrenamiento real bloqueado** | #65 | Runbook de entrenamiento y bitácora del modelo. Falta el dataset real (D6) |
| B-06 | Herramienta terminada (3 PRs); **modelo real bloqueado** | #66, #67, #68 | Paridad PyTorch/ONNX con tolerancia fija, exportación y entrada de manifiesto, ficha del modelo |
| C-01 | Terminada (4 PRs) | #69–#72 | Dominio de EPP (`src/ppe`) sin visión ni motores; anclas por persona y asignación de cada EPP a su ancla (AC-010, mutación 100 %) |
| C-02 | Terminada | #73 | Ventana temporal que confirma la ausencia (AC-012) |
| C-03 | Terminada (2 PRs) | #74, #75 | EPP exigido por zona y regla global; infracciones con enfriamiento (AC-013, AC-014) |
| C-04 | Terminada (3 PRs) | #76, #77, #78 | Caso de uso `EvaluarCumplimiento` con puertos y `cumplimiento_epp.feature` (AC-011, AC-013) |
| C-05 | Terminada | #79 | Tabla `ppe_infracciones` (migración aditiva, inyección SQL probada) |
| C-06 | Terminada (2 PRs) | #80, #81 | Formato de zonas v2 con EPP exigido; `ZoneChecker` lee v1 y v2 |
| C-07 | Terminada (2 PRs) | #82, #83 | Pipeline conectado al caso de uso; replay de regresión con eventos dorados sintéticos |
| C-08 | Terminada (2 PRs) | #84, #85 | Evidencia anotada (AC-015); purga por retención sin valor por omisión (AC-019, D5) |
| C-09 | Terminada (4 PRs) | #86–#89 | Outbox: reintentos, circuit breaker, bandeja SQLite, hilo despachador (AC-016) |
| C-10 | Terminada (7 PRs) | #90, #91, #92, #103, #104, #93, #94 | Webhook firmado (HMAC, https), email con STARTTLS, configuración por entorno, `alertas_epp.feature` (AC-014, AC-016) |
| C-11 | Terminada (4 PRs) | #95–#98 | Overlay de cumplimiento y panel "Alertas EPP" con acuse de recibo |
| C-12 | Terminada (3 PRs) | #99, #100, #101 | Editor de EPP por zona; arregla el editor heredado que dejaba ilegible un archivo v2 |
| C-13 | Terminada (3 PRs) | #102, #105, #106 | Resumen y Excel de cumplimiento con `reporte_cumplimiento_epp.feature` |
| C-14 | **Bloqueada** (D8, D9) | #107 (solo runbook) | [Runbook](../runbooks/piloto_sombra.md) del build 2.0.0 y del piloto en sombra, **no ejecutado** |

## Integración y orden de merge

Las tres pistas parten de A-12 (#39) y se juntan en la rama `-cierre` (PR de cierre), que además
actualiza este archivo y SPEC/9 §19. Los PRs están apilados: cada uno apunta a la rama del
anterior. Orden para mergear con **merge commit** (nunca squash ni rebase, para no romper la pila):

1. `main` ← #1 … #39 (A-01..A-12), en orden.
2. A-13..A-18: #40 … #48.
3. B-01..B-06: #49 … #68.
4. C-01..C-14 siguiendo la cadena de bases: #69 … #92, #103, #104, #93 … #102, #105, #106, #107
   (#103 y #104 se agregaron al dividir C-10 para quedar bajo 400 líneas).
5. El PR de cierre (`-cierre`), que une las tres puntas.

Al mergear cada PR y borrar su rama, GitHub mueve la base del siguiente a `main`.

## Bloqueadas

| Entrega / criterio | Motivo | Decisión que falta |
|--------------------|--------|--------------------|
| Gate de licencias en verde (AC-001) | `ultralytics` y `yolov8n.pt` (AGPL) siguen en el runtime hasta A-16; `tkcalendar` ya salió (A-17); `certifi`, `tqdm`, `pycryptodome` esperan revisión humana | D8 (A-16) y aprobación humana en `docs/legal/licencias_revisadas.json` |
| A-13: benchmark real y cierre de ADR-001 | Faltan los umbrales y el hardware de referencia, y el video etiquetado del piloto | D2, D6 |
| A-15: ONNX como motor por omisión | Falta un modelo ONNX aprobado por la puerta de A-13 | D2 (y B-05/B-06 para el modelo de EPP) |
| Release y piloto (C-14) | Build del ejecutable y revisión legal | D8 y D9 ([expediente](../legal/revision_d9.md), [runbook](../runbooks/piloto_sombra.md)) |
| B-05/B-06 con datos reales | Captura, etiquetado y entrenamiento con imágenes del sitio | D6 (y D4 para las puertas) |
| Umbrales de EPP y retención | Ventana temporal, enfriamiento, asociación; días de retención y si el aviso nombra al empleado | D4, D5 |
| `pragma: allowlist secret` de C-10 (6/7) | Exclusión nueva de detect-secrets en nombres y valores ficticios | Aprobación humana (§14.4) |
| Merge de `-a08b` (constitución) | Modifica `CLAUDE.md`/`Agents.md` | Aprobación humana |
| Rama `main` protegida (SPEC/9 §0.8) | Es configuración del repositorio en GitHub | Acción humana |
| Llave privada versionada (#17) | Rotar la llave y purgar el historial | Acción humana |

## Deuda detectada (no se arregla en estas entregas)

- `data/faces/` versiona fotos y codificaciones biométricas (`encodings.pkl`) de personas reales (CLAUDE.md §9: datos personales reales): decidir su retiro y la purga del historial.
- En la CI de Windows fallan de forma intermitente dos pruebas heredadas de rendimiento con esperas reales (`test_drop_frame_protocol`, `test_frame_consumption_with_mock_producers`) y una creación de Tk (`init.tcl`); en Linux pasan con cualquier semilla. Pendiente reescribirlas sin esperas reales (CLAUDE.md §4).
- `src/gui/views.py` llama a Tk desde el hilo de `DatabaseWorker` (mismo riesgo de crash que A-04 2/2).
- `reportlab` se importa pero no está en `requirements.txt`; `obfuscate.py` no ofusca (W-007, #8).
- Composición de §5.4 sin hacer: evaluación de EPP en `CameraWorker`/`main`, arranque del
  `HiloDespachador`, panel de alertas y reporte de cumplimiento en la navegación, cámara de cada
  infracción y tiempo de cada persona en cada zona (sin él, el % de cumplimiento dice "sin datos").
- Al salir del modo sombra, las infracciones del período siguen PENDIENTE y se enviarían todas:
  falta un procedimiento aprobado (ver el runbook del piloto).
- `src/detection/people_detector.py` no se usa en la aplicación y lee zonas v1 a mano: proponer
  su retiro en un PR aparte.
- Una corrida del gate se colgó una vez en el paso de pruebas (c08) y pytest-timeout no la cortó;
  no se reprodujo. Vigilar en CI.
- `pip-audit` del gate audita `/home/user/venv311` y no `.venv` si falta `PIPAPI_PYTHON_LOCATION`.

## Próxima entrega

Ninguna del lado de los agentes: lo que queda depende de las decisiones D2, D4, D5, D6, D8 y D9 y
de las tareas humanas listadas arriba.
