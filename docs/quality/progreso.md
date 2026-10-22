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
| A-08 | Terminada (2 PRs) | (ramas `-a08`, `-a08b`) | Índice `docs/README.md`, ADR-001 provisional, lecciones de agentes; `-a08b` propone cambios a §6/§7/§16 de la constitución: **necesita aprobación humana** |

## En curso

- A-09 (caracterización de `CameraWorker`), A-10 (tipos neutrales, `DetectorPort`, adaptador de Ultralytics) y A-11 (consumidores del puerto): commiteadas en local, gate en curso.
- C-01..C-04 (subagente en worktree): dominio de EPP en `src/ppe/`.

## Bloqueadas

| Entrega / criterio | Motivo | Decisión que falta |
|--------------------|--------|--------------------|
| Gate de licencias en verde (AC-001) | `ultralytics` y `yolov8n.pt` (AGPL) siguen en el runtime hasta A-16; `tkcalendar` (GPL) hasta A-17; `certifi`, `tqdm`, `pycryptodome` esperan revisión humana | D8 (A-16) y aprobación humana en `docs/legal/licencias_revisadas.json` |
| Merge de `-a08b` (constitución) | Modifica `CLAUDE.md`/`Agents.md` | Aprobación humana |
| Rama `main` protegida (SPEC/9 §0.8) | Es configuración del repositorio en GitHub | Acción humana |
| Llave privada versionada (#17) | Rotar la llave y purgar el historial | Acción humana |

## Deuda detectada (no se arregla en estas entregas)

- `data/faces/` versiona fotos de personas reales (CLAUDE.md §9: datos personales reales): decidir su retiro y la purga del historial.
- `src/gui/views.py` llama a Tk desde el hilo de `DatabaseWorker` (mismo riesgo de crash que A-04 2/2).
- `reportlab` se importa pero no está en `requirements.txt`; `obfuscate.py` no ofusca (W-007, #8).

## Próxima entrega

A-11 (consumidores del puerto) y A-12 (adaptador ONNX Runtime).
