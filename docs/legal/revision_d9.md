# Expediente para la revisión legal (decisión D9)

> **Esto no es asesoría legal.** Es la lista de hechos verificados en el repositorio que la
> persona responsable de la revisión legal (D9, SPEC/9 §4) necesita para decidir si el producto
> se puede distribuir. El release 2.0.0 (C-14) queda bloqueado hasta que D9 se resuelva.

Estado al cierre de A-18. Cada punto dice qué se encontró, dónde, qué ya se hizo y qué decisión
humana falta.

## 1. Motor de IA con licencia AGPL-3.0 (Ultralytics)

- **Hecho:** `ultralytics==8.1.15` en `requirements.txt` y los pesos `yolov8n.pt` (raíz) y
  `models/yolov8/yolov8n.pt` son AGPL-3.0 (ver [manifiesto de modelos](../../models/manifest.json)).
- **Hecho en el plan:** puerto `DetectorPort`, adaptador ONNX Runtime (MIT) e interruptor
  `config.DETECTION_ENGINE` (A-10 a A-15). El gate de licencias falla mientras sigan instalados.
- **Falta:** un modelo ONNX con licencia permisiva que pase la puerta de A-13 (umbrales de D2) y
  la autorización D8 para contraer (A-16: quitar `ultralytics` y `torch`, borrar los `.pt`).

## 2. `tkcalendar` (GPLv3)

- **Hecho:** reemplazado por un selector de fecha propio (A-17); ya no está en `requirements.txt`.
- **Falta:** `gui_app.spec` todavía lo nombra en `hiddenimports` y en un `collect_all` protegido;
  se limpia con el build en A-16 (D8). Prueba de humo manual de la vista de reportes.

## 3. Modelo de 68 puntos de dlib (`face_recognition_models`)

- **Hecho:** `src/gui_app.py` (modo demostración de marcas faciales) llama a
  `face_recognition.face_landmarks`, que por omisión usa el predictor de 68 puntos entrenado con
  iBUG 300-W, cuyo uso comercial está restringido (verificar los términos vigentes).
- **Hecho:** aunque la demostración usara el modelo de 5 puntos, el paquete
  `face_recognition_models` distribuye el archivo de 68 puntos y `face_recognition` lo carga al
  importarse; cambiar la llamada no basta para dejar de distribuirlo.
- **Decisión humana:** (a) obtener permiso de uso comercial; (b) eliminar la demostración y
  sustituir `face_recognition` por dlib con solo el predictor de 5 puntos y el modelo de
  codificación (requiere cambiar el build, D8); o (c) aceptar el riesgo por escrito.

## 4. PyArmor

- **Hecho:** `pyarmor==8.4.6` en `requirements.txt`; `src/gui/views.py` dice que se extrajo de
  `main_ui.py` "para respetar el límite de ofuscación de PyArmor trial". `obfuscate.py` hoy copia
  el código sin ofuscar (waiver W-007, #8, prueba `xfail` estricta en `tests/test_obfuscate_pipeline.py`).
- **Decisión humana:** confirmar la licencia comercial de PyArmor para la versión usada o
  retirar la ofuscación del build. Sin licencia, el modo de prueba no es apto para distribuir.

## 5. Datos personales en el repositorio

- **Hecho:** `data/faces/` versiona fotos de personas identificadas por nombre y
  `data/faces/encodings.pkl` (codificaciones biométricas). Son datos personales y biométricos.
- **Hecho:** el código nuevo no los lee en pruebas (CLAUDE.md §16: la base y los datos de prueba
  viven en `tmp_path`).
- **Decisión humana:** base legal y consentimiento de esas personas; si no los hay, borrarlos y
  purgar el historial de git (reescritura de historia: requiere autorización explícita).

## 6. Avisos de atribución

- **Hecho:** `scripts/generar_avisos_terceros.py` genera `THIRD_PARTY_NOTICES.txt` desde el
  entorno de runtime y el manifiesto (A-18); el job `licencias` de CI lo publica como artefacto.
- **Falta:** generarlo desde el entorno del ejecutable final, revisar los paquetes marcados
  "revisar a mano" (sin texto de licencia) e incluirlo en el instalador `setup_oficina.iss` (D8).

## 7. Licencias pendientes de aprobación humana

- [Licencias revisadas](licencias_revisadas.json): las entradas con `aprobado_por: null` son
  propuestas y no cuentan para el gate hasta que una persona las firme.

## Verificación

- Gate de licencias: `python scripts/check_licenses.py` sobre el entorno de runtime (job
  `licencias` de CI). Debe quedar en verde antes del release (AC-001).
- Este expediente se actualiza en cada PR que cambie un punto de la lista.
