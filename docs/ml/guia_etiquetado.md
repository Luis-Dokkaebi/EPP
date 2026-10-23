# Guía de etiquetado del dataset EPP

**Estado:** borrador para aprobación (DoD de la Fase 2, SPEC/9 §2.5). Las reglas marcadas como
"propuesta" son del borrador y se confirman al aprobar la guía; lo que depende de una decisión
abierta figura como **PENDIENTE (Dn)**. El formato y la taxonomía están en el
[contrato de datos](contrato_datos.md).

## 1. Herramienta y privacidad

- **CVAT** (MIT) o **Label Studio** (Apache-2.0), autoalojados en un equipo con disco cifrado. Las
  imágenes con rostros no se suben a servicios de terceros.
- Exportar en **COCO 1.0**. Los nombres de las etiquetas en la herramienta son exactamente los de la
  taxonomía (`persona`, `cabeza`, `casco`, `chaleco`), en minúsculas y sin tildes.
- No se etiquetan nombres, rostros ni ningún dato que identifique a una persona.

## 2. Reglas generales

1. **Caja ajustada a lo visible:** de borde a borde de la parte que se ve, sin margen. No se estima
   la parte oculta.
2. **Un objeto, una caja.** Dos operarios juntos son dos `persona`, aunque las cajas se solapen.
3. **Región "ignorar"** (en COCO, `iscrowd = 1`): se dibuja la caja de la clase y se marca el
   atributo "ignorar" cuando:
   - el lado menor de la caja está por debajo del tamaño mínimo (valor: **PENDIENTE (D6)**, depende
     de la resolución de las cámaras del piloto);
   - el objeto es ambiguo y dos etiquetadores razonables no se pondrían de acuerdo (reflejos,
     desenfoque fuerte, objeto cortado por el borde en más de la mitad).
4. **Ante la duda, ignorar** antes que adivinar: una etiqueta equivocada enseña un error; una región
   ignorada no enseña nada.

## 3. Definiciones operativas por clase

| Clase | Se etiqueta | No se etiqueta (o va como "ignorar") |
|-------|-------------|--------------------------------------|
| `persona` | Toda persona visible, de pie, agachada o de espaldas | Reflejos en vidrios, personas en pantallas o carteles |
| `cabeza` | La cabeza completa visible, **con el casco incluido** si lo lleva puesto | Propuesta: si se ve menos de la mitad de la cabeza, "ignorar" |
| `casco` | Todo casco de seguridad visible, puesto o no | Gorras, gorros y capuchas no son casco |
| `chaleco` | Chaleco o ropa reflectiva visible, puesta o no | Ropa de color llamativo sin bandas reflectivas |

**Casco puesto, casco en la mano:** el casco se etiqueta siempre como `casco`, esté sobre la cabeza,
en la mano o colgado. Que esté **puesto** no lo decide la etiqueta sino la asociación con la caja de
la `cabeza` (SPEC/9 §4.1): un casco en la mano queda fuera de la región de la cabeza y no cuenta.
Por eso la caja de la `cabeza` incluye el casco puesto: así las dos cajas se solapan.

**Chaleco o mameluco reflectivo:** hasta que se decida si son una clase o dos (**PENDIENTE (D3)**),
ambos se etiquetan como `chaleco`. Se marca el atributo "mameluco" en la herramienta para poder
separarlos después sin volver a etiquetar.

## 4. Iteración 2 (todavía no se etiqueta)

Se agregan `manos`, `guantes`, `gafas` y `barbijo` (decisión D3). Reglas ya conocidas:

- gafas en la frente = no puestas (SPEC/9 §2.5);
- barbijo bajo la nariz o en el cuello: **PENDIENTE (D3)** (cumplimiento parcial).

## 5. Casos difíciles que hay que cubrir

Casco en la mano, casco colgado del cinturón, chaleco abierto o colgado, operarios de espaldas,
aglomeraciones, contraluz, lluvia, noche (si hay turno nocturno) y EPP de colores poco comunes.
Cada caso difícil que aparezca se agrega a esta tabla con un ejemplo (nombre de archivo, nunca la
imagen):

| Caso | Archivo de ejemplo | Decisión |
|------|--------------------|----------|
| — | — | — |

## 6. Doble etiquetado y acuerdo

- El **10 %** de las imágenes, elegido al azar y repartido entre todas las cámaras, lo etiquetan dos
  personas por separado, sin ver el trabajo de la otra.
- El acuerdo se mide por clase con la herramienta de acuerdo entre etiquetadores (entrega B-03).
- El umbral de acuerdo mínimo se fija antes de medir, al aprobar esta guía: **PENDIENTE**. Mientras
  no exista, la medición se informa pero no aprueba nada.
- Una clase por debajo del umbral se **redefine** en esta guía y se vuelve a etiquetar antes de
  entrenar (SPEC/9 §2.5).

## Aprobación

| Rol | Nombre | Fecha |
|-----|--------|-------|
| Responsable de producto | PENDIENTE | |
| Responsable de seguridad e higiene | PENDIENTE | |
