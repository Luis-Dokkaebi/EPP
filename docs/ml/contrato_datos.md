# Contrato de datos del dataset EPP

**Estado:** borrador para aprobación (DoD de la Fase 2, SPEC/9 §8). **Fuente:** SPEC/9 §2.2 a §2.6 y
la skill `mle-workflow` ("Lock the Data Contract"). Las reglas que una máquina puede verificar las
verifica `ml/contrato_datos.py` (columna "Lo verifica"); el resto lo revisa un humano.

## 1. Unidad y clave

| Concepto | Definición |
|----------|------------|
| Unidad (grano) | Una imagen: un frame muestreado de una cámara del piloto. |
| Clave | El nombre de archivo `<camara>_<AAAAMMDD>_<HHMMSS>_<nnnn>.jpg`; `<camara>` es un identificador corto en minúsculas (`a-z`, `0-9`, `-`), nunca un nombre de persona ni una dirección IP. |
| Etiqueta | Cajas alineadas a los ejes, en píxeles de la imagen original, de una clase de la taxonomía. |
| Momento de la etiqueta | Fecha del etiquetado; no hay etiquetas diferidas ni del futuro: la imagen es la única entrada. |

## 2. Taxonomía (decisión D3)

Las categorías del COCO del contrato se numeran desde 1 en el orden de la tabla. La v2 solo agrega
clases al final, así un modelo v1 conserva sus IDs.

| ID | Clase | Versión | Uso |
|----|-------|---------|-----|
| 1 | `persona` | v1 | Seguimiento y dueño del EPP |
| 2 | `cabeza` | v1 | Ancla del casco (y de gafas y barbijo en la v2) |
| 3 | `casco` | v1 | EPP |
| 4 | `chaleco` | v1 | EPP: chaleco o ropa reflectiva (una o dos clases: **PENDIENTE (D3)**) |
| 5 | `manos` | v2 | Ancla de los guantes |
| 6 | `guantes` | v2 | EPP |
| 7 | `gafas` | v2 | EPP |
| 8 | `barbijo` | v2 | EPP |

Lo verifica: `validar_anotaciones` (categorías exactas, en orden y sin huecos).

## 3. Formato de las anotaciones

- **COCO JSON** (`images`, `annotations`, `categories`). CVAT y Label Studio lo exportan de forma
  nativa; `ml/` lo normaliza a este contrato.
- Cada imagen lleva, además de `id`, `file_name`, `width` y `height`, los metadatos de la captura:
  `camara`, `fecha` (`AAAA-MM-DD`), `hora` (`HH:MM:SS`), `turno` y `autorizacion` (identificador del
  documento con el que el cliente autorizó la captura; sin él la imagen no entra al dataset).
- `bbox = [x, y, ancho, alto]` con ancho y alto positivos, dentro de la imagen.
- **Región "ignorar":** una caja con `iscrowd = 1`. El entrenamiento y la evaluación no la cuentan
  ni como acierto ni como error. Se usa para objetos por debajo del tamaño mínimo y para casos
  ambiguos (ver la [guía de etiquetado](guia_etiquetado.md)).
- **Tamaño mínimo:** una caja con el lado menor por debajo de `lado_minimo_px` debe ser región
  "ignorar". El valor depende de la resolución de las cámaras reales: **PENDIENTE (D6)**. La
  validación exige el valor explícito y no tiene uno por omisión.

Lo verifica: `validar_anotaciones` (metadatos obligatorios, nombre de archivo, cajas dentro de la
imagen, tamaño mínimo, IDs de categoría conocidos).

## 4. Split sin fuga de información (SPEC/9 §2.4)

Los frames consecutivos de una cámara son casi idénticos: un split aleatorio infla las métricas.

| Regla | Lo verifica |
|-------|-------------|
| R1. Todas las imágenes de una misma cámara en un mismo día van al mismo split | `validar_split` |
| R2. Al menos una cámara aparece **solo** en test | `validar_split` |
| R3. Los tres splits (`train`, `valid`, `test`) tienen imágenes | `validar_split` |
| R4. Los umbrales se eligen en `valid`; `test` se mira una vez por candidato a promoción | Revisión humana (bitácora) |

Qué cámaras y qué días van a cada split: **PENDIENTE (D6)**; se registra en el manifiesto del dataset.

## 5. Fuentes y licencias (SPEC/9 §2.3)

| Licencia de la fuente | Resultado |
|-----------------------|-----------|
| `propia-con-autorizacion` (cámaras del cliente con autorización escrita), `CC-BY-4.0`, `CC0-1.0`, `MIT` | Permitida; se registra en el manifiesto y en THIRD_PARTY_NOTICES |
| `CC-BY-NC*` (incluye **SH17**), `CC-BY-SA-NC*`, `AGPL*`, `GPL*`, `PML*` | Prohibida: contamina los pesos distribuidos |
| Cualquier otra o vacía | Revisión humana antes de usarla; mientras tanto, falla |

Lo verifica: `validar_licencia_de_fuente`.

## 6. Datos personales y custodia (SPEC/9 §2.6, CLAUDE.md §9)

- Las imágenes contienen rostros: **nunca** van a git. La herramienta de captura se niega a
  escribir dentro del repositorio.
- Las etiquetas no llevan nombres de personas ni la salida del reconocimiento facial.
- Almacenamiento cifrado con acceso restringido; la herramienta de etiquetado (CVAT o Label Studio)
  es autoalojada.
- Plazo de retención, difuminado de rostros, base legal y consentimiento: **PENDIENTE (D5)**.
- Los logs y los manifiestos no guardan imágenes ni rostros; solo nombres de archivo y hashes.

## 7. Versionado

- Versión `vMAYOR.MENOR` (la primera es `v0.1`). Cambiar la taxonomía sube la mayor; agregar
  imágenes o corregir etiquetas sube la menor.
- Manifiesto con el sha256 de cada imagen y de cada archivo de anotaciones, el split de cada imagen,
  la taxonomía y las fuentes con su licencia (B-03).
- Cada modelo entrenado registra la versión exacta del dataset (contrato de `mle-workflow`).

## Aprobación

| Rol | Nombre | Fecha |
|-----|--------|-------|
| Responsable de producto | PENDIENTE | |
| Responsable legal o de privacidad (D5) | PENDIENTE | |
