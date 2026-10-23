# Runbook: etiquetado, acuerdo y versionado del dataset EPP

**Quién:** las personas que etiquetan y la persona responsable del dataset.
**Herramientas:** `tools/acuerdo_etiquetado.py`, `ml/convertir_etiquetas.py` y
`ml/manifiesto_dataset.py` (B-03). **Reglas:** [guía de etiquetado](../ml/guia_etiquetado.md) y
[contrato de datos](../ml/contrato_datos.md).
**Estado:** bloqueado por D6 (no hay imágenes reales) y por la aprobación de la guía. Ningún agente
etiqueta ni ve las imágenes: es trabajo humano.

## 1. Preparar la herramienta (una vez)

1. Instalar **CVAT** o **Label Studio** en un equipo propio con disco cifrado; sin acceso público.
2. Crear un proyecto con las etiquetas de la taxonomía v1, escritas exactamente así: `persona`,
   `cabeza`, `casco`, `chaleco`. Agregar a cada etiqueta el atributo booleano `ignorar` y, a
   `chaleco`, el atributo `mameluco` (PENDIENTE (D3), ver la guía).
3. Subir las imágenes de la captura (`tools/capturar_dataset.py`). No subir `metadatos.jsonl`.

## 2. Etiquetar

- Seguir la guía al pie de la letra. Ante la duda, `ignorar`.
- Elegir al azar el **10 %** de las imágenes, repartido entre todas las cámaras, y crear para él
  una segunda tarea que etiqueta otra persona sin ver la primera.

## 3. Medir el acuerdo (antes de seguir)

Exportar las dos tareas del 10 % como **COCO 1.0** (`a.json` y `b.json`) y correr:

```bash
python -m tools.acuerdo_etiquetado a.json b.json --umbral <U> --reporte acuerdo.json
```

- `<U>` es el umbral de acuerdo aprobado con la guía: **PENDIENTE**. Sin `--umbral`, la medición se
  informa pero sale con código 1: nada se aprueba.
- Código 0: todas las clases superan el umbral. Código 1: hay clases a redefinir (se listan) o
  falta el umbral. Código 2: los dos archivos no cubren las mismas imágenes o categorías.
- Si una clase queda por debajo: corregir su definición en la guía, volver a etiquetar esa clase y
  medir de nuevo. Guardar `acuerdo.json` en la bitácora del dataset.

## 4. Convertir al contrato

Exportar el proyecto completo como COCO 1.0 y unirlo con los metadatos de la captura:

```bash
python -m ml.convertir_etiquetas --exportado proyecto.json \
    --metadatos /ruta/cifrada/dataset/crudo/metadatos.jsonl --taxonomia v1 \
    --salida /ruta/cifrada/dataset/v0.1/anotaciones.json
```

Una imagen sin metadatos de captura (sin autorización registrada) o con otro tamaño se rechaza.
Copiar las imágenes `.jpg` a la misma carpeta que `anotaciones.json`, sin renombrarlas.

## 5. Versionar

```bash
python -m ml.manifiesto_dataset crear --carpeta /ruta/cifrada/dataset/v0.1 --version v0.1 \
    --taxonomia v1 --lado-minimo <D6> --fuente "Piloto <cliente>=propia-con-autorizacion" \
    --camara-test <cámara reservada> --dia-valid <AAAA-MM-DD> \
    --salida ml/datasets/v0.1/manifest.json
```

- `--lado-minimo` y qué cámaras y días van a test y a valid: **PENDIENTE (D6)**.
- El comando valida todo el contrato (taxonomía, metadatos, cajas, licencias, imágenes sin editar
  y split sin fuga) y no escribe nada si algo falla.
- El manifiesto **sí** va a git (solo nombres y hashes); las imágenes **nunca**.
- Anotar la huella que imprime en la bitácora del dataset: la registrará cada entrenamiento.

Antes de cada entrenamiento, y después de mover o copiar el dataset:

```bash
python -m ml.manifiesto_dataset verificar --carpeta /ruta/cifrada/dataset/v0.1 \
    --manifiesto ml/datasets/v0.1/manifest.json
```

Código 0: intacto. Código 1: lista los archivos faltantes, cambiados o sobrantes; no entrenar
hasta resolverlo.

## 6. Checklist de cierre (DoD de la Fase 2)

- [ ] Guía de etiquetado aprobada, con el umbral de acuerdo.
- [ ] Acuerdo medido sobre el 10 % y aprobado (código 0), con `acuerdo.json` guardado.
- [ ] `ml/datasets/v0.1/manifest.json` creado, commiteado y verificado.
- [ ] Fuentes y licencias registradas en el manifiesto y en THIRD_PARTY_NOTICES.
