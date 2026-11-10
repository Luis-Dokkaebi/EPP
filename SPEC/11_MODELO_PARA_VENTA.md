# 11. MODELO PARA VENTA: qué modelos usar, cómo entrenarlos y cómo dejarlos listos para vender

**Estado:** Plan para revisión del dueño del producto
**Revisión:** 2 (respuestas del dueño del producto, 2026-11-10)
**Fecha:** 2026-11-10
**Preparado para:** Luis (dueño del producto)
**Documento hermano:** [`SPEC/10_DEMO_TRIAL.md`](10_DEMO_TRIAL.md) (la prueba de 14 días y el cobro).
**Base:** `SPEC/9_PLAN_EPP_Y_LICENCIA.md`, `docs/adr/001-motor-ia.md`, `docs/ml/`, `ml/` y
`docs/runbooks/`.

> Las licencias se verificaron en las fuentes listadas al final el 2026-11-10. Las licencias de
> modelos y datasets cambian: **antes de cada release se vuelven a verificar** en la fuente
> original y se anotan en `models/manifest.json`. Esto no es asesoría legal (decisión D9).

---

## Índice

0. [Respuesta corta](#0-respuesta-corta)
1. [Qué necesita el producto de un modelo](#1-qué-necesita-el-producto-de-un-modelo)
2. [Detectores de objetos: comparación](#2-detectores-de-objetos-comparación)
3. [Reconocimiento facial: comparación](#3-reconocimiento-facial-comparación)
4. [Herramientas para etiquetar más rápido](#4-herramientas-para-etiquetar-más-rápido)
5. [Datos de entrenamiento con licencia comercial](#5-datos-de-entrenamiento-con-licencia-comercial)
6. [Entrenar con una GPU de 6 GB](#6-entrenar-con-una-gpu-de-6-gb)
7. [Correr rápido en la CPU del cliente](#7-correr-rápido-en-la-cpu-del-cliente)
8. [Del modelo base al modelo de cada cliente](#8-del-modelo-base-al-modelo-de-cada-cliente)
9. [Hoja de ruta del modelo](#9-hoja-de-ruta-del-modelo)
10. [Checklist para poder vender (licencias y calidad)](#10-checklist-para-poder-vender-licencias-y-calidad)
11. [Pasos concretos de la primera semana](#11-pasos-concretos-de-la-primera-semana)
12. [Riesgos](#12-riesgos)
13. [Fuentes](#13-fuentes)

---

## 0. Respuesta corta

### Recomendación

| Pieza | Modelo recomendado | Licencia | Por qué |
|-------|--------------------|----------|---------|
| **Detector de EPP y personas** | **RF-DETR Small** (Nano si la PC del cliente es lenta) | Apache-2.0 (solo Nano, Small, Medium y Large) | Se afina muy bien con pocos datos, ya está integrado en el repo (`ml/entrenador_rfdetr.py`, exportación ONNX y adaptador ONNX con mutación 100 %), se entrena en una GPU de 6 GB y se puede vender sin pagar regalías |
| Plan B del detector | **D-FINE-S** (o DEIM-D-FINE-S) | Apache-2.0 | Muy buena relación precisión/velocidad; salida tipo DETR parecida a la que ya leemos |
| **Motor en el cliente** | **ONNX Runtime** (+ OpenVINO en CPU Intel, a medir) | MIT / Apache-2.0 | Ya integrado; sin PyTorch ni Ultralytics en el `.exe` |
| **Reconocimiento facial (demo)** | Mantener `face_recognition` (dlib, modelo ResNet + 5 puntos) | MIT el código; verificar la licencia de cada modelo | Ya funciona; solo hay que quitar el modelo de 68 puntos (no comercial) |
| **Reconocimiento facial (producto)** | Evaluar **YuNet + SFace** (OpenCV Zoo) contra **AuraFace** | MIT + Apache-2.0 / Apache-2.0 (verificar) | Sin compilar dlib en Windows, ONNX, más rápido en CPU |
| **Etiquetado asistido** (solo en tu PC, no va al cliente) | **Grounding DINO** u **OWLv2** para el primer lote; después, el propio modelo base | Apache-2.0 | Proponen las cajas; una persona solo corrige |

### Lo que **no** se debe usar para vender

| Modelo o dataset | Licencia | Problema |
|------------------|----------|----------|
| Ultralytics YOLOv8 / YOLO11 / YOLO26 (incluido el `yolov8n.pt` actual) | AGPL-3.0 | Obliga a publicar el código de todo el producto, o a pagar la licencia Enterprise. Los modelos entrenados con su código también son AGPL |
| YOLOv7 y YOLOv9 (repositorios originales) | GPL-3.0 | Misma familia de problema que la AGPL |
| YOLO-World | GPL-3.0 | Ídem |
| YOLO-NAS (pesos preentrenados) | Licencia propia de los pesos que restringe el uso comercial | Revisar antes; no vale la pena el riesgo |
| RF-DETR XL, 2XL (y tamaños bajo PML en la ficha de Roboflow) | PML 1.0 | Exige cuenta y condiciones de Roboflow |
| Modelos preentrenados de InsightFace | No comercial (solo investigación) | Hay que comprarles licencia |
| Modelo de 68 puntos de dlib | Dataset iBUG 300-W, uso comercial restringido | Hoy lo llama `src/gui_app.py`; se quita |
| Dataset SH17 | CC BY-NC-SA 4.0 | No comercial |
| Dataset "Construction-PPE" de Ultralytics | AGPL-3.0 | Ídem Ultralytics |

---

## 1. Qué necesita el producto de un modelo

Criterios en orden de importancia, derivados de las decisiones D2-D4 y de la urgencia de vender:

| # | Criterio | Meta | De dónde sale |
|---|----------|------|---------------|
| C1 | **Licencia que permita vender un `.exe` cerrado** | Apache-2.0, MIT, BSD o similar; sin AGPL/GPL/NC | Gate de licencias (AC-001) |
| C2 | Aprende bien con **pocos datos** del cliente | Afinación útil con ~1.000-2.000 imágenes | La prueba dura días, no meses |
| C3 | Corre en **CPU Intel** del cliente | ≥ 5 FPS por cámara, p95 ≤ 200 ms | D2 |
| C4 | Se entrena en **GPU de 6 GB** | Sin quedarse sin memoria | Pregunta T3 de `SPEC/10` |
| C5 | Exporta a **ONNX** | Sin PyTorch en el `.exe` | Fase 1 de `SPEC/9` |
| C6 | Precisión en objetos medianos y chicos (casco a distancia) | Recall por evento ≥ 90 %, ≤ 1 falsa alarma por cámara y hora | D4 |
| C7 | Integración existente y mantenimiento activo | Menos trabajo antes de vender | Urgencia comercial |

---

## 2. Detectores de objetos: comparación

### 2.1 Tabla resumen

| Modelo | Licencia | C2 pocos datos | C3 CPU | C4 6 GB | C5 ONNX | Integración hoy | Veredicto |
|--------|----------|----------------|--------|---------|---------|-----------------|-----------|
| **RF-DETR N/S/M/L** | Apache-2.0 | Excelente | Buena (Nano/Small) | Sí (N/S) | Nativo | **Completa** | **Elegido** |
| D-FINE N/S/M | Apache-2.0 | Muy buena | Muy buena | Sí | Sí | Parcial (salida tipo DETR) | Plan B |
| DEIM (sobre D-FINE) | Apache-2.0 | Muy buena, converge en menos épocas | Muy buena | Sí | Sí | Parcial | Plan B alterno |
| DEIMv2 | Verificar su código; backbones DINOv3 con licencia propia de Meta (comercial con condiciones, §2.5) | Muy buena | Buena | Sí | Sí | Ninguna | No sin revisión legal |
| RT-DETRv2 | Apache-2.0 | Buena | Buena | Sí | Sí | Parcial | Superado por D-FINE |
| YOLOX Nano/Tiny/S | Apache-2.0 | Media | **Excelente** | Sí | Sí, también OpenVINO | Ninguna (salida YOLO + NMS) | Solo si la CPU no da |
| PP-YOLOE+ / PicoDet | Apache-2.0 | Media | Excelente | Sí | Vía `paddle2onnx` | Ninguna | Otro ecosistema; no |
| Ultralytics YOLOv8/11/26 | **AGPL-3.0** | Muy buena | Excelente | Sí | Sí | Adaptador temporal | No (salvo pagar Enterprise) |
| YOLOv7 / YOLOv9 | **GPL-3.0** | Buena | Buena | Sí | Sí | Ninguna | No |
| YOLO-NAS | Pesos restringidos | Buena | Buena | Sí | Sí | Ninguna | No |

### 2.2 Pros y contras en detalle

#### RF-DETR (Roboflow) — **recomendado**

- **Pros**
  - Licencia Apache-2.0 para la librería `rfdetr` y los tamaños Nano, Small, Medium y Large: se
    vende sin regalías ni código abierto obligatorio.
  - Usa un backbone DINOv2 preentrenado, que transfiere muy bien a dominios nuevos con pocos
    datos. Es justo lo que necesita la prueba: afinar en días con las cámaras del cliente.
  - Exportación a ONNX integrada; no necesita NMS (es un DETR), así que el posproceso es simple.
  - **Ya está en el repo:** `ml/entrenador_rfdetr.py`, `ml/export_onnx.py`, `ml/paridad.py`,
    `ml/promotion_gates.py` y el adaptador `src/inference/adapters/onnx_detector.py`. Elegir otro
    modelo cuesta semanas que no tenemos.
  - Proyecto activo, con documentación y comunidad grande.
- **Contras**
  - Un transformer pesa más en CPU que un YOLO del mismo tamaño: hay que medir en la PC del
    cliente (visita previa, `SPEC/10` §7). Nano si no alcanza.
  - Entrenar consume más memoria de GPU que un YOLO: con 6 GB, Nano o Small con lote chico.
  - La licencia **cambia según el tamaño** y los nombres de los tamaños cambiaron entre versiones.
    El repo fija `rfdetr==1.11.2`; usar solo los tamaños que la ficha de esa versión declare
    Apache-2.0 y anotarlo en el manifiesto.
  - Necesita más épocas que un YOLO para converger desde cero; desde un preentrenado es rápido.

#### D-FINE — **plan B**

- **Pros:** Apache-2.0 (código y pesos según la ficha de Roboflow); excelente precisión por
  milisegundo; tamaños desde Nano; salida tipo DETR, así que el adaptador ONNX actual se podría
  reutilizar con cambios menores.
- **Contras:** los checkpoints preentrenados con Objects365 pueden tener términos propios
  (verificar); el código de entrenamiento es de investigación, con menos facilidades que `rfdetr`;
  habría que escribir el entrenador y la paridad.

#### DEIM / DEIMv2

- **Pros:** DEIM (Apache-2.0) mejora el entrenamiento de D-FINE y converge en menos épocas, útil con
  una GPU chica. DEIMv2 (2025) agrega backbones DINOv3 con mejor precisión.
- **Contras:** código de investigación; DEIMv2 depende de DINOv3, que Meta publicó con una licencia
  propia (no Apache): **revisión legal antes de usarlo**.

#### YOLOX

- **Pros:** Apache-2.0; las versiones Nano y Tiny son de los detectores más livianos que existen,
  con exportación a ONNX y OpenVINO probada. Buena opción si la PC del cliente es muy débil.
- **Contras:** sin actividad desde 2023; menos preciso que los DETR modernos en objetos chicos;
  hay que escribir un adaptador nuevo (salida YOLO + NMS) y un entrenador. Ya está considerado en
  ADR-001 como alternativa del benchmark.

#### Ultralytics (YOLOv8, YOLO11, YOLO26)

- **Pros:** lo más fácil de entrenar del mercado; excelente en CPU; es lo que usa hoy la app.
- **Contras:** AGPL-3.0; Ultralytics declara que los modelos entrenados con su código también
  quedan bajo AGPL. Vender un `.exe` cerrado exige la licencia Enterprise, de pago y con costo
  recurrente. Ya se invirtió la Fase 1 completa en salir de aquí: volver no tiene sentido.

### 2.3 Pregunta frecuente: ¿y si usamos Ultralytics solo para entrenar?

**Pregunta (2026-11-10):** "Ultralytics solo se usa para aprender. ¿No podemos entrenar con
Ultralytics y vender el EPP ya aprendido sin la librería?"

**Respuesta: no.** Lo que se vende no es solo la librería: es **el modelo entrenado** (el archivo
de pesos), y ese modelo nace de su código y, normalmente, de sus pesos preentrenados. Ultralytics
lo dice en su propia página de licencias:

- Usar su código, sus modelos, sus arquitecturas, su tubería de entrenamiento **o los modelos
  entrenados o afinados con ella** obliga a publicar todo el proyecto bajo AGPL-3.0 o a comprar
  su licencia Enterprise.
- Según Ultralytics, aplica aunque el modelo se entrene desde cero o se use solo internamente.
- Roboflow, que revende esas licencias, también afirma que los modelos entrenados a medida siguen
  siendo AGPL-3.0.

Exportar a ONNX no cambia nada: el `.onnx` es el mismo modelo en otro formato. Ultralytics no
publica una regla aparte para los pesos exportados; la lectura prudente es que la licencia los
sigue cubriendo. Hay abogados que discuten si unos pesos pueden protegerse por derechos de autor,
pero eso **no se resuelve a nuestro favor sin un juicio**, y un juicio o un reclamo de Ultralytics
en medio de la primera venta es justo lo que no podemos pagar.

| Camino | ¿Se puede vender? | Costo | Comentario |
|--------|-------------------|-------|------------|
| Entrenar con Ultralytics y vender sin la librería | **No** (según Ultralytics) | Riesgo legal | Descartado |
| Entrenar con Ultralytics y comprar la licencia Enterprise | Sí | Cotización a medida, recurrente | Válido si algún día conviene; pedir cotización como dato |
| Entrenar con RF-DETR (Apache-2.0) | **Sí** | Cero en licencias | **Recomendado**: la tubería ya está construida y probada en el repo |

¿Y usar un YOLO solo para **preetiquetar** imágenes (las etiquetas las revisa una persona)? En
general la licencia de un programa no cubre lo que el programa produce, pero no ganamos nada: no
existe un YOLO de EPP con licencia limpia para empezar, y Grounding DINO u OWLv2 (Apache-2.0)
hacen lo mismo sin la duda. Se descarta.

### 2.4 Por qué RF-DETR y no "el más rápido"

La demo se gana o se pierde en **falsas alarmas y casos no detectados** con las cámaras reales del
cliente, no en los FPS de un benchmark. RF-DETR es el que mejor transfiere con pocos datos, y la
velocidad se compensa eligiendo Nano, procesando 1 de cada 2 frames (`cada_n_frames`) o bajando la
resolución. Además, es el único que ya tiene toda la tubería construida y probada en el repo.

### 2.5 ¿Cuál es el modelo libre más avanzado que podemos vender?

**Pregunta (2026-11-10):** sin pagar a Ultralytics, ¿cuál es el modelo de código libre más
avanzado que podemos usar?

**Respuesta: RF-DETR**, de Roboflow. En noviembre de 2026 es el detector en tiempo real más
avanzado con licencia que permite vender: su artículo se aceptó en ICLR 2026, su versión 2XL fue el
primer detector en tiempo real por encima de 60 AP en COCO, y su versión Nano supera a D-FINE Nano
por 5,3 AP con una latencia parecida. **Ojo:** las versiones más grandes (XL y 2XL) están bajo la
licencia PML de Roboflow, no Apache. Para vender sin regalías, el techo es **RF-DETR Large**.

| Modelo | Precisión (COCO, según sus autores) | Licencia para vender | Veredicto |
|--------|-------------------------------------|----------------------|-----------|
| RF-DETR 2XL / XL | La más alta (2XL: 60,1 AP) | PML 1.0 (Roboflow), **no Apache** | No sin contrato con Roboflow |
| **RF-DETR Large** | Muy alta | **Apache-2.0** | El más avanzado 100 % libre; sirve como "maestro" en tu PC si un día se destila |
| **RF-DETR Small / Medium** | Alta | **Apache-2.0** | **El que va en la PC del cliente** (velocidad en CPU) |
| **RF-DETR Nano** | Buena; supera a D-FINE Nano por 5,3 AP | **Apache-2.0** | Si la PC del cliente es lenta |
| DEIMv2 (X: 57,8 AP; S: 50,9 AP con menos de 10 M de parámetros) | Muy alta, muy eficiente | Su código: verificar. Usa backbones **DINOv3**, con licencia propia de Meta: permite uso comercial, pero es una licencia a medida (restringe usos militares, exige indemnizar a Meta y se puede revocar si se incumple) | Candidato serio **solo después de la revisión legal** (D9) |
| D-FINE (L: 54,0 AP; X: 55,8 AP) | Alta | Apache-2.0 | Plan B |
| Ultralytics YOLO11 / YOLO26 | Alta | AGPL-3.0 o Enterprise de pago | No (§2.3) |

**"El más avanzado" no es lo mismo que "el mejor para nosotros".** El cliente tiene una CPU, no una
GPU: un modelo Large o 2XL no daría 5 FPS por cámara. Lo que decide la venta es acertar con casco y
chaleco en sus cámaras, y eso se logra afinando un modelo Small con sus imágenes. La recomendación
de la §0 no cambia: **RF-DETR Small** (Nano si la CPU no alcanza), y RF-DETR Large solo en tu PC
para experimentar o para etiquetar.

La precisión en COCO la publica cada autor con su propio equipo y método; la velocidad real se mide
siempre en la PC del cliente (`tools/bench_detectores.py`).

---

## 3. Reconocimiento facial: comparación

El EPP no necesita reconocer rostros: el aviso puede decir "persona sin casco en zona X" con la
foto. El rostro agrega el nombre (D5: "Juan entró sin casco"), que es más vendible.

| Opción | Licencia | Pros | Contras | Veredicto |
|--------|----------|------|---------|-----------|
| **`face_recognition` + dlib (actual)** | Código MIT y Boost; modelos ResNet y de 5 puntos: verificar en `dlib-models` (se publican como de uso libre); 68 puntos: **no comercial** | Ya integrado, con registro por ráfaga y firma HMAC; precisión buena de frente | Compilar dlib en Windows (hoy hay un `.whl` en la raíz); detector HOG flojo con ángulo, distancia y casco; lento en CPU | **Para la demo**, quitando el de 68 puntos |
| **YuNet (detección) + SFace (reconocimiento)** de OpenCV Zoo | YuNet MIT, SFace Apache-2.0 (según fuentes secundarias; verificar en el repo) | ONNX; corre con OpenCV, que ya es dependencia; rápido en CPU; YuNet detecta caras chicas y de lado mejor que HOG | Precisión menor que los modelos tipo ArcFace grandes; hay que integrarlo y migrar los rostros registrados | **Candidato para el producto** |
| **AuraFace** (fal) | Apache-2.0 según su publicación (verificar) | Tipo ArcFace, pensado para uso comercial; buena precisión | Proyecto chico; hay que integrarlo con un detector (YuNet) | Candidato a comparar con SFace |
| InsightFace (ArcFace `buffalo_l`, etc.) | Código MIT; **pesos no comerciales** | La mejor precisión abierta | Requiere comprar licencia | No, salvo comprarla |
| `facenet-pytorch` | Código MIT; pesos entrenados con VGGFace2/CASIA (licencias de datos restrictivas) | Fácil de usar | Riesgo legal por los datos de entrenamiento | No |

**Recomendación:** demo con lo actual (tarea F-12 de `SPEC/10`: quitar los 68 puntos). Para el
producto, una comparación de un día entre YuNet + SFace y AuraFace con fotos propias (con
consentimiento) de ~20 personas, con y sin casco, y elegir por tasa de identificación correcta y
falsos reconocimientos. Un falso reconocimiento (culpar a la persona equivocada) es peor que no
identificar: el umbral se fija para que casi nunca pase.

---

## 4. Herramientas para etiquetar más rápido

El cuello de botella real no es entrenar: es **etiquetar**. Estas herramientas corren solo en tu
PC (no van al `.exe`), pero sus etiquetas alimentan un modelo que se vende, así que también se
eligen con licencia permisiva.

| Herramienta | Licencia | Uso |
|-------------|----------|-----|
| **Grounding DINO** | Apache-2.0 | Detector por texto: "hard hat", "safety vest", "head". Preetiqueta el primer lote sin modelo propio |
| **OWLv2** | Apache-2.0 | Alternativa a Grounding DINO, disponible en Hugging Face `transformers` |
| **Florence-2** | MIT | Detección por texto y descripciones; útil para revisar casos dudosos |
| **SAM 2** | Apache-2.0 | Ajustar cajas finas (no hace falta para cajas, sí si un día se segmenta) |
| **CVAT** o **Label Studio** autoalojados | MIT / Apache-2.0 | Revisar y corregir las propuestas; exportan COCO, que es el formato del contrato |
| **El modelo base propio** | El nuestro | Desde la segunda iteración, el mejor preetiquetador para los clientes (D6: "el modelo propone y una persona corrige") |

Regla del contrato de datos: una etiqueta propuesta por una máquina **no entra al dataset sin
revisión humana** ([guía de etiquetado](../docs/ml/guia_etiquetado.md),
[runbook](../docs/runbooks/etiquetado.md)).

---

## 5. Datos de entrenamiento con licencia comercial

### 5.1 Fuentes candidatas (verificar cada una en su fuente original antes de usarla)

| Dataset | Licencia declarada | Clases útiles | Encaje con nuestra taxonomía | Notas |
|---------|--------------------|---------------|------------------------------|-------|
| **Hard Hat Workers / "Hard Hat Sample"** (Northeastern University – China, en Roboflow Universe) | CC BY 4.0 en la ficha consultada | `head`, `helmet`, `person` | **Excelente**: `cabeza`, `casco`, `persona` | Hay varias copias subidas por terceros: usar la del autor original y guardar la cita |
| **"vest hat"** (Roboflow Universe) | CC BY 4.0 | `Hardhat`, `Safety Vest`, `NO-Hardhat`, `NO-Safety Vest`, ... | Buena para `casco` y `chaleco` | Las clases `NO-*` no son de nuestra taxonomía: se descartan (el "sin casco" lo deduce el dominio) |
| **Safety Vest Detection** (Kaggle, 3.897 imágenes) | CC BY 4.0 según un espejo | `Safety Vest`, `No Safety Vest` | Buena para `chaleco` | Confirmar la licencia en la ficha original de Kaggle |
| **Fotos propias** | Propias (con consentimiento) | Todas | Total | **La mejor inversión:** 300-500 fotos del equipo con y sin casco/chaleco, en patios, bodegas, de día y de noche, a distancias de cámara real |
| **Imágenes de clientes** | Según la carta de prueba | Todas | Total | Solo con el campo `autorizacion` (`docs/ml/contrato_datos.md`); la cláusula de mejora de `SPEC/10` §8 permite sumarlas al modelo base |

**CC BY 4.0 permite uso comercial con atribución.** Cada dataset usado se cita en
`models/manifest.json` (campo `datasets`) y en el `THIRD_PARTY_NOTICES` que genera la CI.

### 5.2 El problema de las etiquetas incompletas (importante)

Cada dataset público etiqueta **solo sus clases**. Si se mezclan sin cuidado:

- En el dataset de chalecos, las cabezas y los cascos **existen pero no están etiquetados**. El
  modelo aprende que una cabeza sin caja es "fondo" y empieza a no ver cabezas → el sistema no
  puede asociar cascos → **falsas alarmas o infracciones perdidas**.

Solución, en este orden:

1. Preetiquetar las clases faltantes de cada dataset con Grounding DINO u OWLv2 (§4).
2. Revisar a mano una muestra (al menos el 10 %) y todo lo dudoso; lo ambiguo va como región
   "ignorar" (`iscrowd = 1`, ya previsto en el contrato).
3. Validar con `ml/contrato_datos.py` y versionar con `ml/manifiesto_dataset.py`.

### 5.3 Tamaño objetivo del dataset v0.1 (modelo base)

| Fuente | Imágenes | Para qué |
|--------|----------|----------|
| Públicas (§5.1), completadas | 3.000-6.000 | Variedad general |
| Propias | 300-500 | Escenas y cámaras parecidas a las de clientes |
| Primer cliente (en la prueba) | 1.000-2.000 | Afinación y set de prueba del cliente |

El split respeta las reglas sin fuga del contrato: todas las imágenes de una cámara y un día van al
mismo split, y al menos una cámara aparece solo en test (`validar_split`).

---

## 6. Entrenar con una GPU de 6 GB

Tu GPU de 6 GB o menos alcanza para el modelo base y para las afinaciones por cliente.

### 6.1 Preparación de tu PC (una vez)

1. Ver la tarjeta y la memoria: `nvidia-smi`.
2. Crear el entorno aparte del [runbook de entrenamiento](../docs/runbooks/entrenamiento.md), pero
   con la variante CUDA de PyTorch en lugar de `+cpu` (mismas versiones fijadas en
   `ml/requirements-ml.txt`), y correr `pip-audit` y `pip-licenses` como dice el runbook.
3. Datos en carpeta cifrada; pesos fuera de git.

### 6.2 Configuración de partida

| Parámetro | Modelo base (v0.1) | Afinación por cliente |
|-----------|--------------------|-----------------------|
| Tamaño | Small (y una corrida Nano para comparar) | El mismo que pasó en el cliente |
| Resolución | 512 (384 si no cabe en memoria) | La misma del modelo base |
| Lote | 2-4 | 2-4 |
| Acumulación de gradientes | 4-8 (lote efectivo 16) | 4-8 |
| Precisión mixta (AMP) | Sí | Sí |
| Punto de partida | Pesos preentrenados de RF-DETR (Apache-2.0) | **Nuestro modelo base** |
| Épocas | Elegir con `valid` (nunca con `test`) | Menos que el base; elegir con `valid` |

Pendiente técnico: `ml/entrenador_rfdetr.py` no expone la acumulación de gradientes; agregar
`--acumulacion` es la tarea T-09 de `SPEC/10` (corta, con TDD). Si aparece "CUDA out of memory":
bajar el lote a 2, luego la resolución a 384, luego pasar a Nano.

### 6.3 Qué se registra en cada corrida

Ya lo hace la herramienta: `registro.json` con commit, configuración, huella del dataset y sha256
de los pesos. Tú agregas una entrada en la [bitácora del modelo](../docs/ml/bitacora.md) con los
números reales (tiempo de entrenamiento incluido: la primera corrida fija la estimación para las
siguientes).

---

## 7. Correr rápido en la CPU del cliente

En orden de esfuerzo; cada paso se mide con `tools/bench_detectores.py` en la PC real y se acepta
solo si las puertas de precisión siguen en verde:

1. **Elegir el tamaño:** Small si da ≥ 5 FPS por cámara; si no, Nano.
2. **Procesar 1 de cada N frames:** `cada_n_frames` ya existe en `ParametrosEPP`. Con la ventana de
   confirmación de 4 s, analizar 5 frames por segundo sobra.
3. **Resolución:** bajar de 512 a 448 o 384 (múltiplos de 32). Afecta a los cascos lejanos: medir.
4. **OpenVINO** (D2: CPU Intel): probar el proveedor de ejecución de OpenVINO para ONNX Runtime.
   Suele acelerar en CPU Intel; agrega dependencia y tamaño al `.exe`, así que pasa por el gate de
   licencias y `pip-audit`.
5. **Cuantización INT8:** la última opción. Puede bajar la precisión en objetos chicos; solo si las
   puertas de promoción siguen pasando con el modelo cuantizado (se trata como un modelo nuevo,
   con su propia entrada en el manifiesto).

---

## 8. Del modelo base al modelo de cada cliente

```
Datos públicos + propios ──► Modelo base vX (en el repo de modelos, firmado)
                                   │
            Cliente N: captura ────┤  preetiqueta con el modelo base, revisión humana
                                   ▼
                     Afinación (una noche, tu GPU)
                                   ▼
          Puertas de promoción con video del cliente no visto al entrenar
                                   ▼
          Manifiesto firmado (SPEC/10 F-05) ──► instalación remota
                                   │
   Si firmó la cláusula de mejora: sus imágenes (sin rostros identificables) vuelven al dataset
                                   ▼
                       Modelo base vX+1 (mejor para el cliente N+1)
```

Este ciclo es el **activo del negocio**: cada cliente que firma la cláusula de mejora hace el
producto mejor y más barato de instalar para el siguiente. Conviene presentarlo así a los
inversionistas o socios.

Reglas que ya impone el repo y se mantienen:

- **Puertas de promoción fijadas antes de entrenar** (`ml/promotion_gates.py`): recall por evento de
  casco y chaleco ≥ 0,90, ≤ 1 falsa alarma por cámara y hora, recall de persona no peor que el
  modelo actual, ≥ 5 FPS por cámara. Nunca se ajustan mirando resultados.
- **Paridad PyTorch/ONNX** (`ml/paridad.py`) antes de exportar.
- **Ficha del modelo** ([plantilla](../docs/ml/ficha_modelo_plantilla.md)) por cada versión vendida.
- **Modo sombra** en cada instalación nueva.

---

## 9. Hoja de ruta del modelo

| Versión | Contenido | Cuándo | Condición para avanzar |
|---------|-----------|--------|------------------------|
| **v0.1 base** | `persona`, `cabeza`, `casco`, `chaleco` (taxonomía v1) | Semanas 1-2 | Pasa las puertas en video propio |
| **v0.1-cliente1** | Afinado con el primer cliente | Durante su prueba | Pasa las puertas en video del cliente |
| **v1.0** | Base + datos de clientes con cláusula de mejora; ficha del modelo; set dorado por cliente | Tras 2-3 clientes | Sin regresión en ningún set dorado |
| **v2.0** | Taxonomía v2: `manos`, `guantes`, `gafas`, `barbijo` (cubrebocas) | Cuando un cliente lo pague | Probablemente Medium o mayor resolución: son objetos chicos. Medir en CPU antes de prometer |
| (pospuesta) `celular` | Agregar la clase al final de la taxonomía (no rompe IDs) | Solo si algún día se vende el módulo de eficiencia (M-1) | Ver la tabla de abajo |

**Decisión M-1 (2026-11-10): se vende solo casco y chaleco.** La taxonomía v1 queda como está
(`persona`, `cabeza`, `casco`, `chaleco`) y **no se etiquetan celulares**. Efecto: al retirar
Ultralytics (A-16), la detección de uso del celular del módulo de eficiencia heredado deja de
funcionar. No rompe nada (simplemente no detecta celulares), pero el reporte de eficiencia
mostraría siempre cero uso del celular. Por eso, en la demo no se muestra ese reporte, y la tarea
T-18 de `SPEC/10` oculta las vistas de eficiencia cuando la licencia no incluye ese módulo.

Si un cliente pide eficiencia más adelante, estas son las opciones para recuperar el celular sin
Ultralytics, de menos a más trabajo:

| Opción | Trabajo | Costo en la PC del cliente | Comentario |
|--------|---------|----------------------------|------------|
| **RF-DETR preentrenado en COCO** como segundo modelo | Exportar a ONNX y registrar en el manifiesto; **sin entrenar** | Doble inferencia por frame (medir FPS) | Los tamaños Nano/Small/Medium/Large preentrenados son Apache-2.0 y COCO ya incluye "celular" y "persona". Licencia de las imágenes de COCO: anotarla para D9 |
| Clase `celular` en el modelo EPP (taxonomía v2, al final) | Etiquetar celulares en el dataset | Un solo modelo | La más eficiente a largo plazo; más etiquetado |

La primera opción sale en días porque no hay que entrenar.

### 9.1 Si mañana se agrega eficiencia: qué modelo y cómo

**Pregunta (2026-11-10):** si mañana se vende eficiencia, ¿qué modelo se usa sin Ultralytics y
cómo se integra?

**Qué necesita un modelo.** De todo lo que mide eficiencia (tiempo en la zona de trabajo, salidas,
almuerzo, uso del celular), solo el **celular** necesita un detector nuevo. El resto sale de
`persona` + zonas + seguimiento, que ya da el modelo EPP.

**Modelo: RF-DETR**, la misma familia que el EPP, por tres motivos: licencia Apache-2.0 en
Nano/Small/Medium/Large, el adaptador ONNX ya existe, y un solo motor es más fácil de mantener.
Plan B: D-FINE preentrenado en COCO (Apache-2.0), con el mismo adaptador tipo DETR.

**Cómo, en dos etapas:**

| Etapa | Qué es | Trabajo | Costo en la PC del cliente | Cuándo |
|-------|--------|---------|----------------------------|--------|
| **1. Rápida** | **RF-DETR Small preentrenado en COCO** como segundo detector. COCO ya trae `persona` y `celular`: **no se entrena nada** | ~1 semana de código (abajo) | Una segunda inferencia; se compensa corriéndola cada 3-5 frames | El primer cliente que pague eficiencia |
| **2. Definitiva** | Agregar `celular` **al final** de la taxonomía del modelo EPP (los IDs anteriores no cambian) y reentrenar con celulares etiquetados | Etiquetado + una afinación | Ninguno: un solo modelo | Cuando 2 o más clientes paguen eficiencia |

**Pasos de la etapa 1** (cada uno con TDD y su PR, como manda `CLAUDE.md`):

1. **Exportar el preentrenado a ONNX.** `ml/export_onnx.py` hoy exige el `registro.json` de un
   entrenamiento propio. Agregar un modo para un preentrenado oficial: tamaño, resolución,
   versión de `rfdetr` y sha256 de los pesos descargados.
2. **Entrada en `models/manifest.json`:** licencia de los pesos Apache-2.0, dataset COCO 2017
   (anotaciones CC BY 4.0; las imágenes vienen de Flickr con licencias variadas: anotarlo para
   D9) y `clases` solo con los IDs de `persona` y `celular`, tomados del catálogo de esa versión
   de RF-DETR. **Verificar los IDs:** RF-DETR puede numerar con los IDs originales de COCO y no
   con los 80 consecutivos de YOLO. El adaptador ignora cualquier ID que no esté en el catálogo,
   así que las otras 78 clases de COCO no hacen falta.
3. **Raíz de composición con dos detectores**, solo si la licencia incluye el módulo
   `eficiencia`: el detector EPP entrega personas, cabezas y EPP; el de COCO entrega solo
   celulares, cada N frames. `separar_personas_y_celulares` (`src/tracking/person_tracker.py`)
   ya recibe una lista de detecciones neutrales: se le pasan las dos listas unidas. El dominio
   no cambia.
4. **Licencia:** `--modulos epp,eficiencia` en el keygen (T-03) y la tarea T-18 al revés: las
   vistas de eficiencia aparecen solo con ese módulo.
5. **Medir antes de vender:** `tools/bench_detectores.py` con los dos modelos (puerta ≥ 5 FPS por
   cámara) y recall de celular con un video del cliente.

**Riesgos propios del celular, y cómo se manejan:**

| Riesgo | Mitigación |
|--------|------------|
| A distancia de cámara, el celular mide pocos píxeles y COCO lo detecta mal | Resolución mayor o tamaño Medium solo para ese detector; o un segundo paso que recorte la mitad superior de cada persona dentro de su zona de trabajo y la analice a mayor resolución |
| En planta, radios, escáneres y tabletas parecen celulares | En la etapa 2, etiquetarlos como negativos (o como clase propia); exigir que el celular se vea varios segundos, igual que la ventana de 4 s del EPP |
| Uso legítimo del celular (supervisores, llamadas de trabajo) | Regla de negocio por zona o por puesto, no del modelo |
| Datos de entrenamiento de celulares con licencia comercial (etapa 2) | Fotos propias y de clientes con autorización; verificar la licencia de cualquier dataset público antes de usarlo |

---

## 10. Checklist para poder vender (licencias y calidad)

- [ ] El modelo vendido es RF-DETR Nano/Small/Medium/Large (Apache-2.0) o D-FINE, con la licencia
      de los pesos anotada en `models/manifest.json`.
- [ ] Cada dataset usado está en el manifiesto con su licencia y su cita; ninguno es NC, ND o AGPL.
- [ ] `ultralytics`, `torch` y los `.pt` fuera del runtime (A-16); gate de licencias en verde
      (`pre-commit run licencias --hook-stage manual`).
- [ ] Modelo de 68 puntos de dlib fuera del código (F-12 de `SPEC/10`).
- [ ] `THIRD_PARTY_NOTICES` generado e incluido en el instalador, con las atribuciones CC BY 4.0.
- [ ] Licencia comercial de PyArmor confirmada (`docs/legal/revision_d9.md`).
- [ ] Revisión legal D9 hecha y anotada.
- [ ] Ficha del modelo completa; entrada en la bitácora con las métricas reales.
- [ ] Puertas de promoción en verde sobre el set dorado del cliente.
- [ ] Quality Gate de `CLAUDE.md` §10 completo en verde para el código que se toque.
- [ ] (Recomendado) Ejecutable firmado con un certificado de firma de código, para que Windows y el
      antivirus del cliente no lo bloqueen.

---

## 11. Pasos concretos de la primera semana

| Día | Paso | Herramienta | Resultado |
|-----|------|-------------|-----------|
| 1 | Verificar la licencia de cada dataset de §5.1 en su fuente original; descargar en formato COCO | Navegador, Roboflow Universe, Kaggle | Carpeta cifrada + tabla de licencias con enlaces y fecha |
| 1 | Preparar el entorno de entrenamiento con CUDA en tu PC | Runbook de entrenamiento | `pip-audit` y `pip-licenses` limpios |
| 2 | Convertir y unificar clases a la taxonomía v1 | `ml/convertir_etiquetas.py` | Dataset en el formato del contrato |
| 2-3 | Completar las clases faltantes con Grounding DINO/OWLv2 y revisar | CVAT o Label Studio | Etiquetas completas; ambiguos como "ignorar" |
| 3 | Tomar 300-500 fotos propias y etiquetarlas | Cámara IP o celular a altura de cámara | Escenas parecidas a las de clientes |
| 4 | Validar contrato y split; versionar el dataset v0.1 | `ml/contrato_datos.py`, `ml/manifiesto_dataset.py` | Manifiesto con huella |
| 4 | Agregar `--acumulacion` al entrenador (T-09) | TDD | PR chico |
| 5 | Entrenar Small y Nano (de noche) | `ml/entrenador_rfdetr.py` | Dos artefactos con `registro.json` |
| 6 | Análisis de errores en `valid`; bitácora | Runbook §4 | Decisión: cuál sigue |
| 7 | Exportar a ONNX, paridad, entrada de manifiesto; puertas con un video propio | `ml/export_onnx.py`, `ml/paridad.py`, `ml/promotion_gates.py` | **Modelo base v0.1** listo para la visita previa del cliente |

---

## 12. Riesgos

| # | Riesgo | Mitigación |
|---|--------|------------|
| M-R1 | Una licencia de dataset resulta no comercial después de entrenar | Verificar antes de descargar; manifiesto con la licencia de cada fuente; si una cae, reentrenar sin ella (la herramienta registra qué datos usó cada modelo) |
| M-R2 | Las imágenes públicas (fotos de internet) no se parecen a las cámaras reales | Fotos propias a altura de cámara y afinación por cliente; el set de prueba siempre es de cámaras reales |
| M-R3 | RF-DETR no da 5 FPS en la PC del cliente | Nano, `cada_n_frames`, resolución, OpenVINO (§7); plan B YOLOX Nano |
| M-R4 | Casco confundido con gorra o cabeza calva; chaleco con playera amarilla | Agregar esos casos como negativos en las fotos propias; la ventana de 4 s filtra parpadeos |
| M-R5 | Cambio de licencia en una versión nueva de `rfdetr` | Versiones fijadas; revisar la ficha de licencias en cada actualización |
| M-R6 | Etiquetas de la máquina con errores sistemáticos | Revisión humana obligatoria; acuerdo entre etiquetadores (`tools/acuerdo_etiquetado.py`) |
| M-R7 | Reconocimiento facial culpa a la persona equivocada | Umbral conservador; si hay duda, el aviso no nombra a nadie |

---

## 13. Fuentes

Consultadas el 2026-11-10. Las marcadas "secundaria" no son la ficha oficial: confirmar en el
repositorio original antes del release.

- RF-DETR, licencias por tamaño: [Roboflow — RF-DETR Model Licensing](https://roboflow.com/model-licenses/rf-detr);
  [documentación de RF-DETR](https://rfdetr.roboflow.com/latest/learn/run/detection/);
  [modelos preentrenados](https://www.mintlify.com/roboflow/rf-detr/run/pretrained-models) (secundaria).
- D-FINE y DEIM: [Roboflow — D-FINE](https://roboflow.com/model/d-fine);
  [D-FINE vs DEIM](https://playground.roboflow.com/models/compare/d-fine-vs-deim);
  [DEIM vs RF-DETR](https://playground.roboflow.com/models/compare/deim-vs-rf-detr) (secundarias);
  [pydfine en PyPI](https://pypi.org/project/pydfine/).
- OpenCV Zoo (YuNet, SFace): [README de opencv_zoo](https://huggingface.co/opencv/opencv_zoo/blob/30e431e4c2f784faadc76d62470bc039768a5425/README.md);
  [SFace en Hugging Face](https://huggingface.co/opencv/face_recognition_sface/blob/main/demo.py) (secundarias para la licencia por modelo).
- Datasets: [vest hat (Roboflow Universe)](https://universe.roboflow.com/v110/vest-hat);
  [Hard Hat Sample (Roboflow Universe)](https://universe.roboflow.com/khdaksdhkasd/hard-hat-sample-10vfl);
  [Safety Vest Detection (espejo)](https://vercel.hyper.ai/en/datasets/41965).
- Ultralytics y modelos entrenados: [licencia de Ultralytics](https://ultralytics.com/license);
  [Roboflow como licenciatario de Ultralytics](https://roboflow.com/ultralytics).
- Estado del arte: [artículo de RF-DETR (ICLR 2026)](https://arxiv.org/html/2511.09554v2);
  [DEIMv2, "Real-Time Object Detection Meets DINOv3"](https://arxiv.org/html/2509.20787v3);
  [D-FINE vs RF-DETR](https://playground.roboflow.com/models/compare/d-fine-vs-rf-detr) (secundaria).
- DINOv3: [licencia de DINOv3](https://ai.meta.com/resources/models-and-libraries/dinov3-license);
  [anuncio de Meta](https://ai.meta.com/blog/dinov3-self-supervised-vision-model/).
- Ultralytics AGPL, SH17, YOLOX y licencias verificadas antes: `SPEC/9_PLAN_EPP_Y_LICENCIA.md` §3.1
  y §20, `docs/adr/001-motor-ia.md`, `docs/legal/revision_d9.md`.
