# Bitácora del modelo EPP (Observation Ledger)

Una entrada por iteración: entrenamiento, cambio de umbral, de datos o de etiquetas (SPEC/9 §3.5,
skill `mle-workflow`). Se escribe con números de corridas reales; nada se redondea ni se estima.
El procedimiento está en el [runbook de entrenamiento](../runbooks/entrenamiento.md).

**Estado:** sin entradas. Todavía no se corrió ningún entrenamiento (faltan el dataset v0.1, D6,
y los umbrales de promoción, D4 y D2).

## Plantilla (copiar por cada iteración)

```text
Iteración:            <n> — <fecha> — <quién>
Artefacto:            epp-<sha>-<huella> (registro.json)
Dataset:              <versión> — huella <sha256 del manifiesto>
Cambio:               <una hipótesis por iteración>
Por qué importaba:
Movimiento de métricas (valid): <por caja y por evento, con el valor anterior>
Movimiento por slice: <distancia, luz, cámara, oclusión, color del EPP>
Falsos positivos:     <grupos y ejemplos (nombres de archivo, nunca imágenes)>
Falsos negativos:
No verificables:
Errores inesperados:
Decisión:             <seguir, revertir, promover>
Costo aceptado:
Lección registrada:   <dónde quedó: guía, contrato, prueba>
Regresión agregada:   <caso del set dorado>
Deuda creada:
Próxima iteración:    <experimento falsable>
Puertas de promoción: <salida de exigir_promocion, solo si se evaluó test>
```

## Entradas

Ninguna.
