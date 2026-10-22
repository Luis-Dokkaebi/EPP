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
| A-04 | Terminada | (rama `-a04`) | Imports con prefijo `src.`, import-linter + `check_architecture.py`, waiver #10, mutación por parche |

## En curso

- A-03e (subagente): diagnóstico del crash intermitente (SIGSEGV/SIGILL) de la suite heredada de GUI.
- A-05: gate de licencias + `models/manifest.json`.

## Bloqueadas

Ninguna todavía.

## Próxima entrega

A-05.
