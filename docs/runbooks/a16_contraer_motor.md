# Runbook humano: A-16, contraer la migración del motor (requiere D8)

Pasos para retirar Ultralytics y torch del producto (SPEC/9 §1.10). Los agentes no los
ejecutan: tocan el build y binarios, y D8 está sin responder (se trata como NO).

## Requisitos previos (todos)

1. **D8 autorizada** por escrito.
2. **Modelo ONNX aprobado:** el benchmark de A-13 corrido con el video etiquetado del piloto
   (`python -m tools.bench_detectores ...`, ver [bitácora](../benchmarks/motor_ia.md)) con los
   umbrales de D2 fijados en `UMBRALES_DE_PROMOCION` y el veredicto "sí".
3. El modelo declarado en `models/manifest.json` (archivo, sha256, licencias, `clases`,
   `media`, `desviacion`) y `python scripts/generar_manifiesto_embebido.py` ejecutado.

## Pasos (un PR, con el Quality Gate en verde)

1. `config/config.py`: `MODEL_PATH` al `.onnx` y `DETECTION_ENGINE = "onnx"`. Correr la app y el
   benchmark una vez con ONNX antes de borrar nada (reversión inmediata: volver a
   `"ultralytics"`).
2. Quitar `ultralytics` y `torch` (y lo que solo ellos traían) de `requirements.txt` y
   `requirements-ci.txt`; `pip-audit` limpio.
3. Borrar el camino heredado: `src/inference/adapters/ultralytics_detector.py`,
   `MOTOR_ULTRALYTICS` y `_cargar_yolo` en `src/composition.py` (con el parche de `torch.load`),
   el interruptor `DETECTION_ENGINE`, `src/detection/person_detector.py` y sus pruebas, y la
   precarga de `torch` en `src/gui_app.py`. AC-005: `grep -rn "torch.load\|weights_only" src/`
   sin resultados, con una prueba que lo verifique.
4. Borrar `yolov8n.pt` y `models/yolov8/yolov8n.pt` (binarios: instrucción explícita) y sus
   entradas del manifiesto; regenerar el manifiesto embebido.
5. `gui_app.spec`: quitar `ultralytics`, `torch`, `tkcalendar` y `babel.numbers` de
   `hiddenimports` y sus `collect_all`; agregar `onnxruntime` y el `.onnx` como `datas`.
   Aplicar lo que decida D9 sobre `face_recognition_models` (ver
   [expediente legal](../legal/revision_d9.md)).
6. El job `licencias` de CI debe quedar en verde (AC-001); quitar `continue-on-error` y cerrar
   el waiver W-011 (#18).

## Prueba de humo del ejecutable (AC-003, en Windows)

Documentarla en el PR con capturas o registro; **no se declara aprobada sin ejecutarla**.

- [ ] `compilar_exe.bat` termina sin errores en una máquina limpia.
- [ ] El `.exe` arranca en un equipo **sin** `ultralytics` ni `torch` instalados.
- [ ] Detecta personas en una cámara real y persiste el tracking (tablas con filas nuevas).
- [ ] La vista de reportes genera asistencia y eficiencia (también con un rango inválido: avisa).
- [ ] La activación de licencia DRM y el módulo EPP (D10) funcionan.
- [ ] El instalador incluye `THIRD_PARTY_NOTICES.txt` generado desde el entorno del ejecutable.

## Reversión

Antes del paso 3: `DETECTION_ENGINE = "ultralytics"`. Después: reinstalar el instalador 1.3.0,
que se conserva como artefacto.
