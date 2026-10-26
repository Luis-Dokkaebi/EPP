# Progreso del plan SPEC/9 (EPP y licencia)

Bitácora para retomar el trabajo en otra sesión. Se actualiza al cerrar cada entrega.
Fuente de verdad del alcance: `SPEC/9_PLAN_EPP_Y_LICENCIA.md` (§17 para el orden, §19 para los AC).

## Decisiones del dueño del producto (§4)

| ID | Respuesta registrada | Efecto en el trabajo |
|----|----------------------|----------------------|
| D1 | Email + webhook | Se implementan ambos adaptadores (C-10) |
| D2 | CPU Intel con OpenVINO; cámaras por equipo según la licencia DRM (24/10/2026) | Umbrales de A-13: ≥ 5 FPS por cámara y p95 ≤ 200 ms (propuesta aceptada al no indicar otro valor) |
| D3 | Casco y chaleco; guantes, gafas y barbijo en la 2.ª iteración | Taxonomía v1 con anclas `cabeza`/`manos` |
| D4 | Evitar falsas alarmas; confirmar 4 s; enfriamiento 10 min; recall por evento ≥ 90 %; ≤ 1 falsa alarma por cámara y hora (24/10/2026) | Puertas de promoción fijadas; ventana y enfriamiento en la composición del módulo |
| D5 | Evidencias 30 días; el aviso nombra al empleado; sin difuminar rostros (24/10/2026) | Retención y `EPP_ALERTAS_NOMBRE_EMPLEADO=incluir` por omisión en la composición |
| D6 | Cámaras del cliente y un dataset comprado; etiquetado asistido por el modelo (24/10/2026) | Falta quién revisa las etiquetas: el modelo propone y una persona corrige (runbook de etiquetado) |
| D7 | Migrar | Fase 1 completa |
| D8 | **Sí** (24/10/2026) | A-16 queda autorizado; sigue esperando un modelo ONNX aprobado por la puerta (necesita los datos de D6) |
| D9 | PENDIENTE: la hará la persona que designó la dirección | `docs/legal/` preparado; release bloqueado |
| D10 | Módulo activable por licencia DRM | Mismo `.exe` |
| Licencias revisadas | `certifi`, `tqdm` y `pycryptodome` aprobadas (24/10/2026) | `docs/legal/licencias_revisadas.json` |
| Salida del modo sombra | Las infracciones del período sombra se descartan (24/10/2026) | Se descartan antes de arrancar el despachador |
| Llave #17 y `data/faces/` | Se quedan por ahora (24/10/2026) | Sigue como riesgo abierto (W-010) |
| CI de Windows | Observar una semana más, hasta el 31/10/2026 (24/10/2026) | Falla intermitente de Tk (`tk.tcl`) en #37 |
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

## Después de las decisiones del 24/10/2026

| Entrega | PR | Nota |
|---------|----|------|
| Cierre al exportar el Excel de eficiencia | #110 | El aviso de fin vuelve al hilo de Tk por un buzón; antes la app se cerraba |
| Mutación de módulos críticos heredados | #111–#116 | Harness de mutación por importadores; `db_crypto`, `crash_logger`, `drm`, `efficiency_calculator` y `database_manager` ≥ 90 % |
| Decisiones registradas | #117 | Umbrales de D2/D4 en las puertas, licencias aprobadas, esta bitácora |
| Composición del módulo (§5.4) | #118, #119 | Parámetros decididos (4 s, 10 min, 30 días); el módulo se activa solo con licencia `epp` y un modelo que vea casco, chaleco y cabeza |
| EPP en el pipeline de cada cámara | #120 | Evaluación por cámara con overlay; `CameraWorker` sale del waiver W-004 |
| Avisos de la sucursal | #121, #122, #123 | Descarte del período sombra, despachador con reintentos y circuito, retención de 30 días, arranque y cierre con la app |
| Navegación | #124, #125, #126 | "Alertas EPP" y "Cumplimiento EPP" en el menú cuando la licencia incluye el módulo |
| % de cumplimiento | #127 | Tiempo de cada persona en cada zona a partir del seguimiento |
| Escenarios del modo sombra y esta bitácora | #128 | `features/modo_sombra_epp.feature`; SPEC/9 §19 al día |
| EPP en el modo sin interfaz | (este PR) | `main.py` valida la licencia y arma el mismo módulo, overlay y avisos que la GUI (§11, 5.4) |

## Integración en `main`

Todos los PRs del plan (#1 … #108) se mergearon en `main` el 2026-10-23, en este orden y con
**merge commit** (sin squash ni rebase):

1. #1 … #39 (A-01..A-12), con #30 (cambio a la constitución) después de #29.
2. #40 … #48 (A-13..A-18).
3. #49 … #68 (B-01..B-06).
4. C-01..C-14 siguiendo la cadena de bases: #69 … #92, #103, #104, #93 … #102, #105, #106, #107
   (#103 y #104 salieron de dividir C-10 para quedar bajo 400 líneas).
5. #108 (cierre: esta bitácora y SPEC/9 §19).

Las tres pistas partían de A-12 y los arreglos de CI de A-07 (#28) llegaron después de abrir los
PRs de arriba, así que algunas ramas recibieron un merge de `main` antes de su PR, con la suite
completa en verde:

- `-a11` (#36): prueba de fugas de `CameraWorker` (cola con nombre y espera por evento de #28 +
  `DetectorPort` de A-11) y cuatro pruebas del gate que ahora usan la copia versionada del
  repositorio.
- `-c02`, `-c06b`, `-c07b`, `-c08`, `-c11`: filas de `docs/quality/mutantes_equivalentes.md` y
  conteos de W-001/W-003 en `docs/quality/waivers.md`, unidos con los de las pistas A y B.

Se mergeó con los checks `gate (windows-latest)` (fallas heredadas de Tk y rendimiento, #37) y
`licencias` (en rojo por diseño hasta D8 y D9) en rojo, por decisión explícita del dueño del
producto; `gate (ubuntu-latest)` y `mutacion` estaban en verde.

## Bloqueadas

| Entrega / criterio | Motivo | Decisión que falta |
|--------------------|--------|--------------------|
| Gate de licencias en verde (AC-001) | `ultralytics` y `yolov8n.pt` (AGPL) siguen en el runtime hasta A-16; `tkcalendar` ya salió (A-17); `certifi`, `tqdm` y `pycryptodome` aprobadas el 24/10/2026 (#117) | A-16 (D8 autorizada; falta el modelo ONNX, D6) |
| A-13: benchmark real y cierre de ADR-001 | Umbrales fijados (≥ 5 FPS, p95 ≤ 200 ms); faltan el equipo de referencia del cliente y el video etiquetado del piloto | D6 |
| A-15: ONNX como motor por omisión | Falta un modelo ONNX aprobado por la puerta de A-13 | D6 (B-05/B-06 para el modelo de EPP) |
| Release y piloto (C-14) | Build del ejecutable y revisión legal | D9 y el modelo de EPP ([expediente](../legal/revision_d9.md), [runbook](../runbooks/piloto_sombra.md)) |
| B-05/B-06 con datos reales | Captura, etiquetado y entrenamiento con imágenes del sitio | D6 (quién revisa las etiquetas) |
| `pragma: allowlist secret` de C-10 (6/7) | Exclusión nueva de detect-secrets en nombres y valores ficticios | Aprobación humana (§14.4) |
| Merge de `-a08b` (constitución) | Modifica `CLAUDE.md`/`Agents.md` | Aprobación humana |
| Rama `main` protegida (SPEC/9 §0.8) | Es configuración del repositorio en GitHub | Acción humana |
| Llave privada versionada (#17) | Rotar la llave y purgar el historial | Acción humana |

## Deuda detectada (no se arregla en estas entregas)

- `data/faces/` versiona fotos y codificaciones biométricas (`encodings.pkl`) de personas reales (CLAUDE.md §9: datos personales reales): decidir su retiro y la purga del historial.
- En la CI de Windows fallan de forma intermitente dos pruebas heredadas de rendimiento con esperas reales (`test_drop_frame_protocol`, `test_frame_consumption_with_mock_producers`) y una creación de Tk (`init.tcl`); en Linux pasan con cualquier semilla. Pendiente reescribirlas sin esperas reales (CLAUDE.md §4).
- `reportlab` se importa pero no está en `requirements.txt`; `obfuscate.py` no ofusca (W-007, #8).
- WAIVER-#2 pide formatear en un commit aparte cada archivo heredado que un PR toca:
  `src/main_ui.py`, `src/tracking/camera_worker.py` y `src/tracking/tracking_pipeline.py` se
  tocaron en #120–#126 sin formatear. Formatear `main_ui.py` lo llevaría por encima de 500 líneas:
  primero hay que sacarle una responsabilidad (ver abajo).
- Las infracciones no guardan la cámara que las vio (el panel y el reporte agrupan por zona).
- `src/main_ui.py` quedó en 498 líneas (máximo 500): el próximo cambio ahí tiene que sacar
  otra responsabilidad (por ejemplo, el selector de cámaras) a su propio módulo.
- `mypy` no revisa `tests/` y `tests/test_main_ui.py` tiene 3 errores de tipos en la fixture
  `despachador` (#123).
- La CI de Windows falla seguido al crear ventanas Tk (`init.tcl`, `tk.tcl`, aborto
  `0x80000003`) en el paso 8b, también en PRs que no tocan Tk (#119, #120): se observa hasta el
  31/10/2026 por decisión del dueño del producto.
- El reporte de eficiencia heredado falla con `pd.to_datetime` cuando la tabla `tracking` mezcla
  horas con y sin microsegundos (lo dejan así `datetime.now().isoformat()`); el de cumplimiento
  no tiene ese problema.
- `src/detection/people_detector.py` no se usa en la aplicación y lee zonas v1 a mano: proponer
  su retiro en un PR aparte.
- Una corrida del gate se colgó una vez en el paso de pruebas (c08) y pytest-timeout no la cortó;
  no se reprodujo. Vigilar en CI.
- `pip-audit` del gate audita `/home/user/venv311` y no `.venv` si falta `PIPAPI_PYTHON_LOCATION`.

### Cobertura de ramas de los módulos críticos (W-012, aprobado el 26/10/2026)

CLAUDE.md §6 pide 100 % de ramas en `src/security/`, `src/storage/`, `src/analysis/` y `src/ppe/`;
el gate no lo controla por módulo y no hay waiver para lo heredado. Medido en `main` el 26/10/2026:
todo `src/ppe/` y los módulos nuevos de `src/storage/` están al 100 %; los heredados no:
`src/analysis/generar_reporte.py` 0 %, `report_main.py` 42 %, `report_generator.py` 59 %,
`state_manager.py` 94 %, `efficiency_calculator.py` 99 %; `src/security/crash_logger.py` 93 %,
`drm.py` 97 %, `db_crypto.py` 99 %; `src/storage/database_manager.py` 98 %. Propuesta (requiere
aprobación humana, §15): waiver W-012 hasta el 2027-01-26 para esos archivos y un paso nuevo del
gate que exija 100 % de ramas en los módulos críticos que no figuren en el waiver.

El dueño del producto aprobó W-012 el 26/10/2026 (#133). El gate lo controla en el paso
`4e-cobertura-critica` (`scripts/check_cobertura_criticos.py`): exige 100 % de líneas y ramas a los
módulos críticos fuera de `cobertura_critica_waiver` y obliga a sacar de esa lista cada archivo que
llegue al 100 % (trinquete).

## Próxima entrega

Ninguna del lado de los agentes: el módulo de EPP está compuesto y probado de punta a punta con
dobles. Lo que queda es humano: los datos y el etiquetado del sitio (D6) para entrenar el modelo
de EPP, que a su vez destraba A-13, A-15, A-16 y AC-018; la revisión legal (D9) para el release; el
piloto en sombra (AC-017) y la observación de la CI de Windows hasta el 31/10/2026.
