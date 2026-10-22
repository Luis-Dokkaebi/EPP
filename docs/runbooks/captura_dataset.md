# Runbook: captura de imágenes para el dataset EPP

**Quién:** la persona responsable del dataset, en el sitio piloto o con sus videos grabados.
**Herramienta:** `tools/capturar_dataset.py` (B-02). **Contrato:** [contrato de datos](../ml/contrato_datos.md).
**Estado:** bloqueado hasta resolver D5 y D6 (SPEC/9 §4). Ningún agente ejecuta este runbook: las
imágenes reales tienen rostros y solo las maneja un humano autorizado.

## 1. Antes de empezar (todo obligatorio)

| # | Requisito | Decisión |
|---|-----------|----------|
| 1 | Autorización **escrita** del cliente para capturar en sus cámaras, con un identificador (por ejemplo `AUT-2026-001`) | D5 |
| 2 | Plazo de retención de las imágenes, en días; la herramienta no tiene valor por omisión | **PENDIENTE (D5)** |
| 3 | Qué cámaras y qué días se capturan, y cuál cámara queda reservada solo para test | **PENDIENTE (D6)** |
| 4 | Carpeta de destino en un disco **cifrado** con acceso restringido, **fuera** del repositorio (la herramienta se niega a escribir dentro) | D5 |
| 5 | Tabla de turnos del sitio, que cubra las 24 horas una sola vez | Dato del cliente |
| 6 | Identificador corto de cada cámara (`a-z`, `0-9`, `-`): nunca el nombre de una persona ni la IP | — |

## 2. Captura

Video grabado (la hora de cada imagen sale de `--inicio` y de los FPS del archivo):

```bash
python -m tools.capturar_dataset --fuente /ruta/cifrada/videos/cam-01_2026-10-21.mp4 \
    --inicio 2026-10-21T06:00:00 --camara cam-01 --salida /ruta/cifrada/dataset/crudo \
    --autorizacion AUT-2026-001 --retencion-dias <D5> \
    --turnos "manana=6-14,tarde=14-22,noche=22-6" --intervalo-segundos 5
```

Cámara en vivo (la hora sale del reloj del equipo: verifica que esté sincronizado):

```bash
python -m tools.capturar_dataset --fuente "$URL_CAM_02" --en-vivo \
    --camara cam-02 --salida /ruta/cifrada/dataset/crudo --autorizacion AUT-2026-001 \
    --retencion-dias <D5> --turnos "dia=6-18,noche=18-6" --intervalo-segundos 10 --maximo 500
```

- `URL_CAM_02` es una variable de entorno con la URL RTSP de la cámara, credenciales incluidas,
  cargada desde el almacén seguro del sitio: la clave no queda en documentos ni en el historial.
- `--intervalo-segundos`: un frame cada N segundos. Más chico no agrega diversidad: los frames
  seguidos son casi iguales.
- `--distancia-maxima` (por omisión 5 de 64 bits): dos imágenes a esa distancia de dHash o menos se
  consideran la misma escena y la segunda se descarta. Es una propuesta del borrador: si se
  descartan escenas distintas, bájala; si pasan casi duplicados, súbela. Anota el valor usado.
- La captura en vivo termina con `--maximo`, si la cámara se corta, o con Ctrl+C. Todo lo guardado
  hasta ese momento queda completo: cada imagen se escribe antes que su línea de metadatos.
- Las URL RTSP se muestran sin usuario ni clave en los mensajes de error.

## 3. Verificación (después de cada corrida)

1. El resumen dice cuántas imágenes se guardaron y cuántas se descartaron por casi duplicadas.
2. `metadatos.jsonl` tiene una línea por imagen `.jpg` de la carpeta.
3. Mira una muestra de 20 imágenes: luz, distancia y casos difíciles de la
   [guía de etiquetado](../ml/guia_etiquetado.md) (casco en la mano, aglomeraciones, contraluz).
4. Si faltan turnos, climas o distancias, programa otra captura antes de etiquetar (SPEC/9 §2.4).

## 4. Qué no hacer

- No subir imágenes a git, a la nube pública ni a servicios de etiquetado de terceros.
- No renombrar ni editar las imágenes: el sha256 de los metadatos dejaría de coincidir.
- No mezclar en una carpeta capturas de clientes distintos.

## 5. Errores frecuentes

| Mensaje | Qué hacer |
|---------|-----------|
| `... ya existe: la captura nunca sobrescribe imágenes` | Usa otra carpeta o revisa si ya se capturó ese tramo |
| `La fuente no informa sus FPS` | Convierte el video a FPS fijos (por ejemplo, con ffmpeg) y repite |
| `El reloj retrocedió` | Sincroniza la hora del equipo (NTP) y repite la captura en vivo |
| `... está dentro del repositorio` | Elige una carpeta en el disco cifrado |
| `Horas sin turno` / `Horas en más de un turno` | Corrige la tabla de turnos: cada hora, una sola vez |

## 6. Retención

Cada línea de metadatos trae `eliminar_despues_de`. Hasta que exista la purga automática
(depende de D5), una persona revisa esa fecha una vez por semana y borra las imágenes vencidas
junto con sus líneas de metadatos, y lo anota en la bitácora del dataset.
