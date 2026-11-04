# Expediente para la revisión legal (decisión D9)

> **Esto no es asesoría legal.** Es la lista de hechos verificados en el repositorio que la
> persona responsable de la revisión legal (D9, SPEC/9 §4) necesita para decidir si el producto
> se puede distribuir. El release 2.0.0 (C-14) queda bloqueado hasta que D9 se resuelva.

Estado al cierre de A-18. Cada punto dice qué se encontró, dónde, qué ya se hizo y qué decisión
humana falta.

## 1. Motor de IA: de Ultralytics (AGPL-3.0) a RF-DETR (Apache-2.0)

- **Hecho (2026-11-04):** `ultralytics`, `torch`, `torchvision` y los dos `yolov8n.pt` salieron
  del producto. La app detecta con RF-DETR Nano (pesos y código Apache-2.0, `rfdetr==1.11.2`)
  exportado a ONNX y ejecutado con ONNX Runtime (MIT): `models/rfdetr/rfdetr-nano-coco-int8.onnx`.
- **Falta (decisión humana):** RF-DETR se preentrenó con Objects365 y se afinó con COCO 2017
  (CC-BY-4.0, con imágenes de Flickr de licencias variadas). El gate marca Objects365 para que
  el abogado confirme sus términos.

## 2. `tkcalendar` (GPLv3)

- **Hecho:** reemplazado por un selector de fecha propio (A-17) y fuera del build: el
  `gui_app.spec` que lo nombraba se borró con el paso a Nuitka.

## 3. Reconocimiento facial: de dlib a YuNet + SFace

- **Hecho (2026-11-04):** `face_recognition`/dlib y su predictor de 68 puntos (iBUG 300-W,
  uso comercial restringido) salieron del producto. El reconocimiento usa
  `src/recognition/motor_facial_opencv.py` con dos modelos de opencv_zoo en `models/rostros/`:
  YuNet (detección y 5 puntos, licencia MIT) y SFace (vector de 128, Apache-2.0). La demostración
  de la GUI dibuja los 5 puntos de YuNet.
- **Falta (decisión humana):** las licencias de los pesos son permisivas, pero los datos de
  entrenamiento no: YuNet se entrenó con WIDER FACE (solo investigación no comercial) y
  opencv_zoo no publica el dataset de SFace (el repositorio original usa CASIA-WebFace / MS1M).
  El gate de licencias los marca por eso. Ningún modelo facial abierto se entrenó con datos de
  uso comercial claro: el abogado decide si el riesgo se acepta, se compra un modelo comercial o
  se entrena uno propio con fotos con consentimiento.

## 4. PyArmor y PyInstaller

- **Hecho (2026-11-04):** salieron del build. El ejecutable se compila con Nuitka 2.8.10
  (Apache-2.0; desde Nuitka 4.0 la licencia es AGPL-3.0 con una excepción que libera el
  ejecutable compilado, por eso se fija la 2.8.10). `requirements-build.txt` lo declara.

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
- **Hecho (2026-11-04):** `compilar_exe.bat` lo genera desde el entorno del build y
  `setup_oficina.iss` lo instala junto al ejecutable.
- **Falta:** revisar a mano los paquetes marcados "revisar a mano" (sin texto de licencia).

## 7. Licencias pendientes de aprobación humana

- [Licencias revisadas](licencias_revisadas.json): las entradas con `aprobado_por: null` son
  propuestas y no cuentan para el gate hasta que una persona las firme.

## Verificación

- Gate de licencias: `python scripts/check_licenses.py` sobre el entorno de runtime (job
  `licencias` de CI). Debe quedar en verde antes del release (AC-001).
- Este expediente se actualiza en cada PR que cambie un punto de la lista.
