# 7. BUILD & RELEASE: Runbook de Empaquetado B2B (Nuitka → Inno Setup)

Este documento es el **procedimiento operativo** para convertir el código fuente
en un instalador `.exe` distribuible que corre en otra computadora **sin Python
instalado**. Complementa el checklist de aceptación de `5_REVIEW.md`.

> **Cambio del 2026-11-04:** PyArmor (ofuscación, sin licencia comercial) y PyInstaller se
> reemplazaron por **Nuitka 2.8.10** (Apache-2.0), que compila el Python a C: el ejecutable no
> lleva bytecode legible, así que no hace falta un ofuscador aparte. El motor de IA es
> RF-DETR Nano en ONNX Runtime y el reconocimiento facial es YuNet + SFace (OpenCV): el
> ejecutable ya no incluye PyTorch, Ultralytics (AGPL) ni dlib.

> **🚨 PLATAFORMA:** el instalador de distribución se compila en **Windows** (Nuitka no compila
> para otro sistema operativo). En Linux, `python scripts/compilar_ejecutable.py` compila un
> binario de Linux: sirve para probar que el build no se rompió, no para distribuir.

---

## 7.0 Prerrequisitos (PC de build del proveedor)

| Requisito | Versión | Notas |
|---|---|---|
| Windows | 10 / 11 x64 | |
| Python | **3.11 de 64 bits** (python.org) | Nuitka no soporta el Python de la Microsoft Store. |
| Compilador de C | MSVC 2022 (Build Tools) o MinGW64 | Si no hay ninguno, Nuitka descarga MinGW64 solo (`--assume-yes-for-downloads`). |
| Inno Setup | 6.x | `ISCC.exe` en `C:\Program Files (x86)\Inno Setup 6\`. |

---

## 7.1 Paso 0 — Entorno virtual

Desde la raíz del proyecto:

```bat
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt -r requirements-build.txt
```

`compilar_exe.bat` asume que el venv vive en `.\venv\`. `requirements-build.txt` trae solo las
herramientas de build (Nuitka y pip-licenses); no viajan en el ejecutable.

---

## 7.2 Paso 1 — Llaves DRM RSA-2048 (obligatorio antes de vender)

El licenciamiento offline depende de un par de llaves RSA. La **pública** se embebe en
`src/security/drm.py` (`_PUBLIC_KEY_PEM`); la **privada** firma las licencias y **jamás** se
versiona ni se compila en el `.exe`.

> ⚠️ **La llave privada que estuvo en `scripts/` está comprometida:** se versionó y sigue en el
> historial de git. Salió del árbol y está en `.gitignore`, pero hay que **rotar el par** antes del
> primer cliente. Las pruebas generan su propio par y no la necesitan.

En **tu PC** (no en la nube ni en CI):

```bat
python scripts\generar_llaves_maestras.py
```

- `scripts\tu_llave_maestra_privada.pem` → guárdala en un cofre o USB cifrado y haz respaldo.
  Git la ignora.
- `scripts\llave_publica_clientes.pem` → copia su contenido a `_PUBLIC_KEY_PEM` en
  `src/security/drm.py`, corre la suite y haz commit **solo** de la pública.

---

## 7.3 Paso 2 — Modelos de IA y su hash de integridad

Los modelos viven en `models/` y se declaran en `models/manifest.json` (archivo, sha256,
licencias y datasets):

| Archivo | Uso | Licencia de los pesos |
|---|---|---|
| `models/rfdetr/rfdetr-nano-coco-int8.onnx` | Personas y celulares | Apache-2.0 |
| `models/rostros/face_detection_yunet_2023mar.onnx` | Detección de caras | MIT |
| `models/rostros/face_recognition_sface_2021dec.onnx` | Reconocimiento de caras | Apache-2.0 |

El ejecutable verifica el SHA-256 contra `src/models/manifiesto_aprobado.py` y no arranca la
inferencia si no coincide. **Si cambias un modelo:** actualiza su entrada en el manifiesto y
corre `python scripts/generar_manifiesto_embebido.py`.

---

## 7.4 Paso 3 — Build (Nuitka → instalador)

Un solo comando:

```bat
compilar_exe.bat
```

En este orden:

1. Instala `requirements.txt` y `requirements-build.txt` (versiones fijadas).
2. Genera `THIRD_PARTY_NOTICES.txt` con las licencias de terceros del entorno de build.
3. `python scripts\compilar_ejecutable.py` → Nuitka en modo `--standalone` compila
   `src/main_ui.py` y deja la carpeta `build\nuitka\main_ui.dist\` con
   `OficinaEficiencia_VMS.exe`, las DLL, `models\` y `VERSION`. El informe de la compilación
   queda en `build\nuitka\compilacion.xml`. La primera compilación tarda bastante (decenas de
   minutos); las siguientes usan la caché de Nuitka.
4. `ISCC.exe /DMyAppVersion=<VERSION> setup_oficina.iss` → instalador en
   `installer_output\setup_oficina_eficiencia_v<VERSION>.exe`, con la carpeta compilada y los
   avisos de terceros.

La versión sale del archivo `VERSION` (formato `X.Y.Z`; el build se detiene si no lo es).

---

## 7.5 Paso 4 — Validación de aceptación en una SEGUNDA PC limpia

**Esto es lo que convierte "compiló" en "aprobado para distribuir".** Instala en una PC **sin
Python** y completa el checklist de `5_REVIEW.md`. Mínimo:

- [ ] **Arranque sin Python:** el `.exe` abre sin `ModuleNotFoundError` ni faltas de DLL.
- [ ] **DRM/Activación:** muestra el Machine ID; una licencia válida desbloquea; una forjada o
      vencida se rechaza sin traceback.
- [ ] **Detección:** con una cámara real, detecta personas y escribe el tracking en la BD.
- [ ] **Reconocimiento facial:** registrar a un empleado con fotos y que lo reconozca en cámara.
- [ ] **Aislamiento multi-tenant:** un empleado de "Norte" no existe en "Sur".
- [ ] **BD cifrada en reposo:** `local_tracking.enc_db` ilegible con DB Browser.
- [ ] **Reportes Excel** con 4 cámaras activas sin que la UI se congele.
- [ ] **Antivirus:** Windows Defender no marca el `.exe` (si lo hace, firma el binario, §7.7).

---

## 7.6 Paso 5 — Emisión de licencias (flujo comercial)

1. El cliente abre la app y te envía su **Machine ID**.
2. En tu PC, con la llave privada: `python scripts\keygen_b2b.py <MACHINE_ID_DEL_CLIENTE>`.
3. Le envías el bloque Base64; lo pega en "Activación de Software".

---

## 7.7 Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| Nuitka no encuentra compilador de C | Sin MSVC ni MinGW | Instala "Build Tools for Visual Studio 2022" (C++) o deja que Nuitka descargue MinGW64. |
| `FileNotFoundError` de un `.onnx` | Falta `models\` junto al `.exe` | El build usa `--include-data-dir=models=models`; revisa `build\nuitka\main_ui.dist\models\`. |
| "Modelo AI manipulado" | El `.onnx` no coincide con el manifiesto | Regenera el manifiesto embebido (§7.3) y recompila. |
| `ModuleNotFoundError` en el `.exe` | Import dinámico que Nuitka no siguió | Agrega `--include-module=<módulo>` en `scripts/compilar_ejecutable.py` y una prueba. |
| Antivirus marca el `.exe` | Binario sin firmar | Firma con un certificado de firma de código (`signtool sign /fd SHA256 ...`). |
| Licencia válida rechazada | La pública de `drm.py` no es pareja de la privada | Re-embebe la pública (§7.2) y recompila. |

---

## 7.8 Checklist de Release ("Golden Master")

- [ ] Llaves de **producción** rotadas y privada fuera de git (§7.2).
- [ ] Revisión legal D9 cerrada (`docs/legal/revision_d9.md`): datasets de entrenamiento de
      los modelos y fotos de `data/faces/`.
- [ ] `VERSION` incrementado.
- [ ] `compilar_exe.bat` corrió completo sin errores.
- [ ] Checklist de §7.5 y de `5_REVIEW.md` completado en una **segunda PC limpia**.
- [ ] Ejecutable e instalador firmados con certificado de firma de código.
