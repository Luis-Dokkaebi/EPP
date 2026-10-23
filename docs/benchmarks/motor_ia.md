# Bitácora del benchmark de motores de IA (SPEC/9 §1.5, A-13)

Decide el motor de ADR-001. **Solo se publican números de corridas reales**: no se redondean ni
se inventan. Hoy la tabla está vacía porque faltan los insumos del piloto.

## Estado

- Herramienta lista: `tools/bench_detectores.py` (pruebas en `tests/test_bench_detectores*.py`).
- **Bloqueado** por:
  - **D2** (hardware real del sitio): los umbrales de FPS y p95 de `UMBRALES_DE_PROMOCION` son
    `None` y la puerta falla cerrada hasta que se fijen;
  - el clip de validación del cliente y de 200 a 500 frames etiquetados con personas;
  - los modelos ONNX candidatos (RF-DETR Nano/Small, YOLOX, D-FINE) exportados y declarados en
    `models/manifest.json` con `clases`, `media` y `desviacion`.

## Cómo correrlo (en el equipo del piloto)

```bash
python -m tools.bench_detectores --video clip_piloto.mp4 --etiquetas etiquetas.json \
    --hardware "<CPU exacta>, solo CPU" --confianza-minima 0.5 \
    --variante baseline-yolov8n ultralytics yolov8n.pt "estado actual (AGPL)" \
    --variante rfdetr-nano-onnx onnx models/rfdetr_nano.onnx "más preciso en objetos chicos"
```

La primera variante es la referencia (`ref`). Cada fila impresa se pega tal cual en la tabla.
Antes de correrlo, el dueño del producto fija en `UMBRALES_DE_PROMOCION` el FPS mínimo por cámara
(con N cámaras simultáneas) y el p95 máximo por frame (D2). El recall de persona de cada variante
debe ser mayor o igual al del baseline.

## Resultados

Variante | Hipótesis | Hardware | FPS | p95 ms | RAM MB | Recall persona | ¿Pasa? | Notas
---------|-----------|----------|-----|--------|--------|----------------|--------|------
