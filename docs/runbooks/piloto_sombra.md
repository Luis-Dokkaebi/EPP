# Runbook: build 2.0.0 y piloto en modo sombra del módulo EPP (C-14)

> **Estado: NO EJECUTADO.** Este documento lista los pasos humanos de la Fase 9 de
> `SPEC/9_PLAN_EPP_Y_LICENCIA.md` (§15). Ningún paso fue ejecutado por un agente. C-14 está
> bloqueada por **D8** (autorización para tocar el build y los binarios) y **D9** (revisión legal
> de licencias). Tampoco hay valores para **D4** (umbrales) ni **D5** (retención y nombre en los
> avisos). Hasta que esas decisiones existan, este runbook no se puede completar.

## 0. Requisitos previos (decisiones humanas)

| Decisión | Qué hace falta para el piloto | Dónde se usa |
|----------|-------------------------------|--------------|
| D4 | Umbrales de la ventana temporal (fracción ausente, tiempo de confirmación, presentes para recuperar, limpieza), enfriamiento y umbrales de asociación | Configuración del caso de uso EPP (sin valores por omisión) |
| D5 | Días de retención de las evidencias y si los avisos nombran al empleado | `retencion_de_evidencias(dias)` y `EPP_ALERTAS_NOMBRE_EMPLEADO` (`incluir` / `omitir`) |
| D8 | Autorización explícita para modificar `gui_app.spec`, `compilar_exe.bat`, `obfuscate.py`, `setup_oficina.iss` y borrar `yolov8n.pt` | Build (§1) |
| D9 | Revisión legal de licencias (`docs/legal/`, THIRD_PARTY_NOTICES) | Release (§1) |
| B-06 | Clips reales del sitio y modelo `.onnx` entrenado con su manifiesto | Replay dorado y build |

## 1. Build 2.0.0 (requiere D8 y D9)

1. Partir de la rama integrada con las pistas A, B y C en verde (gate completo, §10 de `CLAUDE.md`).
2. `gui_app.spec`: quitar `ultralytics` y `torch`; incluir `onnxruntime`, el modelo `.onnx` y su
   manifiesto (fichas del modelo, §9.2).
3. Revisar `obfuscate.py` y `compilar_exe.bat` para los módulos nuevos (`src/ppe`, `src/alerts`,
   `src/gui/panel_*`, `src/gui/presentador_*`).
4. `VERSION`: 1.3.0 → **2.0.0** (cambio mayor: nuevo motor, formato de zonas v2, módulo EPP).
5. Instalador: incluir THIRD_PARTY_NOTICES, las fichas de los modelos y el aviso de privacidad de D5.

### Prueba de humo del ejecutable (a documentar en el PR del build)

Registrar para cada punto: fecha, equipo, resultado y captura.

- [ ] El `.exe` arranca en un equipo limpio sin Python instalado.
- [ ] El dashboard muestra las cámaras y el overlay de EPP (verde, rojo, gris).
- [ ] La vista "Zonas" muestra las casillas de EPP y guarda el archivo en formato v2
      (deja `zonas_config.v1.bak.json` si el archivo era v1).
- [ ] El panel "Alertas EPP" lista infracciones y el botón "Recibido" guarda el acuse.
- [ ] El reporte Excel de cumplimiento se genera sin congelar la interfaz.
- [ ] El módulo EPP se puede desactivar y la aplicación sigue funcionando como 1.x.

## 2. Piloto en modo sombra

Objetivo: el módulo detecta y registra, pero **no notifica**. Un humano audita los eventos antes
de activar los avisos (sombra → canary, skill `mle-workflow`).

1. Instalar 2.0.0 en el sitio piloto con la configuración de D4 y D5.
2. **No** configurar canales de aviso (`EPP_ALERTAS_*`) y **no** arrancar el despachador de avisos
   (`HiloDespachador`). Las infracciones quedan en `ppe_infracciones` como `PENDIENTE`.
3. Durante el período acordado, cada día:
   - exportar el reporte de cumplimiento del día;
   - auditar una muestra de eventos con su evidencia: verdadero o falso positivo;
   - auditar una muestra de video sin eventos: falsos negativos (personas sin EPP no alertadas);
   - registrar métricas a nivel evento (§9.5): falsas alarmas por cámara y por hora, proporción de
     `NO_VERIFICABLE`, latencia hasta el evento, FPS por cámara.
4. Criterios de salida del modo sombra: **los fija el negocio (D4)**. Este runbook no los inventa.

### Antes de activar los avisos

> **Riesgo conocido:** todas las infracciones del período sombra siguen `PENDIENTE`. Si se arranca
> el despachador tal cual, se enviará un aviso por cada una. Antes de activarlo hay que decidir
> qué hacer con ellas (por ejemplo, marcarlas como ya revisadas en la auditoría). Hoy no existe
> una herramienta para eso: queda como tarea pendiente, no se debe resolver con SQL a mano en
> producción sin un procedimiento aprobado.

1. Configurar los canales (D1: email y webhook) por variables de entorno; los secretos van al
   almacén de credenciales, nunca a archivos del repositorio.
2. Probar el canal con una infracción de prueba y verificar el acuse en el panel.
3. Arrancar el despachador y vigilar el panel de alertas y los avisos fallidos.

## 3. Reversión

- Desactivar el módulo EPP (la aplicación vuelve al comportamiento 1.x).
- Zonas: restaurar `zonas_config.v1.bak.json` sobre `zonas_config.json` si hace falta volver al
  formato v1.
- Base de datos (destructivo, manual y con respaldo previo): `quitar_columna_proximo_intento` y
  `eliminar_tabla_infracciones` revierten las migraciones de la bandeja y de las infracciones.
- Reinstalar el instalador 1.x conservado (§9.7).
