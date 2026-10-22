# ADR-001: Motor de IA con licencia Apache/MIT

## Estado

**Provisional** (2026-10-22). Se confirma o se cambia con el benchmark de la entrega A-13
(`docs/benchmarks/motor_ia.md`, SPEC/9 §1.5). La decisión de negocio sobre el hardware (D2) está
abierta: el benchmark se corre en CPU y el proveedor de ejecución queda configurable.

## Contexto

- El ejecutable para Windows es cerrado y se vende con protección DRM.
- Hoy la detección usa Ultralytics YOLOv8 (`ultralytics==8.1.15` y `yolov8n.pt`), con licencia
  AGPL-3.0. Según Ultralytics, también los modelos entrenados con su código quedan bajo AGPL; el
  uso comercial cerrado exige su licencia Enterprise, que es de pago (SPEC/9 §3.1 y §20).
- El gate de licencias (`scripts/check_licenses.py`, A-05) falla hoy por esa razón (AC-001).
- Hardware objetivo declarado en el plan: CPU i3/i5 de oficina, sin GPU garantizada.
- Hoy se parchea `torch.load` con `weights_only=False` para cargar YOLO (`src/main_ui.py`,
  CR-05): una superficie de deserialización insegura que desaparece con ONNX.

## Opciones

| Opción | A favor | En contra |
|--------|---------|-----------|
| Ultralytics Enterprise | Sin migración de código | Costo recurrente; dependencia comercial; sigue usando PyTorch en el `.exe` |
| RF-DETR (Nano, Small, Medium, Large) + ONNX Runtime | Apache-2.0 en esos tamaños; exporta a ONNX; buen rendimiento en objetos chicos | Sin cifras oficiales en CPU; los tamaños Atto, Femto, Pico, XL y 2XL son PML 1.0 (prohibidos) |
| YOLOX + ONNX Runtime | Apache-2.0; muy liviano en CPU; exporta a ONNX y OpenVINO | Sin actividad desde 2023 |
| D-FINE + ONNX Runtime | Apache-2.0 | Los checkpoints entrenados con Objects365 pueden tener términos propios |

## Decisión

**Provisional:** RF-DETR (solo tamaños Apache-2.0) entrenado con `rfdetr` fuera del ejecutable,
exportado a ONNX y ejecutado con ONNX Runtime (MIT), detrás de un puerto `DetectorPort` (A-10).
El ejecutable no incluye PyTorch ni Ultralytics.

Se confirma solo si el benchmark de A-13 cumple los umbrales que fije el dueño del producto (D2/D4);
mientras tanto el puerto permite cambiar de motor sin tocar el dominio.

## Consecuencias

- Fase 1 en pasos de `migration`: expandir (puerto + adaptador Ultralytics temporal), migrar
  (adaptador ONNX, motor por defecto tras el benchmark) y contraer (quitar Ultralytics, torch y los
  `.pt`, A-16, bloqueado por D8).
- `models/manifest.json` declara cada modelo con su hash y licencias; el verificador por manifiesto
  (A-14) rechaza un modelo no declarado.
- Riesgo R5: el rendimiento de un modelo tipo DETR en CPU puede ser menor al esperado; YOLOX queda
  como alternativa liviana.
- **Reversión:** mientras no se ejecute A-16, volver a Ultralytics es cambiar el motor configurado;
  después de A-16, es revertir ese PR. Ninguna opción toca los datos persistidos.
