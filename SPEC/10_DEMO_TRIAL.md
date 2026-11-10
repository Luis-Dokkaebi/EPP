# 10. DEMO: prueba gratis de 14 días que se cobra cuando el modelo ya aprendió

**Estado:** Plan para revisión del dueño del producto
**Revisión:** 1
**Fecha:** 2026-11-10
**Preparado para:** Luis (dueño del producto)
**Base:** análisis del código en `main` (versión `1.3.0`), `SPEC/9_PLAN_EPP_Y_LICENCIA.md` y
`docs/quality/progreso.md`.
**Documento hermano:** [`SPEC/11_MODELO_PARA_VENTA.md`](11_MODELO_PARA_VENTA.md), que explica qué
modelos de IA usar, con pros y contras, y cómo dejar el modelo listo para vender.

> Este documento no es asesoría legal. Las partes de privacidad y contratos se validan con un
> abogado en México antes de la primera instalación en un cliente.

---

## Índice

0. [Respuesta corta](#0-respuesta-corta)
1. [Decisiones tomadas en esta sesión](#1-decisiones-tomadas-en-esta-sesión)
2. [Qué ya funciona hoy](#2-qué-ya-funciona-hoy)
3. [Qué falta para la demo](#3-qué-falta-para-la-demo)
4. [Cómo funciona la prueba: licencia de aprendizaje + 14 días](#4-cómo-funciona-la-prueba-licencia-de-aprendizaje--14-días)
5. [Calendario: de hoy al cobro](#5-calendario-de-hoy-al-cobro)
6. [Entrenar en tu PC con GPU trabajando remoto](#6-entrenar-en-tu-pc-con-gpu-trabajando-remoto)
7. [La PC del cliente: requisitos y visita previa](#7-la-pc-del-cliente-requisitos-y-visita-previa)
8. [Legal en México: lo mínimo antes de instalar](#8-legal-en-méxico-lo-mínimo-antes-de-instalar)
9. [Cómo cerrar la venta](#9-cómo-cerrar-la-venta)
10. [Criterios de aceptación y escenarios Gherkin](#10-criterios-de-aceptación-y-escenarios-gherkin)
11. [Tareas para los agentes, en orden](#11-tareas-para-los-agentes-en-orden)
12. [Riesgos](#12-riesgos)
13. [Checklists imprimibles](#13-checklists-imprimibles)

---

## 0. Respuesta corta

**El software está casi listo; lo que falta es el modelo y el mecanismo de cobro.**

Ya existen el seguimiento de personas, las zonas, el reconocimiento de rostros, toda la lógica de
cumplimiento de EPP, las alertas por email y webhook, el panel de alertas y el reporte de
cumplimiento en Excel. Todo eso está probado y mergeado (`docs/quality/progreso.md`, entregas A-01
a C-13).

Faltan siete cosas. Las cuatro primeras **impiden hacer la demo**:

| # | Falta | Por qué bloquea | Esfuerzo estimado |
|---|-------|-----------------|-------------------|
| 1 | **Un modelo que vea casco, chaleco y cabeza** | El modelo actual (`yolov8n.pt`) solo conoce "persona" y "celular". Sin las tres clases, el módulo EPP no se enciende (`modelo_detecta_epp` en `src/composicion_epp.py`) | 1 semana (base) + 3-4 días por cliente |
| 2 | **La llave privada de licencias está en el repositorio** | `scripts/tu_llave_maestra_privada.pem` está versionada. Quien tenga acceso al repo puede emitir licencias gratis e ilimitadas: el negocio de cobrar no existe mientras esto siga así | 1-2 días |
| 3 | **El generador de licencias no activa el módulo EPP ni sabe hacer pruebas** | `scripts/keygen_b2b.py` no escribe `modulos` en la licencia; con la licencia que emite hoy el EPP **nunca** se activa. Tampoco hay licencia de prueba, aviso de días restantes, ni protección contra atrasar el reloj | 3-4 días |
| 4 | **No se puede entregar el `.exe` al cliente todavía** | Instalarlo en la PC del cliente es *distribuir* el software. Con `ultralytics` dentro, la licencia AGPL-3.0 obliga a publicar el código de todo el producto. Hay que contraer el motor (A-16, ya autorizado por D8) y hacer el build | 3-5 días |
| 5 | Cada modelo nuevo exige recompilar el `.exe` | Los hashes de modelos aprobados viajan dentro del código (`src/models/manifiesto_aprobado.py`). Un modelo afinado para un cliente en medio de la prueba obliga a un build nuevo | 2-3 días (manifiesto firmado) |
| 6 | Documentos legales de la prueba (México) | Aviso de privacidad, consentimiento escrito de los empleados para su rostro y carta de prueba con el cliente | 2-3 días con abogado |
| 7 | Fotos y biometría de personas reales en el repo | `data/faces/` versiona fotos y `encodings.pkl` de personas reales (deuda W-010). Riesgo legal antes de mostrar el producto | 1 día |

**Camino más corto al primer cobro:** unas **3 semanas de preparación** (en paralelo: modelo base
en tu GPU + licencias + build) y luego **la prueba en el cliente** (aprendizaje de ~4 días + 14 días
de prueba). Cobro estimado: **5-6 semanas desde hoy** si nada se atasca. Ver la §5.

**La idea clave de la prueba:** no se entrena un modelo desde cero en cada cliente. Se entrena
**un modelo base antes** de la primera visita (con datos públicos de licencia comercial más fotos
propias) y en el cliente solo se **afina** con sus cámaras. Así "el modelo aprende sus rostros y
sus objetos" en días, no en semanas, y los 14 días de prueba se ven funcionando.

---

## 1. Decisiones tomadas en esta sesión

| ID | Pregunta | Respuesta | Efecto en el plan |
|----|----------|-----------|-------------------|
| T1 | Duración de la prueba y qué pasa al terminar | **14 días; al vencer, la app se bloquea** | §4: licencia de prueba de 14 días; al vencer, ventana de activación |
| T2 | Dónde corre la demo | **En la PC del cliente** | §7: visita previa obligatoria para medir el equipo; la licencia queda ligada a esa PC |
| T3 | Dónde se entrena | **En la PC de Luis con GPU NVIDIA de 6 GB o menos, trabajando remoto** | §6: sí se puede; RF-DETR Nano o Small, lote chico, acumulación de gradientes |
| T4 | Qué objetos aprende el modelo en la demo | **Casco + chaleco** (más `cabeza` y `persona`, que el código necesita como anclas) | Coincide con D3; guantes, gafas y cubrebocas quedan para la v2 |
| T5 | País | **México** | §8: Ley Federal de Protección de Datos Personales en Posesión de los Particulares (2025) |
| T6 | ¿Hay comprador? | **Sí, ya hay uno** | La visita previa se agenda ya; sus cámaras alimentan la afinación |
| T7 | Datos de entrenamiento | **No se compraron; buscar gratuitos con licencia comercial** | Detalle en `SPEC/11` §5 |

Decisiones del plan anterior que siguen vigentes y aplican a la demo (`docs/quality/progreso.md`):
D1 email + webhook, D2 CPU Intel, D3 casco y chaleco, D4 confirmar 4 s y enfriamiento 10 min con
recall por evento ≥ 90 % y ≤ 1 falsa alarma por cámara y hora, D5 evidencias 30 días con el nombre
del empleado y sin difuminar, D8 autorizado tocar el build, D10 módulo activable por licencia.

### 1.1 Decisión que propongo y necesito que confirmes

**P-1. La prueba de 14 días empieza cuando el modelo ya funciona, no el día de la instalación.**
Para eso se usa una *licencia de aprendizaje* (gratis, unos 7 días, sin módulo EPP) mientras se
capturan imágenes, se registran rostros y se afina el modelo; después se emite la licencia de
prueba de 14 días con el EPP encendido. Es lo que pediste ("se cobra después de que el modelo
aprenda") y **no requiere código nuevo**: hoy la app ya funciona sin el módulo EPP. Si prefieres
14 días contados desde la instalación, el calendario de la §5.3 comprime el aprendizaje a los días
1-4 y el cliente ve el EPP funcionando solo 10 días.

---

## 2. Qué ya funciona hoy

Verificado en el código de `main` (no en la documentación vieja):

| Capacidad | Dónde | Estado para la demo |
|-----------|-------|---------------------|
| Captura multicámara USB/RTSP con reconexión | `src/tracking/camera_worker.py` | Lista |
| Seguimiento con ID por persona (ByteTrack de `supervision`, MIT) | `src/tracking/person_tracker.py` | Lista |
| Zonas poligonales con EPP exigido por zona (formato v2) y editor | `src/zones/`, `src/gui/panel_zonas.py` | Lista |
| Registro de rostros (archivo o ráfaga desde la cámara) y reconocimiento | `src/recognition/face_recognizer.py`, `src/gui/views.py` | Lista (ver riesgo R5) |
| Asociación de cada casco/chaleco a su persona, ventana de 4 s, enfriamiento de 10 min | `src/ppe/domain/` | Lista, mutación 100 % |
| Infracciones guardadas en SQLite cifrada | `src/storage/infracciones_epp.py` | Lista |
| Evidencia (foto anotada) con retención de 30 días | `src/tracking/evidencias_epp.py`, `src/storage/retencion_evidencias.py` | Lista |
| Avisos por email (STARTTLS) y webhook firmado con reintentos | `src/alerts/` | Lista; falta configurar el SMTP del cliente |
| Overlay de cumplimiento, panel "Alertas EPP" y menú | `src/tracking/overlay_epp.py`, `src/gui/` | Lista |
| Reporte de cumplimiento en Excel y % de cumplimiento por persona y zona | `src/analysis/reporte_cumplimiento_epp.py` | Lista: es la base del informe de cierre (§9) |
| Modo sombra (evaluar sin avisar, luego descartar) | `features/modo_sombra_epp.feature` | Listo: útil para los primeros días de la prueba |
| Licencia RSA ligada al hardware, con días y cámaras | `src/security/drm.py` | Funciona, pero con los huecos de la §3 |
| Motor ONNX Runtime (MIT) para modelos tipo DETR | `src/inference/adapters/onnx_detector.py` | Listo; falta el modelo |
| Entrenamiento, exportación, paridad y puertas de promoción | `ml/` | Herramientas listas; **nunca se corrió un entrenamiento real** |
| Herramienta de captura del dataset y de replay | `tools/capturar_dataset.py`, `tools/replay.py` | Lista |
| Benchmark de motores en el equipo real | `tools/bench_detectores.py` | Lista; se usa en la visita previa (§7) |

---

## 3. Qué falta para la demo

Prioridades: **P0** sin esto no hay demo; **P1** sin esto la demo sale mal o no se cobra;
**P2** mejora la venta pero puede esperar.

### 3.1 P0 — Bloqueantes

#### F-01. Modelo EPP base (casco, chaleco, cabeza, persona)

- **Hecho:** `models/manifest.json` solo tiene `yolov8n` de COCO. `docs/ml/bitacora.md` está vacía.
- **Qué hacer:** entrenar RF-DETR (Apache-2.0) con datasets públicos de licencia comercial, más
  fotos propias tomadas por ustedes con casco y chaleco en distintos lugares y luces. Exportar a
  ONNX y pasar las puertas de promoción. Todo el detalle está en `SPEC/11` §4 a §7.
- **Ojo con el celular:** la app de eficiencia usa la clase `celular` de COCO para detectar el uso
  del teléfono. El modelo EPP no la tiene en la taxonomía v1. Para la demo de EPP no importa; si
  el cliente también compra el módulo de eficiencia, ver `SPEC/11` §9.
- **Listo cuando:** existe un `.onnx` en `models/` con entrada en el manifiesto, pasa
  `ml/promotion_gates.py` sobre un video de prueba y `modelo_detecta_epp` devuelve verdadero.

#### F-02. Sacar la llave privada del repositorio y rotarla

- **Hecho:** `scripts/tu_llave_maestra_privada.pem` está versionada (riesgo #17 en
  `progreso.md`). Además, `tests/test_drm_rsa_b2b.py` firma licencias con esa misma llave, así que
  las pruebas dependen de ella.
- **Qué hacer:**
  1. Que `DRMValidator` reciba la llave pública por inyección (con la embebida como valor de
     producción) y que las pruebas generen un par de llaves temporal en cada corrida. TDD: primero
     la prueba que falla porque la llave no se puede inyectar.
  2. Generar un par nuevo **fuera del repo** (`scripts/generar_llaves_maestras.py`), con la privada
     protegida por contraseña y guardada en un gestor de contraseñas y en una memoria USB cifrada.
  3. Embeber la pública nueva en `src/security/drm.py` y `scripts/llave_publica_clientes.pem`.
  4. Borrar la privada vieja del repo y agregar `*.pem` privado al `.gitignore`. Purgar el
     historial (`git filter-repo`) es acción humana; con la llave rotada, la vieja deja de servir
     aunque alguien la tenga.
- **Listo cuando:** ninguna llave privada está en el repo (`detect-secrets` limpio sin
  excepciones nuevas) y una licencia firmada con la llave vieja es rechazada (prueba).

#### F-03. Licencias de prueba que activen el EPP y se puedan cobrar

- **Hecho:** `keygen_b2b.py` emite `{"hw_id", "exp", "tier": "enterprise", "max_cams"}`, sin
  `modulos`. `DRMValidator.incluye_modulo("epp")` lee `modulos`, así que hoy el EPP nunca se
  activa con una licencia emitida. La expiración se valida solo al abrir la app y contra el reloj
  local.
- **Qué hacer** (diseño detallado en la §4):
  1. `keygen_b2b.py` no interactivo: `--hw-id`, `--dias`, `--camaras`, `--modulos epp`,
     `--tier aprendizaje|prueba|comercial`, `--cliente <código corto>`. Agrega `emitida` (epoch) e
     `id` (UUID) al contenido firmado. Registra cada emisión en un CSV **fuera del repo** para no
     regalar dos pruebas al mismo hardware.
  2. `DRMValidator`: `dias_restantes()`, `es_prueba()`, y rechazo si la hora local es anterior a
     `emitida` o a la última hora vista (reloj atrasado). La última hora vista se guarda firmada con
     HMAC derivado del `machine_id`, igual que `face_recognizer.py`.
  3. Revalidar la licencia **cada hora** con la app abierta (GUI y modo sin interfaz). Una app que
     corre 24/7 hoy nunca vence.
  4. Al vencer: detener cámaras y avisos, guardar todo y mostrar la ventana de activación con el
     Machine ID y un texto de "contrate para continuar; lo aprendido se conserva".
  5. Banner en la GUI: "Prueba: quedan N días" (en rojo los últimos 3).
- **Listo cuando:** los escenarios de `features/licencia_de_prueba.feature` (§10) pasan y
  `src/security/` mantiene mutación ≥ 90 % (`CLAUDE.md` §9).

#### F-04. Ejecutable sin AGPL que se pueda instalar en el cliente

- **Hecho:** `requirements.txt` incluye `ultralytics==8.1.15`; `config.DETECTION_ENGINE =
  "ultralytics"`; `gui_app.spec` hace `collect_all('ultralytics')`. El gate de licencias falla por
  diseño mientras siga así (AC-001).
- **Qué hacer:** con el modelo de F-01 aprobado: cambiar el motor por omisión a `onnx` (A-15),
  ejecutar A-16 siguiendo [`docs/runbooks/a16_contraer_motor.md`](../docs/runbooks/a16_contraer_motor.md)
  (quitar `ultralytics` y `torch`, borrar los `.pt`, limpiar `gui_app.spec`), y construir el `.exe`
  con la prueba de humo de [`docs/runbooks/piloto_sombra.md`](../docs/runbooks/piloto_sombra.md).
- **Opción B si el modelo se atrasa:** pedir cotización de Ultralytics Enterprise. No lo
  recomiendo: es un costo recurrente y el modelo EPP igual se entrena con RF-DETR.
- **D9 (revisión legal)** sigue pendiente. Para una prueba gratuita en un solo cliente, lo mínimo
  es que el abogado revise el expediente [`docs/legal/revision_d9.md`](../docs/legal/revision_d9.md)
  y el `THIRD_PARTY_NOTICES` que genera la CI.
- **Listo cuando:** `pre-commit run licencias --hook-stage manual` en verde y el `.exe` abre,
  activa una licencia de prueba y muestra una cámara en una PC Windows limpia.

### 3.2 P1 — Necesarias para que la demo salga bien y se cobre

#### F-05. Aprobar un modelo nuevo sin recompilar (manifiesto firmado)

- **Hecho:** `src/models/model_verifier.py` solo acepta los hashes de
  `src/models/manifiesto_aprobado.py`, generado en el build. Afinar el modelo con datos del cliente
  en el día 4 obliga a recompilar, ofuscar y reinstalar el `.exe`.
- **Qué hacer:** aceptar también un `modelo.manifest` **firmado con la misma llave RSA** de las
  licencias (archivo, sha256, clases, cliente, fecha). El verificador comprueba la firma con la
  llave pública embebida y luego el hash. Sigue fallando cerrado: sin firma válida, no carga.
- **Alternativa sin código:** recompilar por cliente (cada build lleva 1-2 h más prueba de humo).
  Aceptable para el primer cliente; no para vender a varios.

#### F-06. Retirar fotos y biometría reales del repo

- `data/faces/` (32 archivos) con `encodings.pkl`. Moverlos fuera del repo, decidir la purga del
  historial (acción humana) y usar solo fotos de ustedes mismos, con consentimiento escrito, para
  las pruebas de la demo.

#### F-07. Documentos legales de la prueba (México)

Ver §8. Sin consentimiento escrito de los empleados, no se registra ningún rostro.

#### F-08. Configuración del cliente en un solo lugar

- Hoy el SMTP y el webhook se configuran por variables de entorno (`src/alerts/configuracion.py`).
  En la PC del cliente eso es frágil. Documentar un `.bat` o una pantalla mínima de configuración
  de avisos. Para la primera demo basta con el `.bat` de arranque con las variables.

#### F-09. Soporte remoto

- Herramienta de acceso remoto aceptada por el área de TI del cliente (la que ellos usen, o
  AnyDesk/TeamViewer con su permiso por escrito). Sin esto, cada problema es un viaje.
- Cómo traer las imágenes capturadas a tu PC de entrenamiento: disco cifrado o carpeta cifrada
  compartida; nunca por correo ni por git (ver §6.3).

### 3.3 P2 — Mejoran la venta, pueden esperar

| ID | Mejora | Motivo |
|----|--------|--------|
| F-10 | Guardar la cámara en cada infracción | Deuda en `progreso.md`: el reporte agrupa por zona, no por cámara |
| F-11 | Arreglar el reporte de eficiencia heredado (`pd.to_datetime` con horas mezcladas) | Solo si la demo también muestra eficiencia |
| F-12 | Quitar la demo de 68 puntos faciales de `src/gui_app.py` | Modelo iBUG 300-W sin uso comercial (`docs/legal/revision_d9.md` §3) |
| F-13 | Estabilizar la CI de Windows (Tk intermitente) | Confianza en el build, no bloquea la demo |
| F-14 | Informe de cierre de la prueba en un clic | Hoy se arma a mano con el Excel de cumplimiento (§9.2) |

---

## 4. Cómo funciona la prueba: licencia de aprendizaje + 14 días

### 4.1 Tipos de licencia

Todas firmadas con RSA-2048, ligadas al Machine ID de la PC del cliente:

| Tier | Días | Módulos | Para qué |
|------|------|---------|----------|
| `aprendizaje` | 7 | ninguno | Instalar, registrar rostros, dibujar zonas, capturar imágenes para afinar. La app funciona como hoy sin EPP |
| `prueba` | 14 | `epp` | Prueba gratuita con el modelo afinado: overlay, alertas y reporte |
| `comercial` | 365 (o lo que se venda) | `epp` (+ eficiencia si se vende) | Después del pago |

Contenido firmado propuesto (todos los campos en el payload que firma RSA):

```json
{"id": "uuid", "cliente": "acme-planta1", "hw_id": "<sha256>", "tier": "prueba",
 "emitida": 1767225600, "exp": 1768435200, "max_cams": 4, "modulos": ["epp"]}
```

### 4.2 Reglas de la licencia de prueba

1. **Una prueba por equipo:** el registro de emisiones (CSV fuera del repo) impide emitir dos
   pruebas para el mismo `hw_id`. Es control del proveedor, no de la app.
2. **Reloj alterado:** si la hora local es anterior a `emitida`, o más de 1 hora anterior a la
   última hora vista, la licencia se rechaza con el mensaje "La fecha del equipo no es correcta".
3. **Vencimiento en caliente:** la app revalida cada hora. Al vencer detiene la detección y los
   avisos, y muestra la ventana de activación. No borra nada.
4. **Lo aprendido se conserva:** al activar la licencia comercial siguen los rostros, zonas, el
   modelo afinado y el historial. Es un argumento de venta: "si compra, no empieza de cero".
5. **Si no compra:** el contrato (§8) fija que el proveedor borra los rostros y las imágenes de
   entrenamiento del cliente en un plazo, por ejemplo, de 15 días, con constancia escrita.

### 4.3 Flujo completo

```
Visita previa ──► Instalación + licencia de aprendizaje (7 d)
                     │  registro de rostros, zonas, captura de ~1.000-2.000 imágenes
                     ▼
                Etiquetado asistido por el modelo base (tú lo revisas)
                     ▼
                Afinación en tu GPU (una noche) ──► puertas de promoción
                     ▼
                Modelo firmado (F-05) instalado + licencia de prueba (14 d)
                     │  días 1-2 en modo sombra (sin avisar), luego alertas reales
                     ▼
                Informe de resultados (día 12) ──► reunión de cierre (día 13)
                     ▼
          Paga ──► licencia comercial         No paga ──► vence, borrado por contrato
```

---

## 5. Calendario: de hoy al cobro

Estimaciones de esfuerzo para dos personas más agentes, sin imprevistos. Se ajustan con la
primera corrida real del entrenamiento.

### 5.1 Preparación (semanas 1 a 3)

| Semana | Pista A: modelo (`SPEC/11`) | Pista B: producto | Pista C: negocio |
|--------|-----------------------------|-------------------|------------------|
| 1 | Descargar datasets y verificar licencias; convertir al contrato; fotos propias (300-500); preparar el entorno de entrenamiento en tu PC | F-02 llaves; F-03 licencias de prueba (TDD) | Visita previa al cliente (§7); borradores legales con el abogado (§8) |
| 2 | Entrenar el modelo base (Nano y Small); exportar a ONNX; paridad; puertas sobre video propio | F-05 manifiesto firmado; F-06 retirar biometría | Acordar criterios de éxito y precio con el cliente (§9.1) |
| 3 | Benchmark en una PC parecida a la del cliente (§7) | F-04: motor ONNX por omisión, A-16, build y prueba de humo | Firmar carta de prueba, aviso de privacidad, consentimientos |

### 5.2 En el cliente (con la licencia de aprendizaje, propuesta P-1)

| Día | Actividad | Responsable |
|-----|-----------|-------------|
| 0 | Instalar el `.exe`, copiar el Machine ID, activar la licencia de aprendizaje, conectar cámaras, dibujar zonas y marcar EPP exigido | Ustedes, en sitio |
| 0 | Registrar rostros de los empleados **que firmaron el consentimiento** (ráfaga de 5-10 fotos por persona, de frente y con casco puesto) | Ustedes + supervisor del cliente |
| 0-3 | Captura automática de imágenes (`tools/capturar_dataset.py`) en varios turnos y luces | Automático |
| 3-4 | Traer imágenes cifradas; preetiquetar con el modelo base; revisar y corregir a mano | Tú (o quien designes) |
| 4 (noche) | Afinar el modelo base con las imágenes del cliente en tu GPU | Tu PC |
| 5 | Puertas de promoción con un video del cliente que no se usó al entrenar; firmar el manifiesto; instalar remotamente; emitir licencia de prueba de 14 días | Tú |

### 5.3 Prueba de 14 días

| Día | Actividad |
|-----|-----------|
| 1-2 | Modo sombra: el sistema evalúa sin avisar. Revisar falsas alarmas cada día y ajustar zonas |
| 3 | Salida del modo sombra (se descartan las infracciones de sombra, decisión ya tomada). Activar email/webhook al responsable de seguridad |
| 3-11 | Alertas reales. Llamada corta con el responsable los días 5 y 9: ¿qué alertas fueron útiles? |
| 7 | (Opcional) Segunda afinación con los errores de la semana. Solo si las falsas alarmas superan 1 por cámara y hora |
| 12 | Informe de resultados (§9.2) |
| 13 | Reunión de cierre con quien decide la compra. Llevar la propuesta y la factura lista |
| 14 | Vence. Si firmó: licencia comercial ese mismo día para que no se bloquee |

Si no aceptas P-1, los días 0-5 de la §5.2 caen dentro de los 14 días y la parte con alertas
reales se reduce a unos 6 días.

---

## 6. Entrenar en tu PC con GPU trabajando remoto

**Respuesta: sí, se puede.** El entrenamiento no necesita estar en la misma ciudad ni en la misma
red que el resto del equipo. Hay tres formas, de la más simple a la más automatizada:

### 6.1 Opción A (recomendada para empezar): tú corres los comandos

1. El código vive en GitHub; tú haces `git pull` en tu PC.
2. Los datos (imágenes del cliente) **no** van a GitHub: se copian a tu PC en un disco o carpeta
   cifrada (BitLocker o VeraCrypt).
3. Corres los comandos del [runbook de entrenamiento](../docs/runbooks/entrenamiento.md); en
   Windows con la GPU, el entorno se crea igual pero con PyTorch para CUDA.
4. Subes el `registro.json` y la entrada de la bitácora al repo; el `.onnx` va al repositorio de
   modelos o a un almacenamiento privado, nunca suelto por correo.

### 6.2 Opción B: un agente usa tu PC por Remote Control

Claude Code puede conectarse a una carpeta de tu PC mediante Remote Control (en la app de
escritorio de Claude: Configuración → Claude Code → Remote Control). Así un agente en la nube corre
el entrenamiento en tu GPU, lee los resultados y llena la bitácora, mientras tú solo dejas la PC
encendida. Requiere que la app de Claude esté abierta en tu PC y que autorices la carpeta.

### 6.3 Opción C: acceso por SSH

Con una VPN privada (por ejemplo Tailscale) y SSH, cualquier persona del equipo lanza el
entrenamiento en tu PC. Útil si son varias personas; requiere más configuración.

### 6.4 Lo que sí o sí hay que cuidar

- **Las imágenes del cliente son datos personales** (rostros de empleados). Se guardan cifradas,
  solo en tu PC, y se borran según el contrato. No se suben a servicios de terceros (Roboflow,
  Colab, etc.) salvo que el contrato lo permita por escrito.
- **Con 6 GB de memoria de GPU:** RF-DETR Nano o Small, resolución 384-512, lote 2-4 y acumulación
  de gradientes para simular un lote de 16. Hoy `ml/entrenador_rfdetr.py` no expone la
  acumulación de gradientes: es una tarea corta (T-09). Ver `SPEC/11` §6.
- **Cómo saber tu tarjeta:** en una terminal, `nvidia-smi` muestra el nombre y la memoria (columna
  `Memory-Usage`, el total a la derecha).
- Deja la PC conectada a corriente, sin suspensión, durante el entrenamiento. Una afinación con
  ~2.000 imágenes debería tardar unas horas; el tiempo real se anota en la bitácora en la primera
  corrida.

---

## 7. La PC del cliente: requisitos y visita previa

Como la demo corre en la PC del cliente, **no se instala nada sin visitarla antes**. La licencia
queda ligada a esa PC; si la cambian, hay que emitir otra.

### 7.1 Requisitos mínimos propuestos (a confirmar con el benchmark)

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| Sistema | Windows 10 64 bits | Windows 11 64 bits |
| CPU | Intel Core i5 de 8.ª generación | Core i5/i7 de 11.ª generación o más reciente |
| RAM | 8 GB | 16 GB |
| Disco libre | 30 GB (evidencias 30 días) | 100 GB SSD |
| Red | Ver las cámaras IP por RTSP desde esa PC | Cable, misma red que las cámaras |
| Encendido | Horario laboral | 24/7, sin suspensión ni actualizaciones automáticas en horario |
| Permisos | Usuario que pueda instalar | Cuenta local dedicada para la app |

### 7.2 Qué hacer en la visita previa (1-2 horas)

1. Correr `tools/bench_detectores.py` con el modelo base en esa PC. La puerta fijada es ≥ 5 FPS
   por cámara y p95 ≤ 200 ms (D2). Si no da, el número de cámaras de la licencia baja, o se
   recomienda un mini-PC.
2. Probar la URL RTSP de cada cámara desde esa PC.
3. Tomar 5-10 fotos por cámara: altura, distancia, luz de día y de noche. Una persona debe medir
   **al menos ~100 px de alto** en el video para ver su casco con confianza; la cara necesita
   más para el reconocimiento facial.
4. Elegir 1-4 cámaras para la prueba: las que miran zonas con EPP obligatorio y tienen buena luz.
   Menos cámaras bien puestas venden más que muchas mal puestas.
5. Saber quién es el responsable de seguridad e higiene que recibirá los avisos y su correo.
6. Preguntar a TI: antivirus (lista blanca para el `.exe`), acceso remoto, salida SMTP.

---

## 8. Legal en México: lo mínimo antes de instalar

La nueva **Ley Federal de Protección de Datos Personales en Posesión de los Particulares** se
publicó el 20 de marzo de 2025 y abrogó la de 2010. Los datos sensibles exigen consentimiento
expreso y por escrito (firma autógrafa, electrónica o un mecanismo de autenticación). Validar con
el abogado si el rostro usado para identificar entra como dato sensible en el texto vigente; el
plan asume que sí, que es lo prudente.

Documentos a preparar con el abogado:

| Documento | Quién firma | Contenido mínimo |
|-----------|-------------|------------------|
| **Carta de prueba (contrato de evaluación)** | Cliente y ustedes | Duración (aprendizaje + 14 días), gratuita, sin garantía de resultados, criterios de éxito (§9.1), precio y condiciones si compra, propiedad y destino de los datos, confidencialidad, borrado si no compra |
| **Acuerdo de tratamiento de datos** | Cliente (responsable) y ustedes (encargado) | Ustedes tratan los datos por cuenta del cliente; medidas de seguridad (base cifrada, retención 30 días); prohibición de usarlos para otro fin **salvo la cláusula de mejora** |
| **Cláusula de mejora del modelo** (opcional, muy valiosa) | Cliente | Permiso para usar imágenes **sin rostros identificables** (o recortes de casco/chaleco) para mejorar el modelo general. Cada cliente que la firme hace mejor el producto para el siguiente |
| **Aviso de privacidad para empleados** | Lo emite el cliente | Qué se captura, para qué (seguridad), cuánto tiempo, derechos ARCO |
| **Consentimiento escrito de cada empleado registrado** | Cada empleado | Uso de su rostro para identificarlo en alertas de seguridad. Quien no firma no se registra: el sistema lo trata como "persona" sin nombre |
| **Autorización de captura para entrenamiento** | Cliente | Es el campo `autorizacion` que exige `docs/ml/contrato_datos.md`: sin él, ninguna imagen entra al dataset |

---

## 9. Cómo cerrar la venta

### 9.1 Antes de instalar: acordar éxito y precio por escrito

La mejor herramienta para cobrar es **acordar antes de la prueba** qué tiene que pasar para que el
cliente compre y a qué precio. Propuesta de criterios (son las puertas que ya fijaron en D4):

| Criterio | Meta |
|----------|------|
| Infracciones reales detectadas (casco o chaleco faltante) | ≥ 90 % de las verificadas en video |
| Falsas alarmas | ≤ 1 por cámara y por hora |
| Tiempo del evento al aviso | ≤ 1 minuto con conexión a internet |
| Disponibilidad | La app corre todo el horario acordado |

Si se cumplen, el cliente se compromete a comprar al precio de la propuesta. Se firma en la carta
de prueba.

### 9.2 Informe de resultados (día 12)

Se arma con el Excel de cumplimiento y el panel de alertas. Una página:

1. Cumplimiento de EPP por zona, por día, al inicio y al final de la prueba (si el número sube, el
   sistema ya generó valor).
2. Infracciones detectadas y confirmadas, con 3-5 fotos de ejemplo (con permiso del cliente).
3. Falsas alarmas por cámara y hora contra la meta.
4. Personas con más infracciones repetidas (solo para el responsable de seguridad).
5. Qué pasa si compra: continuidad sin reinstalar, soporte, siguiente iteración (guantes, gafas,
   cubrebocas).

### 9.3 Estructura de precio sugerida

**Supuesto, sin estudio de mercado verificado:** validar con el prospecto. Estructura recomendada:

| Concepto | Cuándo se cobra | Rango inicial a probar |
|----------|-----------------|------------------------|
| Implementación (visita, instalación, afinación con sus datos) | Al firmar la compra (no durante la prueba) | MXN 20,000 – 45,000 por sitio |
| Licencia anual por equipo, incluye hasta 4 cámaras y el módulo EPP | Anual, por adelantado | MXN 1,000 – 2,000 por cámara al mes, cobrado anual |
| Cámaras adicionales | Con la licencia | Mismo precio por cámara |
| Re-entrenamiento por cambio de uniformes, cámaras o nuevos EPP | Por evento | Cotización |

Tácticas para cobrar rápido:

- **Descuento por firmar dentro de la prueba** (por ejemplo 15 % de la implementación) para que la
  decisión no se alargue después del día 14.
- **Facturar al firmar**, no al terminar la instalación: la instalación ya está hecha.
- Si el cliente duda por el precio, bajar cámaras, no el precio por cámara.

---

## 10. Criterios de aceptación y escenarios Gherkin

Siguiendo `CLAUDE.md` §5, estos criterios se implementan como `.feature` con sus steps. Borrador
del archivo `features/licencia_de_prueba.feature`:

```gherkin
# language: es
Característica: Licencia de prueba del módulo EPP
  Como proveedor
  Quiero dar una prueba gratuita de 14 días que se bloquee al terminar
  Para que el cliente vea el sistema funcionando y luego lo compre

  Escenario: Prueba vigente muestra los días restantes
    Dado una licencia de prueba de 14 días emitida hace 10 días para este equipo
    Cuando abro la aplicación
    Entonces el módulo EPP está activo
    Y veo el aviso "Prueba: quedan 4 días"

  Esquema del escenario: Días restantes de la prueba
    Dado una licencia de prueba de 14 días emitida hace <dias> días para este equipo
    Cuando abro la aplicación
    Entonces veo el aviso "Prueba: quedan <restantes> días"

    Ejemplos:
      | dias | restantes |
      | 0    | 14        |
      | 13   | 1         |

  Escenario: La prueba vence con la aplicación abierta
    Dado una licencia de prueba que vence en 30 minutos
    Y la aplicación está vigilando cámaras
    Cuando pasa una hora
    Entonces la vigilancia se detiene
    Y se pide una licencia para continuar
    Y los rostros, zonas e historial se conservan

  Escenario: Atrasar el reloj no extiende la prueba
    Dado una licencia de prueba vigente
    Y la aplicación ya funcionó hoy
    Cuando la fecha del equipo se atrasa dos días
    Entonces la licencia se rechaza por fecha incorrecta

  Escenario: La licencia comercial conserva lo aprendido
    Dado una licencia de prueba vencida
    Y empleados registrados durante la prueba
    Cuando activo una licencia comercial para este equipo
    Entonces los empleados registrados siguen reconociéndose

  Escenario: Licencia emitida para otro equipo
    Dado una licencia de prueba emitida para otro equipo
    Cuando intento activarla
    Entonces la activación se rechaza
```

Criterios que no son de usuario final y se prueban con pruebas unitarias:

| AC | Criterio | Dónde se prueba |
|----|----------|-----------------|
| AC-T01 | La licencia emitida por el keygen incluye `modulos`, `tier`, `emitida`, `id` y `cliente` firmados | `tests/test_keygen_b2b.py` |
| AC-T02 | El keygen se niega a emitir una segunda prueba para el mismo `hw_id` | `tests/test_keygen_b2b.py` |
| AC-T03 | Una licencia firmada con la llave vieja se rechaza | `tests/test_drm_*.py` |
| AC-T04 | Ninguna prueba lee una llave privada del repositorio | `tests/test_drm_*.py` + `detect-secrets` |
| AC-T05 | Un modelo con manifiesto firmado válido carga; con firma inválida, hash distinto o sin firma, no | `tests/test_model_verifier_*.py` |
| AC-T06 | El gate de licencias está en verde (sin AGPL ni GPL en el runtime) | `scripts/check_licenses.py` |

---

## 11. Tareas para los agentes, en orden

Cada tarea sigue `CLAUDE.md`: TDD (rojo → verde → refactor), Quality Gate completo, PR de 400
líneas o menos con la evidencia pegada. Las marcadas **(H)** necesitan una acción humana.

| # | Tarea | Depende de | Skills | Tamaño |
|---|-------|------------|--------|--------|
| T-01 | Inyectar la llave pública en `DRMValidator`; pruebas con par de llaves temporal | — | `surgical-patch`, `python-testing` | S |
| T-02 | **(H)** Generar el par nuevo fuera del repo; embeber la pública; borrar la privada; purga del historial | T-01 | `security-review` | S |
| T-03 | `keygen_b2b.py` no interactivo con `--modulos`, `--tier`, `--cliente`, `emitida`, `id`, registro de emisiones | T-01 | `lean-build` | M |
| T-04 | `DRMValidator`: `dias_restantes`, `es_prueba`, protección de reloj con última hora vista firmada | T-03 | `python-testing`, `error-handling` | M |
| T-05 | Revalidación periódica y bloqueo en caliente (GUI y sin interfaz) + banner de días | T-04 | `safe-refactor`, `lean-build` | M |
| T-06 | `features/licencia_de_prueba.feature` y sus steps | T-04, T-05 | `python-testing` | S |
| T-07 | Manifiesto de modelo firmado (F-05) | T-02 | `hexagonal-architecture`, `security-review` | M |
| T-08 | **(H)** Retirar `data/faces/` y decidir purga | — | — | S |
| T-09 | `--acumulacion` (gradient accumulation) en `ml/entrenador_rfdetr.py` | — | `surgical-patch` | S |
| T-10 | Modelo base: datos, entrenamiento, ONNX, puertas (`SPEC/11` §11) | T-09 | `mle-workflow`, `benchmark-optimization-loop` | L |
| T-11 | Motor ONNX por omisión (A-15) con el modelo aprobado | T-10 | `migration` | S |
| T-12 | **(H)** A-16: contraer el motor, build del `.exe` y prueba de humo | T-11 | `verify-and-stop` | M |
| T-13 | `.bat` de arranque con la configuración de avisos del cliente | — | `lean-build` | S |
| T-14 | Quitar la demo de 68 puntos faciales (F-12) | — | `surgical-patch` | S |

Ruta crítica: **T-09 → T-10 → T-11 → T-12**. Las tareas T-01 a T-08 corren en paralelo.

---

## 12. Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|--------------|---------|------------|
| R1 | El modelo base no alcanza recall ≥ 90 % en las cámaras del cliente | Media | Alto | Afinación con sus datos; elegir las cámaras con mejor ángulo; segunda afinación el día 7 |
| R2 | La PC del cliente es lenta (< 5 FPS) | Media | Alto | Visita previa con benchmark; modelo Nano; analizar 1 de cada 2 frames (`cada_n_frames`); menos cámaras |
| R3 | El cliente se lleva el `.exe` y lo usa sin pagar | Baja | Medio | Licencia ligada al hardware y a la fecha; protección de reloj (T-04); PyArmor |
| R4 | Muchas falsas alarmas el primer día queman la confianza | Media | Alto | Dos días en modo sombra antes de avisar |
| R5 | El reconocimiento facial falla con casco o a distancia | Alta | Medio | Registrar rostros con casco puesto; cámara de acceso cercana para identificar; si no identifica, la alerta dice "persona sin casco en zona X" con foto |
| R6 | Problema legal por rostros sin consentimiento | Baja si se sigue §8 | Muy alto | Nadie se registra sin firma; retención 30 días; borrado al final |
| R7 | La llave privada vieja ya se filtró | Desconocida | Muy alto | Rotación (T-02) antes de emitir cualquier licencia real |
| R8 | El antivirus del cliente bloquea el `.exe` ofuscado | Media | Medio | Probar en la visita previa; pedir lista blanca a TI; a futuro, firmar el ejecutable con certificado de código |
| R9 | Retraso en el modelo atrasa todo | Media | Alto | Pista A empieza el día 1; si en la semana 2 no pasa las puertas, hacer la demo solo con casco y chaleco en 1-2 cámaras bien puestas |
| R10 | Internet del sitio inestable | Media | Bajo | El outbox reintenta; el panel local muestra todo aunque no salga el correo |

---

## 13. Checklists imprimibles

### Antes de la visita previa

- [ ] Modelo base exportado a ONNX en una memoria USB.
- [ ] `tools/bench_detectores.py` probado en una PC propia.
- [ ] Lista de preguntas a TI (§7.2).
- [ ] Borrador de la carta de prueba con criterios de éxito y precio.

### Antes de instalar

- [ ] Llaves rotadas (T-02); ninguna privada en el repo.
- [ ] `.exe` sin AGPL, con prueba de humo en Windows limpio.
- [ ] Carta de prueba, acuerdo de datos y aviso de privacidad firmados.
- [ ] Consentimientos de los empleados a registrar.
- [ ] Licencia de aprendizaje emitida para el Machine ID de la PC.
- [ ] Acceso remoto acordado con TI.

### Antes de emitir la licencia de prueba

- [ ] Modelo afinado pasa las puertas con un video del cliente no usado al entrenar.
- [ ] Manifiesto del modelo firmado (o build nuevo).
- [ ] Zonas y EPP exigido revisados con el responsable de seguridad.
- [ ] Destinatarios de los avisos configurados y probados con un aviso de prueba.

### Cierre

- [ ] Informe de resultados enviado el día 12.
- [ ] Reunión de cierre el día 13 con quien decide.
- [ ] Propuesta y factura listas.
- [ ] Licencia comercial lista para emitir el mismo día de la firma.

---

## Fuentes

- Código y bitácoras del repositorio: `src/security/drm.py`, `scripts/keygen_b2b.py`,
  `src/composicion_epp.py`, `src/models/model_verifier.py`, `models/manifest.json`,
  `docs/quality/progreso.md`, `docs/ml/bitacora.md`, `docs/legal/revision_d9.md`.
- Ley mexicana de datos personales 2025: [texto oficial, Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf);
  [Garrigues: nueva LFPDPPP](https://www.garrigues.com/es_ES/noticia/mexico-nueva-ley-federal-proteccion-datos-personales-posesion-particulares-introduce);
  [Hogan Lovells: qué significa para las empresas](https://www.hoganlovells.com/es/publications/mexicos-new-federal-data-protection-law-what-it-means-for-companies);
  [IDC: 5 cambios clave](https://idconline.mx/corporativo/2025/03/28/lfpdppp-5-cambios-clave-en-el-manejo-de-datos-personales).
