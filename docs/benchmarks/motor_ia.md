# Bitácora del benchmark de motores de IA (SPEC/9 §1.5, A-13)

Decide el motor de ADR-001. **Solo se publican números de corridas reales**: no se redondean ni
se inventan. Hoy la tabla está vacía porque faltan los insumos del piloto.

## Estado

- Herramienta lista: `tools/bench_detectores.py` (pruebas en `tests/test_bench_detectores*.py`).
- **Bloqueado** por:
  - el equipo del piloto: D2 (24/10/2026) eligió CPU Intel con OpenVINO y fijó
    `UMBRALES_DE_PROMOCION` en ≥ 5 FPS por cámara y p95 ≤ 200 ms; falta medir en ese equipo;
  - el clip de validación del cliente y de 200 a 500 frames etiquetados con personas;
  - los modelos ONNX candidatos (RF-DETR Nano/Small, YOLOX, D-FINE) exportados y declarados en
    `models/manifest.json` con `clases`, `media` y `desviacion`.

## Cómo correrlo (en el equipo del piloto)

```bash
python -m tools.bench_detectores --video clip_piloto.mp4 --etiquetas etiquetas.json \
    --hardware "<CPU exacta>, solo CPU" --confianza-minima 0.5 \
    --variante rfdetr-nano-int8 onnx models/rfdetr/rfdetr-nano-coco-int8.onnx "estado actual" \
    --variante rfdetr-small onnx models/rfdetr/rfdetr-small.onnx "más preciso en objetos chicos"
```

La primera variante es la referencia (`ref`). Cada fila impresa se pega tal cual en la tabla.
Antes de correrlo, el dueño del producto fija en `UMBRALES_DE_PROMOCION` el FPS mínimo por cámara
(con N cámaras simultáneas) y el p95 máximo por frame (D2). El recall de persona de cada variante
debe ser mayor o igual al del baseline.

## Resultados

Variante | Hipótesis | Hardware | FPS | p95 ms | RAM MB | Recall persona | ¿Pasa? | Notas
---------|-----------|----------|-----|--------|--------|----------------|--------|------

## Medición previa: RF-DETR Nano fp32 contra int8 (2026-11-04)

No reemplaza la corrida del piloto: no hay etiquetas, así que mide **acuerdo** entre las dos
versiones del mismo modelo, no recall. Hardware: contenedor Linux de la nube, solo CPU.

- Exportación: `rfdetr==1.11.2`, `RFDETRNano().export()` (entrada 384x384, salidas `dets` y
  `labels` con 91 clases de COCO: persona = 1, celular = 77). El fp32 pesa 117,6 MB, más que el
  límite de 100 MB por archivo de GitHub.
- Cuantización: `onnxruntime.quantization.quantize_dynamic(QInt8, per_channel=True)`, 37,8 MB.
- 40 capturas de `data/snapshots/` (solo lectura): fp32 encontró 55 personas con confianza
  > 0,4; int8 encontró 52 de esas 55 (IoU > 0,7) con la misma regla y las 55 bajando su umbral a
  0,3 (las 3 que faltaban estaban en el borde). Diferencia media de confianza: 0,019.
- Latencia media por frame: fp32 125 ms, int8 88 ms.

Decisión del dueño del producto (2026-11-04): RF-DETR Nano int8 es el motor de la app (ADR-001).
