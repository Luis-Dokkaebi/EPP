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
| A-10 | Terminada (3 PRs) | #32, ramas `-a10h`, `-a10` | Dobles compartidos; loggers intactos tras import-linter y gate de prueba en copia temporal; tipos neutrales, `DetectorPort` y adaptador de Ultralytics |
| A-11 | Terminada (2 PRs) | ramas `-a11a`, `-a11` | Anotador propio, conversión para ByteTrack, caracterización headless; worker, GUI y headless usan el puerto y la raíz de composición |
| A-12 | Terminada (2 PRs) | ramas `-a12a`, `-a12` | `onnxruntime==1.31.0` (MIT), pruebas reales de `enumerate_cameras`; adaptador ONNX Runtime tipo DETR (mutación 100 %) |
| A-13 | Herramienta terminada (3 PRs); **corrida real bloqueada** | ramas `-a13a`, `-a13`, `-a13b` | Métricas, puerta que falla cerrada sin los umbrales de D2, CLI y bitácora vacía. Falta el benchmark con el video del piloto (D2, D6) |
| A-14 | Terminada | rama `-a14` | Verificador por manifiesto embebido (AC-002), falla cerrada |
| A-15 | Parcial (2 PRs) | ramas `-a15a`, `-a15` | Interruptor de motor en la raíz, parche de `torch.load` confinado al motor heredado, camino ONNX sin torch. **ONNX por omisión bloqueado**: falta un modelo que pase la puerta de A-13 |
| A-16 | **Bloqueada** (D8) | — | [Runbook](../runbooks/a16_contraer_motor.md) con la prueba de humo del ejecutable (AC-003) |
| A-17 | Terminada (2 PRs) | ramas `-a17a`, `-a17` | Selector de fecha propio; `tkcalendar` fuera de `requirements.txt`. Prueba de humo manual de reportes pendiente (humano) |
| A-18 | Terminada; release bloqueado por D9 | rama `-a18` | `THIRD_PARTY_NOTICES` generado en CI y [expediente legal](../legal/revision_d9.md) |

## En curso

- Pista B (B-01..B-06, subagente): documentos del contrato de datos, herramientas de captura y
  etiquetado, `ml/train.py` y `ml/promotion_gates.py` con los umbrales de D4 en `None`.
- Pista C (C-01..C-13, subagente): dominio de EPP en `src/ppe/` (C-01..C-04 terminadas en local)
  y el resto de la integración.

## Bloqueadas

| Entrega / criterio | Motivo | Decisión que falta |
|--------------------|--------|--------------------|
| Gate de licencias en verde (AC-001) | `ultralytics` y `yolov8n.pt` (AGPL) siguen en el runtime hasta A-16; `tkcalendar` ya salió (A-17); `certifi`, `tqdm`, `pycryptodome` esperan revisión humana | D8 (A-16) y aprobación humana en `docs/legal/licencias_revisadas.json` |
| A-13: benchmark real y cierre de ADR-001 | Faltan los umbrales y el hardware de referencia, y el video etiquetado del piloto | D2, D6 |
| A-15: ONNX como motor por omisión | Falta un modelo ONNX aprobado por la puerta de A-13 | D2 (y B-05/B-06 para el modelo de EPP) |
| Release (C-14) | Revisión legal | D9 ([expediente](../legal/revision_d9.md)) |
| Merge de `-a08b` (constitución) | Modifica `CLAUDE.md`/`Agents.md` | Aprobación humana |
| Rama `main` protegida (SPEC/9 §0.8) | Es configuración del repositorio en GitHub | Acción humana |
| Llave privada versionada (#17) | Rotar la llave y purgar el historial | Acción humana |

## Deuda detectada (no se arregla en estas entregas)

- `data/faces/` versiona fotos y codificaciones biométricas (`encodings.pkl`) de personas reales (CLAUDE.md §9: datos personales reales): decidir su retiro y la purga del historial.
- En la CI de Windows fallan de forma intermitente dos pruebas heredadas de rendimiento con esperas reales (`test_drop_frame_protocol`, `test_frame_consumption_with_mock_producers`) y una creación de Tk (`init.tcl`); en Linux pasan con cualquier semilla. Pendiente reescribirlas sin esperas reales (CLAUDE.md §4).
- `src/gui/views.py` llama a Tk desde el hilo de `DatabaseWorker` (mismo riesgo de crash que A-04 2/2).
- `reportlab` se importa pero no está en `requirements.txt`; `obfuscate.py` no ofusca (W-007, #8).

## Próxima entrega

Integrar las pistas B y C (PRs apilados) y la verificación final (§17 de CLAUDE.md).
