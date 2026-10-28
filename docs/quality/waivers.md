# Waivers vigentes (CLAUDE.md §15)

Aprobación: el dueño del producto aprobó de antemano waivers **solo para código heredado**
(nunca para código nuevo), con caducidad de 90 días, cada uno con su issue y su fila aquí
(instrucción de la sesión del 2026-10-21). Un waiver vencido bloquea el siguiente PR que toque
el archivo afectado.

| ID | Regla incumplida | Archivo | Motivo técnico | Riesgo | Fecha límite | Issue |
|----|------------------|---------|----------------|--------|--------------|-------|
| W-001 | `ruff format --check` (§8, §10.1) | 52 archivos heredados listados en `[tool.ruff.format] exclude` | Código previo al formateador; reformatear en masa está prohibido sin instrucción (§14.10) | Bajo | 2027-01-19 | #2 |
| W-002 | `ruff check` (§8, §10.2) | Archivos heredados de `[tool.ruff.lint.per-file-ignores]`, solo con los códigos que hoy incumplen | Deuda previa al gate | Medio (C901, PLR09xx, S110, E722) | 2027-01-19 | #3 |
| W-003 | `mypy` con `disallow_untyped_defs` (§3, §8) | 21 módulos de `src/` y 1 de `config/` con `[[tool.mypy.overrides]]` | Código sin anotar; imports sin prefijo `src.` hasta A-04 | Medio | 2027-01-19 | #4 |
| W-004 | `radon cc -n C` y `radon mi -n B` (§3, §10.5) | 10 bloques listados en `docs/quality/metricas.json` (`radon_cc_waiver`) y `src/gui_app.py` (`radon_mi_waiver`) | Funciones heredadas largas | Alto en `CameraWorker.run` y `TrackingPipeline.process` | 2027-01-19 | #5 |
| W-005 | `bandit -ll` (§8, §10.6) | `src/security/{crash_logger,db_crypto,drm}.py` (B413), `src/recognition/face_recognizer.py` (B301), `src/storage/database_manager.py` (B608) | B413 es falso positivo (`pycryptodome`); B301 migración `.pkl` única; B608 nombre de tabla constante | Bajo / medio (B301) | 2027-01-19 | #6 |
| W-006 | `--cov-fail-under=85` (§6, §10.4) | `src/` (global) | La línea base es 41 %; el piso del gate es `cobertura_global_minima` de `metricas.json` y solo sube | Medio | 2027-01-19 | #7 |
| W-007 | Suite 100 % verde (§4) | `tests/test_obfuscate_pipeline.py::test_obfuscate_command_is_restrictive_pyarmor` (`xfail(strict=True)`) | `obfuscate.py` no ofusca; arreglarlo exige D8 y licencia de PyArmor | **Alto** | 2027-01-19 | #8 |
| W-008 | Contrato `dominio-sin-detalles` de import-linter (§16) | `src/zones/zone_editor.py -> cv2` (`ignore_imports` en `.importlinter`) | Editor interactivo heredado con ventana de OpenCV dentro de `src/zones` | Bajo | 2027-01-20 | #10 |
| W-009 | Longitud de archivo ≤ 500 líneas (§3) | `src/gui_app.py` (`longitud_waiver` en `metricas.json`) | GUI heredada de 1094 líneas | Medio | 2027-01-20 | #16 |
| W-010 | Sin secretos en el repositorio (§9) | `scripts/tu_llave_maestra_privada.pem` (registrado en `.secrets.baseline` como secreto real) | Llave privada versionada antes del gate; rotarla y purgar el historial es acción humana | **Alto** | 2027-01-20 | #17 |
| W-011 | No se hace merge con checks en rojo (§13) | `.github/workflows/quality-gate.yml`, job `licencias` con `continue-on-error: true` | Dependencias y pesos heredados con licencia prohibida (AC-001) hasta A-14/A-16/A-17 | **Alto** | 2027-01-20 | #18 |

Las reglas para código **nuevo** (paquetes `src/inference`, `src/ppe`, `src/alerts`, `ml/`, `tools/`
y archivos de prueba nuevos) no tienen ningún waiver.
