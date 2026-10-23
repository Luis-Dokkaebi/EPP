# Runbook: exportar el modelo EPP a ONNX y declararlo en el manifiesto

**Quién:** la persona responsable del modelo, en el entorno de entrenamiento
([runbook de entrenamiento](entrenamiento.md)). **Herramientas:** `ml/export_onnx.py`,
`ml/paridad.py`. **Estado:** bloqueado hasta que un modelo pase las puertas de promoción (D4, D2).
El `.onnx` es un binario: se agrega al repositorio solo con la autorización explícita de D8.

## 1. Exportar

```bash
~/venv-epp-ml/bin/python -m ml.export_onnx \
    --registro /ruta/cifrada/artefactos/epp-<sha>-<huella>/registro.json \
    --manifiesto-dataset ml/datasets/v0.1/manifest.json \
    --version 0.1.0 --archivo models/epp/epp-0.1.0.onnx > entrada_manifiesto.json
```

Deja `inference_model.onnx` en la carpeta del artefacto (opset 17, resolución del entrenamiento)
e imprime la entrada para `models/manifest.json` con su sha256, licencias, fuentes del dataset y
catálogo de clases.

## 2. Probar la paridad (antes de declarar nada)

- Elegir un conjunto **fijo** de 20 a 50 imágenes de `valid` (nombres anotados en la bitácora) y
  preprocesarlas como lo hace el adaptador de la app (`DetectorOnnx`: BGR a RGB, redimensión a la
  entrada, normalización con la media y la desviación del modelo, NCHW float32).
- Correr `ml.paridad.exigir_paridad(referencia, sesion, tensores)` con
  `sesion = onnxruntime.InferenceSession("inference_model.onnx")`.
- La tolerancia (rtol 1e-3, atol 1e-5) está fijada en `ml/paridad.py` con su justificación.
  **No se amplía para que pase** (CLAUDE.md §14.3): si falla, se investiga la exportación.
- **PENDIENTE:** el adaptador `ReferenciaPort` del modelo PyTorch. Debe devolver las salidas
  crudas (`dets`, `labels`) del mismo módulo que rfdetr 1.11.2 traza al exportar
  (`RFDETR.export` usa una copia de `model.model` en modo export). Hay que escribirlo y probarlo
  con rfdetr instalado; no se pudo verificar en este entorno sin pesos reales.
- Verificar además, con una imagen conocida, que el índice de clase de `labels` coincide con el
  catálogo de la entrada (persona 1, cabeza 2, casco 3, chaleco 4).

## 3. Ficha del modelo

Copiar [la plantilla](../ml/ficha_modelo_plantilla.md) como `models/cards/epp-v0.1.md` y
completarla con números reales de la bitácora y de las puertas de promoción.

## 4. Declarar en `models/manifest.json` (requiere D8)

1. Copiar el `.onnx` a la ruta de `--archivo` (`models/epp/epp-0.1.0.onnx`).
2. Agregar el contenido de `entrada_manifiesto.json` al arreglo `modelos` de
   `models/manifest.json`, sin tocar las otras entradas (el modelo anterior queda para la
   reversión, SPEC/9 §9.7).
3. Si existe `scripts/generar_manifiesto_embebido.py` (A-14), regenerar el manifiesto embebido que
   usa el verificador de modelos.
4. Correr el gate de licencias: el hash debe coincidir y ninguna licencia debe estar prohibida.
   La licencia de datos propia (`propia-con-autorizacion`) hoy no la reconoce el gate de
   licencias: necesita la aprobación humana registrada en `docs/legal/` o un ajuste del gate.
5. Abrir el PR con la ficha, la entrada del manifiesto, la salida de la paridad y la de las
   puertas de promoción.

## 5. Reversión

El modelo anterior sigue en el manifiesto: volver a él es cambiar la configuración, no
reentrenar. Nunca se borra la entrada de un modelo que estuvo en producción.
