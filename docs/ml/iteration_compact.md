# Iteration Compact del modelo EPP — iteración 1

**Estado:** borrador para aprobación del responsable de producto (DoD de la Fase 2, SPEC/9 §8).
**Fuente:** SPEC/9 §2.1, skill `mle-workflow` (Iteration Compact). Lo que depende de una decisión
abierta figura como **PENDIENTE (Dn)** y no se completa con valores supuestos.

| Campo | Contenido |
|-------|-----------|
| Goal | Detectar, por persona y en tiempo real, la ausencia de cada elemento de EPP exigido. |
| Who cares | Responsable de seguridad e higiene; operarios; dirección (cumplimiento legal). |
| Decision owner | Responsable de seguridad e higiene del sitio. |
| Acción que cambia el modelo | Se genera una alerta y se registra una infracción (Fases 4 a 7). |
| Success metric | Recall de infracciones reales a nivel evento, medido en los videos dorados (SPEC/9 §3.3). |
| Guardrail metrics | Falsas alarmas por cámara y por hora; FPS por cámara; latencia de la alerta. |
| Mistake budget | **PENDIENTE (D4).** Sin presupuesto no hay umbrales: las puertas de `ml/promotion_gates.py` fallan cerradas. |
| Unacceptable mistakes | No alertar a alguien sin casco en una zona de riesgo durante más de T segundos (T: **PENDIENTE (D4)**). |
| Acceptable mistakes | Estado "no verificable" cuando la cabeza no se ve o el torso no es visible (ADR-002, anclas). |
| Assumptions | Cámaras fijas; operarios a una distancia parecida a la del video de referencia; luz diurna (S2, S3). |
| Constraints | CPU i3/i5 sin GPU (D2 desconocido: se mide en el hardware del piloto); ejecutable cerrado; solo licencias permisivas. |
| Labels and data snapshot | Dataset propio del piloto, versión `v0.1`, todavía sin crear: **PENDIENTE (D6)** (origen, presupuesto y quién etiqueta). Contrato en [contrato_datos.md](contrato_datos.md). |
| Baseline | RF-DETR Small (Apache-2.0), ajuste fino con la taxonomía v1. |
| Candidate signals | Cajas de EPP + anclas corporales (cabeza; torso como región de la persona) + `track_id` + zona. |
| Threshold or config plan | Umbral por clase elegido en validación, nunca en test. Los valores mínimos de promoción: **PENDIENTE (D4)**; el FPS mínimo: **PENDIENTE (D2)**. |
| Eval slices | Distancia (persona chica o grande), iluminación, oclusión, cámara, color del EPP. |
| Known risks | Oclusión, casco en la mano, EPP de colores raros, aglomeraciones, fatiga de alertas (R1, R2). |
| Next experiment | Medir el recall de casco por slice de distancia sobre el split de validación. |
| Rollback or fallback | Modelo anterior del manifiesto (`models/manifest.json`); módulo EPP desactivable. |

## Alcance de la iteración 1 (decisión D3)

- **Elementos:** casco y chaleco (o ropa reflectiva). Guantes, gafas y barbijo pasan a la
  iteración 2 junto con el ancla `manos`.
- **Clases del detector (taxonomía v1):** `persona`, `cabeza`, `casco`, `chaleco`. La taxonomía v2
  agrega `manos`, `guantes`, `gafas` y `barbijo` sin renumerar las clases de la v1. La lista exacta
  vive en `ml/contrato_datos.py` y la validan sus pruebas.
- Si el chaleco y el mameluco reflectivo son una clase o dos: **PENDIENTE (D3)**. Hasta que se
  decida, ambos se etiquetan como `chaleco` (SPEC/9 §2.2).

## Decisiones abiertas que bloquean el cierre

| Decisión | Qué bloquea | Qué hacen las herramientas mientras tanto |
|----------|-------------|--------------------------------------------|
| D2 | FPS mínimo de la puerta de promoción | La puerta de FPS falla cerrada |
| D4 | Umbrales de promoción y tiempo de confirmación T | Las puertas con umbral `None` fallan cerradas y nombran D4 |
| D5 | Retención, difuminado de rostros y base legal de las imágenes | La captura exige un plazo de retención explícito y no tiene valor por omisión |
| D6 | Captura real, cámaras, días, etiquetadores | Las herramientas existen y se prueban con videos sintéticos; no hay datos reales |

## Aprobación

| Rol | Nombre | Fecha | Firma o enlace |
|-----|--------|-------|----------------|
| Responsable de producto | PENDIENTE | | |
| Responsable de seguridad e higiene | PENDIENTE | | |
