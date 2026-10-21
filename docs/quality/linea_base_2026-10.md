# Línea base de calidad — 2026-10-21

Medición del código heredado al adoptar el Quality Gate (SPEC/9 §0.2, entrega A-02).
Entorno: Linux, Python 3.11.15, Xvfb, `requirements-ci.txt` + `requirements-dev.txt`
(torch CPU 2.14.1 + ultralytics 8.1.15 para que las pruebas heredadas de la GUI arranquen).

La deuda medida aquí queda cubierta por los waivers de `docs/quality/waivers.md`.
Las cifras solo pueden mejorar (trinquete): `docs/quality/metricas.json` guarda los pisos.

## 1. Formato — `ruff format --check .`

```
60 files would be reformatted, 13 files already formatted
```

Los 60 archivos son todo el Python heredado de `src/`, `tests/`, `config/`, `scripts/`, `utils/`
y la raíz. `tests/conftest.py` se limpió en esta misma entrega, así que la exclusión cubre 59.

## 2. Lint — `ruff check . --statistics` (selección del Apéndice A)

```
241  E501     Line too long
142  S101     Use of `assert` detected        (pruebas: se permite por configuración)
120  T201     `print` found
 86  I001     Import block is un-sorted
 32  E402     Module level import not at top of file
 31  PLR2004  Magic value used in comparison
 27  W291     Trailing whitespace
 27  F401     imported but unused
 11  C901     too complex
 11  UP007    Use `X | Y` for type annotations
 10  S110     try-except-pass
  8  PLR0912  Too many branches
  8  PLR0915  Too many statements
  6  UP015 · 5 F841 · 5 PLR0913 · 4 S108 · 4 E701 · 4 E702 · 3 B007 · 3 E722 · 3 F541 · 3 F811
  3  UP035 · 2 S608 · 2 N806 · 2 E741 · 2 W292 · 2 UP012 · 2 RUF005 · 1 B904 · 1 B905 · 1 N801
  1  E401 · 1 PLR0911 · 1 PLW2901 · 1 UP006 · 1 RUF003 · 1 RUF013 · 1 RUF100
```

El detalle por archivo es exactamente `[tool.ruff.lint.per-file-ignores]` de `pyproject.toml`.

## 3. Tipos — `mypy src/`

```
Found 211 errors in 25 files (checked 36 source files)
167 no-untyped-def · 19 import-not-found · 17 import-untyped · 3 attr-defined
2 truthy-function · 2 var-annotated · 1 no-redef
```

- `import-untyped`: librerías sin anotaciones publicadas (pandas, shapely, supervision,
  customtkinter, tkcalendar…). Se resuelve con `ignore_missing_imports` por librería (no es waiver).
- `import-not-found`: imports heredados sin el prefijo `src.` (`from analysis...`); A-04 los unifica.
- Resto: `[[tool.mypy.overrides]]` por módulo, solo con los códigos que incumple.

## 4. Complejidad y mantenibilidad — `radon cc src -n C` / `radon mi src -n B`

```
src/main.py                         F start_video_stream                      C (17)
src/gui_app.py                      M SystemGUI._update_video                 E (31)
src/gui_app.py                      M SystemGUI._process_burst                C (13)
src/acquisition/camera_enumerator.py F enumerate_cameras                      C (16)
src/storage/database_manager.py     M DatabaseManager.get_efficiency_report   C (13)
src/tracking/tracking_pipeline.py   M TrackingPipeline.process                C (17)
src/tracking/camera_worker.py       M CameraWorker.run                        D (26)
src/tracking/camera_worker.py       C CameraWorker                            C (11)
src/recognition/face_recognizer.py  M FaceRecognizer.load_known_faces         C (18)
src/analysis/efficiency_calculator.py M EfficiencyCalculator.calculate_efficiency C (14)
src/security/drm.py                 M DRMValidator._generate_machine_id       C (11)

radon mi: src/gui_app.py - B (11.38)
```

## 5. Seguridad — `bandit -r src -ll` y `pip-audit`

```
B413 (High)   src/security/crash_logger.py:25, db_crypto.py:29, drm.py:162-164  (falso positivo: pycryptodome)
B301 (Medium) src/recognition/face_recognizer.py:102  (migración única desde .pkl)
B608 (Medium) src/storage/database_manager.py:379     (nombre de tabla constante)
pip-audit: 7 vulnerabilidades en cryptography 42.0.5 y 1 en pytest 8.1.1 → corregidas en A-01.
```

## 6. Pruebas y cobertura — `pytest --cov=src --cov-branch`

Antes de A-02 (rojo en `main`):

```
FAILED tests/test_drm_fallback.py::TestDRM::test_wmi_fallback - ModuleNotFoundError: wmi
FAILED tests/test_obfuscate_pipeline.py::test_obfuscate_command_is_restrictive_pyarmor
FAILED tests/test_security_fixes.py::TestFaceEncodingsIntegrity::test_valid_roundtrip_load_save
3 failed, 134 passed · TOTAL 2973 stmts, cobertura 36 %
```

Causas y tratamiento en A-02:

| Prueba | Causa | Tratamiento |
|--------|-------|-------------|
| `test_wmi_fallback` | Usaba `patch('wmi.WMI')`, que exige `wmi` instalado (solo Windows) | Se reescribe con un doble de `wmi` en `sys.modules`; misma aserción |
| `test_valid_roundtrip_load_save` | Acoplada al orden de importación: si `face_recognizer` se importó antes del doble de `face_recognition`, el módulo queda con `None` y no carga nada | Fixture `autouse` que fija el doble en el módulo bajo prueba |
| `test_obfuscate_command_is_restrictive_pyarmor` | `obfuscate.py` no ofusca (copia sin PyArmor) | `xfail(strict=True)` con WAIVER-#8; requiere D8 |

Después de A-02: `143 passed, 1 xfailed`, cobertura **41 %** (piso del trinquete).

## 7. Otros hallazgos (anotados, fuera del alcance de A-02)

- `tests/test_sprint5_audit.py` escribía `stress_test_export_50k.xlsx` en la raíz del repo
  (corregido en A-02 a un directorio temporal; el binario versionado no se toca, §14.12).
- `tests/test_sprint5_audit.py` y `tests/test_ui_navigation.py` construyen `AppMain`, que carga
  el modelo YOLO real (§16: un test unitario no carga modelos). Se resuelve en A-11/A-15.
- `scripts/tu_llave_maestra_privada.pem` es una **llave privada versionada** (§9). Requiere
  rotación y borrado del historial por un humano.
- `src/gui_app.py` importa `reportlab`, que no figura en `requirements.txt`.
- La suite heredada con orden aleatorio (`pytest-randomly`) puede abortar con `Segmentation
  fault` en algunas semillas (Tk + hilos); ver `docs/quality/lecciones_agentes.md` cuando exista.
