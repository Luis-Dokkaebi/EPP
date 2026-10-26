# Runbook: entrenamiento, análisis de errores y promoción del modelo EPP

**Quién:** la persona responsable del modelo, en un equipo de entrenamiento (no el del cliente).
**Herramientas:** `ml/train.py`, `ml/entrenador_rfdetr.py`, `ml/promotion_gates.py` (B-04).
**Estado:** bloqueado. Falta el dataset v0.1 (D6, [runbook de etiquetado](etiquetado.md)) y los
umbrales de promoción (D4 y D2). **Ningún entrenamiento se ha corrido todavía**; la
[bitácora](../ml/bitacora.md) está vacía hasta la primera corrida real.

## 1. Entorno aparte (una vez por equipo)

```bash
python3.11 -m venv ~/venv-epp-ml
~/venv-epp-ml/bin/python -m pip install -r ml/requirements-ml.txt
~/venv-epp-ml/bin/python -m pip install pip-audit==2.7.3 pip-licenses==5.5.5
~/venv-epp-ml/bin/pip-audit            # debe terminar sin vulnerabilidades
~/venv-epp-ml/bin/pip-licenses --format=markdown > licencias_entrenamiento.md
```

- Este entorno **no** es el del producto: no instalar `requirements.txt` aquí ni `rfdetr` en el
  entorno de la app. import-linter falla si `src/` importa `ml/`.
- Revisar `licencias_entrenamiento.md`: ningún paquete AGPL ni GPL; `certifi` y `tqdm` (MPL-2.0)
  esperan la revisión humana anotada en `ml/requirements-ml.txt`.
- Con GPU NVIDIA, cambiar el índice de PyTorch y el sufijo `+cpu` por los de CUDA y repetir
  pip-audit.

## 2. Antes de entrenar (puertas fijadas de antemano)

1. Los umbrales de `PUERTAS_DE_PROMOCION` en `ml/promotion_gates.py` quedaron fijados el
   24/10/2026, antes de cualquier entrenamiento (D4: recall por evento de casco y de chaleco ≥ 0,90,
   falsas alarmas ≤ 1 por cámara y por hora, recall de persona no peor que el modelo actual;
   D2: ≥ 5 FPS por cámara). Ese PR es la evidencia de que no se ajustaron mirando resultados:
   cambiarlos exige una decisión nueva del negocio, nunca un resultado de entrenamiento.
2. Verificar el dataset: `python -m ml.manifiesto_dataset verificar ...` (código 0).
3. Commitear todo: el entrenamiento se niega a correr con cambios sin commitear.

## 3. Entrenar el baseline y las variantes (SPEC/9 §3.2)

```bash
~/venv-epp-ml/bin/python -m ml.entrenador_rfdetr --dataset /ruta/cifrada/dataset/v0.1 \
    --manifiesto ml/datasets/v0.1/manifest.json --tamano small --resolucion 512 \
    --epocas <E> --lote <L> --tasa <T> --semilla 7 --salidas /ruta/cifrada/artefactos
```

- **Baseline:** RF-DETR Small, resolución 512. Variantes, una hipótesis por corrida: Nano (más
  rápido), Medium (objetos chicos), mayor resolución (múltiplo de 32).
- Épocas, lote y tasa: elegirlos con el conjunto `valid`; **nunca** mirar `test` para decidir.
- Cada corrida crea `epp-<sha>-<huella>/` con `registro.json` (código, configuración, dataset,
  sha256 de los pesos) y no sobrescribe corridas anteriores. Los pesos **no** van a git.
- Las métricas por caja (AP50, recall por clase) quedan en los registros de RF-DETR dentro de la
  carpeta del artefacto. Las métricas de evento (recall de infracciones, falsas alarmas por hora)
  se miden con los videos dorados, con la ventana temporal de la Fase 4, y se anotan en la
  bitácora.

## 4. Análisis de errores (SPEC/9 §3.5)

Después de cada corrida, sobre `valid`:

1. Separar falsos positivos, falsos negativos y "no verificables".
2. Agruparlos por slice: distancia (persona chica o grande), iluminación, cámara, oclusión, color
   del EPP.
3. Traducir cada grupo grande en un movimiento: mejores etiquetas, más datos de ese slice, otro
   umbral u otro fallback de producto.
4. Cada error importante se agrega como caso del set dorado (prueba de regresión).
5. Registrar la iteración en la [bitácora](../ml/bitacora.md) con la plantilla *Observation Ledger*.

## 5. Promoción

```bash
~/venv-epp-ml/bin/python -c "import json, sys; from ml.promotion_gates import exigir_promocion; \
exigir_promocion(json.load(open(sys.argv[1])))" metricas_evento.json
```

- `metricas_evento.json` tiene una clave por puerta (`recall_evento_casco`, ...). Se mide **una
  sola vez** sobre `test` por candidato.
- Mientras D4 o D2 estén pendientes, la promoción falla siempre y nombra la decisión que falta.
- Si pasa: exportar a ONNX, probar la paridad, completar la ficha del modelo y registrar el
  artefacto en el manifiesto de modelos ([runbook de exportación](exportacion_modelo.md)).

## 6. Qué no hacer

- No usar SH17 ni datasets no comerciales; no usar tamaños PML de RF-DETR (Atto, Femto, Pico,
  XL, 2XL): la configuración los rechaza.
- No subir pesos ni imágenes a git ni a servicios de terceros.
- No relajar un umbral después de ver resultados: se corrige con un PR nuevo que explique por qué,
  aprobado por el responsable de producto.
