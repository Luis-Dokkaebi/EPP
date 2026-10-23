# Ficha del modelo (plantilla)

Copia este archivo como `models/cards/epp-vX.Y.md` por cada modelo que se declare en
`models/manifest.json` (SPEC/9 §3.7). Todo número sale de corridas reales registradas en la
[bitácora](bitacora.md); lo que todavía no se midió se escribe **PENDIENTE** con su motivo.

## Identidad

| Campo | Valor |
|-------|-------|
| Nombre y versión | `epp` vX.Y.Z |
| Archivo y sha256 | `models/epp/epp-X.Y.Z.onnx` — `<sha256>` (igual al del manifiesto) |
| Artefacto de entrenamiento | `epp-<sha>-<huella>` (`registro.json`) |
| Código | commit `<sha del código>` |
| Motor de entrenamiento | RF-DETR `<tamaño>` (Apache-2.0), resolución `<N>` |
| Exportación | ONNX opset 17; paridad aprobada con rtol 1e-3 y atol 1e-5 (`ml/paridad.py`) |
| Licencias | pesos Apache-2.0; código de entrenamiento Apache-2.0; datos: ver abajo |

## Clases (catálogo del manifiesto)

| ID | Clase | Uso |
|----|-------|-----|
| 1 | persona | Seguimiento y dueño del EPP |
| 2 | cabeza | Ancla del casco |
| 3 | casco | EPP |
| 4 | chaleco | EPP |

## Datos de entrenamiento

- Dataset `vX.Y`, huella `<sha256 del manifiesto>`, manifiesto `ml/datasets/vX.Y/manifest.json`.
- Fuentes y licencias: `<nombre — licencia>` (solo licencias comerciales; SH17 nunca).
- Split por cámara y día; cámara(s) solo de test: `<...>`.
- Imágenes por split: train `<n>`, valid `<n>`, test `<n>`.

## Métricas (test, medidas una sola vez)

| Métrica | Valor | Umbral de promoción (D2/D4) |
|---------|-------|-----------------------------|
| Recall de infracciones de casco (evento) | | |
| Recall de infracciones de chaleco (evento) | | |
| Falsas alarmas por cámara y por hora | | |
| FPS por cámara en el hardware del piloto | | |
| Recall de persona menos el del modelo de producción | | |

### Por slice

| Slice | Recall casco | Recall chaleco | Falsas alarmas/h |
|-------|--------------|----------------|------------------|
| Persona chica (lejos) | | | |
| Persona grande (cerca) | | | |
| Poca luz | | | |
| Oclusión | | | |
| Cámara `<id>` | | | |

## Uso previsto y no previsto

- **Previsto:** verificar casco y chaleco de operarios en cámaras fijas del sitio, como señal para
  el responsable de seguridad e higiene, con confirmación temporal (Fase 4).
- **No previsto:** identificar personas, evaluar desempeño laboral, decidir sanciones sin revisión
  humana, cámaras móviles o ángulos muy distintos de los del dataset.

## Limitaciones conocidas

- `<casos difíciles del análisis de errores: casco en la mano, contraluz, aglomeraciones...>`
- Guantes, gafas y barbijo no están en esta versión (iteración 2 de D3).

## Aprobaciones

| Rol | Nombre | Fecha |
|-----|--------|-------|
| Responsable del modelo | | |
| Responsable de producto | | |
