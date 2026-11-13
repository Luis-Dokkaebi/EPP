# 7. BUILD & RELEASE: Runbook de Empaquetado B2B (PyArmor → PyInstaller → Inno Setup)

Este documento es el **procedimiento operativo** para convertir el código fuente
en un instalador `.exe` distribuible que corre en otra computadora **sin Python
instalado**. Complementa el checklist de aceptación de `5_REVIEW.md`.

> **🚨 PLATAFORMA OBLIGATORIA:** Todo este pipeline es **Windows-only**. PyArmor,
> PyInstaller (target Windows), `wmi`, `pywin32` e Inno Setup **no** funcionan en
> Linux/macOS. No intentes compilar el binario de distribución fuera de Windows.

> **Estado al momento de escribir este runbook:** el código está implementado y
> cubierto por pruebas unitarias (115 + 5 GUI) y revisión de seguridad, pero el
> binario **aún no se ha construido ni validado en Windows**. Este documento es
> la ruta para hacerlo. Hasta completar §7.5 el producto **no** está aprobado
> para distribución (ver `5_REVIEW.md`).

---

## 7.0 Prerrequisitos (PC de Build — la tuya, el proveedor)

| Requisito | Versión | Notas |
|---|---|---|
| Windows | 10 / 11 x64 | El binario heredará el target de esta máquina. |
| Python | **3.10 o 3.11** | NO 3.12+ (PyArmor/PyInstaller no garantizan ofuscado completo — TASK-0.1). |
| Inno Setup | 6.x | `ISCC.exe` en `C:\Program Files (x86)\Inno Setup 6\` (ruta usada por `compilar_exe.bat`). |
| Git | cualquiera | Para clonar/versionar. |
| Visual C++ Build Tools | opcional | Solo si decides intentar `pysqlcipher3` nativo (no requerido: se usa el fallback AES-256). |

Comprueba la versión de Python:
```bat
python --version
```

---

## 7.1 Paso 0 — Entorno virtual y dependencias (Environment Freeze)

Desde la raíz del proyecto (`MLCLAUDE\`):

```bat
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`compilar_exe.bat` asume que el venv vive en `.\venv\` (usa `.\venv\Scripts\pyinstaller`
y `.\venv\Scripts\python.exe`). **No cambies esa ubicación** o ajusta el `.bat`.

Verifica que las herramientas críticas quedaron instaladas:
```bat
pyarmor --version
pyinstaller --version
python -c "import wmi, Crypto, cv2, ultralytics; print('stack OK')"
```

> Si `pysqlcipher3` falla al compilar: **es esperado y NO bloquea**. El cifrado
> de la BD usa el fallback AES-256 a nivel de aplicación (`src/security/db_crypto.py`),
> no SQLCipher nativo (ver TASK-0.1 y `0_REVIEW_FINDINGS` P0-2). `pysqlcipher3`
> **no** está en `requirements.txt` por esta razón.

---

## 7.2 Paso 1 — Llaves DRM RSA-2048 (Provisión del proveedor)

El licenciamiento offline depende de un par de llaves RSA. La **pública** se
embebe en `src/security/drm.py` (`_PUBLIC_KEY_PEM`); la **privada** firma las
licencias y **jamás** se distribuye ni se compila en el `.exe`.

### 7.2.1 Para PRODUCCIÓN (obligatorio antes del primer release real)

El repo incluye un par de llaves de **desarrollo** en `scripts/`. Para un release
comercial **debes rotarlas** (las dev son públicas en el historial de Git):

```bat
python scripts\generar_llaves_maestras.py --salida D:\boveda
```
Esto genera, **fuera del repositorio**:
- `D:\boveda\llave_maestra_privada.pem` → cifrada con la contraseña que pide el script.
- `D:\boveda\llave_publica_clientes.pem`.

Y deja la llave pública nueva embebida en `src/security/drm.py` y en
`scripts\llave_publica_clientes.pem` (ver `docs/runbooks/prueba_14_dias.md` §0).

> ⚠️ **Acción de seguridad pre-release:** tras rotar, confirma que
> `tu_llave_maestra_privada.pem` está en `.gitignore` y **no** se incluye en
> `gui_app.spec` (no lo está). El `.exe` solo debe contener la llave **pública**.
> Re-ejecuta `tests/test_drm_rsa_b2b.py` para confirmar que la privada nueva
> firma licencias que la pública nueva valida.

### 7.2.2 Para PRUEBAS internas
Puedes usar las llaves de desarrollo ya presentes en `scripts/` sin regenerar.

---

## 7.3 Paso 2 — Modelo AI y su hash de integridad

`yolov8n.pt` debe estar en la raíz del proyecto (ya lo está). El módulo
`src/models/model_verifier.py` valida su SHA-256 en runtime (TASK-5.2).

> **Si reemplazas el modelo** (`yolov8n.pt`) por otra versión, debes actualizar
> `EXPECTED_MODEL_SHA256` en `src/models/model_verifier.py`, o el `CameraWorker`
> abortará el tracking por "modelo manipulado". Para recalcular:
> ```bat
> python -c "import hashlib;print(hashlib.sha256(open('yolov8n.pt','rb').read()).hexdigest())"
> ```

---

## 7.4 Paso 3 — Build (Ofuscación → Empaquetado → Instalador)

Un solo comando ejecuta todo el pipeline SECOPS:

```bat
compilar_exe.bat
```

Internamente hace, **en este orden estricto** (Anti-Vibe Hacking — no se puede saltar):

1. **`python obfuscate.py`** → limpia `build/` y `dist/obfuscated/`, y ofusca
   `src/` + `config/` con `pyarmor gen -O dist/obfuscated --enable-jit --restrict 1`.
2. **`pyinstaller gui_app.spec --clean -y`** → empaqueta el código **ofuscado**
   (`gui_app.spec` apunta a `dist\obfuscated\src\main_ui.py`) en
   `dist\OficinaEficiencia_VMS\`. Incluye `yolov8n.pt`, `VERSION`, runtime de
   PyArmor, y los `hiddenimports` de `wmi`/`win32com`/`Crypto`/`ultralytics`/etc.
3. **`ISCC.exe ... setup_oficina.iss`** → genera el instalador en
   `installer_output\setup_oficina_eficiencia_v<VERSION>.exe`.

El número de versión sale del archivo `VERSION` (actual: **1.4.0**) y se inyecta
al `.iss` vía `/DMyAppVersion`.

### Salidas esperadas
```
dist\obfuscated\           <- código ofuscado intermedio
dist\OficinaEficiencia_VMS\OficinaEficiencia_VMS.exe   <- binario portable
installer_output\setup_oficina_eficiencia_v1.4.0.exe   <- INSTALADOR a distribuir
```

### Build manual (si quieres correr pasos por separado para depurar)
```bat
.\venv\Scripts\python.exe obfuscate.py
.\venv\Scripts\pyinstaller gui_app.spec --clean -y
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.4.0 setup_oficina.iss
```

> **Tip de depuración:** `gui_app.spec` tiene `console=True`. Déjalo así durante
> las primeras pruebas para ver tracebacks; cámbialo a `console=False` solo para
> el release final de producción.

---

## 7.5 Paso 4 — Validación de aceptación en una SEGUNDA PC limpia

**Esto es lo que convierte "compiló" en "aprobado para distribuir".** Copia el
instalador a una PC **sin Python ni el toolchain**, instálalo y completa el
checklist de `5_REVIEW.md`. Mínimo imprescindible:

- [ ] **Arranque sin Python:** el `.exe` instalado abre sin "ModuleNotFoundError"
      ni faltas de DLL (libiomp5md, pysqlcipher, etc.).
- [ ] **DRM/Activación (Auditoría 5.3.3):** la app muestra un Machine ID; al pegar
      una licencia válida (§7.6) se desbloquea; una licencia forjada/expirada se
      rechaza sin traceback.
- [ ] **Aislamiento Multi-Tenant (Prueba 5.1.2):** crear 2 sucursales; un empleado
      de "Norte" no existe ni es reconocido en "Sur".
- [ ] **BD cifrada en reposo (Auditoría 5.3.2):** tras cerrar la app, en
      `%APPDATA%\OficinaEficiencia\Tenants\<ID>\db\` existe `local_tracking.enc_db`
      y DB Browser **no** puede abrirlo (aparece corrupto).
- [ ] **Zero-Blocking (Prueba 5.1.1):** generar reporte Excel con 4 cámaras activas
      sin que la UI muestre "No responde".
- [ ] **Crash log cifrado (TASK-5.1):** ante un error, el usuario ve solo "Contacte
      a Soporte B2B" y `Config\crash_logs.dat` es ilegible a simple vista.

Marca estos ítems (y los de `5_REVIEW.md` §5.1–5.4) **sobre el binario**, no sobre
el código.

---

## 7.6 Paso 5 — Emisión de licencias (flujo comercial)

Cuando un cliente compra:

1. El cliente abre la app → copia su **Machine ID** (SHA-256) desde la ventana de
   activación y te lo envía.
2. Tú, en tu PC con la **llave privada**, emites la licencia:
   ```bat
   python scripts\keygen_b2b.py --hw-id <MACHINE_ID_DEL_CLIENTE> --cliente acme-planta1 ^
       --tier prueba --llave D:\boveda\llave_maestra_privada.pem --registro D:\boveda\emisiones.csv
   ```
   (tiers `aprendizaje`, `prueba` y `comercial`: `docs/runbooks/prueba_14_dias.md` §1).
3. Copias el bloque Base64 generado y se lo envías al cliente.
4. El cliente lo pega en "Activación de Software". La app valida la firma RSA
   contra la llave pública embebida y guarda la licencia.

> La llave privada **nunca** sale de tu máquina. El cliente solo recibe el Base64.

---

## 7.7 Troubleshooting (problemas frecuentes del pipeline B2B)

| Síntoma | Causa probable | Solución |
|---|---|---|
| `OMP: Error #15 ... libiomp5md.dll` | Conflicto OpenMP (Torch/Numpy/cv2) | Ya mitigado: `KMP_DUPLICATE_LIB_OK=TRUE` en `compilar_exe.bat`, `gui_app.spec` y `main_ui`. Verifica que no se haya borrado. |
| `ModuleNotFoundError` en el `.exe` (face_recognition, shapely, ultralytics) | PyArmor enmascara imports del analizador de PyInstaller | Añade el módulo a `hiddenimports` en `gui_app.spec` (Riesgo 3, `2_PLANNING`). |
| `FileNotFoundError: yolov8n.pt` | Path roto en binario congelado | El código usa `get_resource_path()` → `sys._MEIPASS`. No uses `os.path.abspath(__file__)` para recursos. |
| Antivirus marca el `.exe` | UPX + bootloader PyInstaller | Pon `upx=False` en `gui_app.spec` o firma el binario con un cert de código. |
| `pyarmor: command not found` en el `.bat` | venv no activado / mal ubicado | Confirma `.\venv\Scripts\pyarmor.exe`. Reinstala `pyarmor==8.4.6`. |
| ISCC no encontrado | Inno Setup en otra ruta | Ajusta la ruta a `ISCC.exe` en `compilar_exe.bat` línea del `[3/3]`. |
| Licencia válida rechazada en cliente | Public key en `drm.py` no corresponde a la privada usada | Re-embebe `llave_publica_clientes.pem` en `_PUBLIC_KEY_PEM` y recompila. |
| WMI vacío en placas genéricas | Servicio WMI corrupto/placa china | Ya manejado: `drm.py` cae a MAC + BIOS UUID (Plan B, SPEC 1.6.1). |

---

## 7.8 Checklist de Release (firma final — "Golden Master")

Antes de entregar el instalador a un cliente:

- [ ] Llaves de **producción** rotadas y privada fuera de Git (§7.2.1).
- [ ] `VERSION` incrementado y reflejado en `setup_oficina.iss`.
- [ ] `console=False` en `gui_app.spec` (release de producción).
- [ ] `compilar_exe.bat` corrió completo sin errores (ofuscación + exe + instalador).
- [ ] **Auditoría 5.3.1 (PyArmor):** `pyinstxtractor` sobre el `.exe` + decompilador
      → `drm.pyc` ilegible ("Invalid Magic Number"), llave pública RSA no visible.
- [ ] Checklist `5_REVIEW.md` §5.1–5.4 completado en una **segunda PC limpia** (§7.5).
- [ ] Backlog consciente revisado: P2-2 (HMAC desde hostname), P2-3 (recovery de
      hardware binding), gaps legales de biometría — decididos o aceptados.

Solo cuando **todo** lo anterior esté marcado, el instalador
`setup_oficina_eficiencia_v1.4.0.exe` se considera **Release Candidate** lista
para distribución B2B.
