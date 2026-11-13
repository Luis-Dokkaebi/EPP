# Runbook: licencias de prueba, modelo firmado y demo (SPEC/10)

Pasos del proveedor para instalar la prueba de 14 días en la PC del cliente. Todo lo que aquí se
corre con `python scripts/...` es **del proveedor**: nunca se copia al equipo del cliente.

## 0. Una sola vez: rotar la llave maestra (acción humana, T-02)

La llave privada que estuvo versionada (`scripts/tu_llave_maestra_privada.pem`, waiver W-010) no
sirve para vender: cualquiera con acceso al repositorio puede emitir licencias. Antes de la
primera licencia real:

```bash
python scripts/generar_llaves_maestras.py --salida <carpeta fuera del repositorio>
git rm scripts/tu_llave_maestra_privada.pem
git add src/security/drm.py scripts/llave_publica_clientes.pem
git commit -m "sec(drm): rotar la llave maestra"
```

- Pide una contraseña de 12 caracteres o más, dos veces. Guárdela en un gestor de contraseñas.
- Deja `llave_maestra_privada.pem` (cifrada) y `llave_publica_clientes.pem` en la carpeta de
  salida. Guarde esa carpeta en una memoria USB cifrada (BitLocker o VeraCrypt) y una copia aparte.
- Embebe la llave pública nueva en `src/security/drm.py`. Hay que **reconstruir el ejecutable**.
- Las licencias y manifiestos firmados con la llave anterior dejan de valer.
- Purgar la llave vieja del historial (`git filter-repo`) sigue siendo decisión humana; con la
  llave rotada, la vieja ya no firma nada que la app acepte.

## 1. Emitir una licencia

El cliente abre la app y copia su **Machine ID** de la ventana de activación.

```bash
python scripts/keygen_b2b.py --hw-id <Machine ID> --cliente acme-planta1 --tier aprendizaje \
    --llave <carpeta>/llave_maestra_privada.pem --registro <carpeta>/emisiones.csv
```

| Tier | Días | Módulos | Cuándo |
|------|------|---------|--------|
| `aprendizaje` | 7 | ninguno | Día 0: instalar, registrar rostros, dibujar zonas, capturar imágenes |
| `prueba` | 14 | `epp` | Cuando el modelo afinado pasó las puertas de promoción |
| `comercial` | 365 | `epp` | El día que firma la compra |

- `--dias`, `--camaras` (por omisión 4) y `--modulos epp,eficiencia` cambian los valores del tier.
- El registro (`emisiones.csv`) vive **fuera del repositorio**. El emisor se niega a dar una
  segunda licencia `prueba` al mismo Machine ID.
- La última línea que imprime es la llave de activación: se envía completa al cliente.

## 2. Instalar el modelo afinado sin recompilar (T-07)

Con el `.onnx` exportado y su entrada en `models/manifest.json`
([runbook de exportación](exportacion_modelo.md)):

```bash
python scripts/firmar_manifiesto_modelo.py --modelo models/epp_acme.onnx \
    --manifiesto models/manifest.json --cliente acme-planta1 \
    --llave <carpeta>/llave_maestra_privada.pem --salida <entrega>/modelo.manifest
```

En la PC del cliente, con la app cerrada, copie `modelo.manifest` y el `.onnx` a
`%APPDATA%\OficinaEficiencia\modelo\` y abra la app. Desde ese momento usa ese modelo con el
motor ONNX. Falla cerrado: si la firma no es del proveedor, el `.onnx` cambió o falta, las
cámaras no infieren y la app lo dice. Para volver al modelo del ejecutable, borre esa carpeta.

El módulo EPP solo se enciende si la licencia incluye `epp` **y** el modelo declara las clases
`casco`, `chaleco` y `cabeza`.

## 3. Arrancar con los avisos configurados (T-13)

Copie `scripts/arranque_cliente.bat` junto a `OficinaEficiencia_VMS.exe`, complete el servidor de
correo o el webhook y abra la app siempre con ese archivo. Viene con el modo sombra encendido
(`EPP_MODO_SOMBRA=1`): los días 1 y 2 de la prueba se registra sin avisar. Para salir de la
sombra, vacíe esa variable y escriba la fecha de salida en `EPP_FIN_MODO_SOMBRA`.

## 3.1 Cargar los rostros de todos los empleados de una vez (T-15)

Arme una carpeta con una subcarpeta por empleado (el nombre de la subcarpeta es el que saldrá en
las alertas) y un `consentimientos.csv`:

```
rostros_acme/
  consentimientos.csv        nombre,id_consentimiento
  Ana Lopez/   foto1.jpg foto2.jpg
  Juan Perez/  foto1.jpg
```

En la app: Gestión de Empleados → "Importar carpeta con consentimientos". Solo se carga a quien
figura en el CSV con un identificador de consentimiento; del resto la pantalla dice por qué no
(sin consentimiento, sin fotos, ya registrado, sin rostro detectable). Cada carga queda en
`importaciones_rostros.csv` dentro de la carpeta de la sucursal, con fecha, usuario de Windows,
nombre, constancia y número de fotos. Las fotos y huellas nunca van al repositorio (SPEC/10 §14.4).

## 4. Qué ve el cliente durante la prueba

- Bajo el título de la barra lateral: "Prueba: quedan N días" (en rojo los últimos tres).
- La app revalida la licencia cada hora. Al vencer detiene cámaras y avisos, **no borra nada** y
  muestra la ventana de activación con el Machine ID. Con una licencia `comercial` pegada ahí,
  sigue funcionando con los mismos rostros, zonas e historial.
- El menú no muestra "Reportes Históricos" (eficiencia) salvo que la licencia incluya el módulo
  `eficiencia` (decisión M-1).

## 5. Problemas frecuentes

| Síntoma | Causa | Qué hacer |
|---------|-------|-----------|
| "La fecha del equipo no es correcta" | El reloj está más de una hora antes de la emisión de la licencia o de la última vez que la app funcionó | Corregir la fecha de Windows. Si la fecha estuvo adelantada por error y la app funcionó así, borrar `%APPDATA%\OficinaEficiencia\reloj.sig` con el proveedor presente |
| "La llave no es válida, está dañada o no corresponde a este equipo" | Llave incompleta, Machine ID de otra PC, o ejecutable construido con otra llave pública | Copiar la llave completa; emitir para el Machine ID que muestra esa PC |
| No aparecen "Alertas EPP" ni "Cumplimiento EPP" | Licencia sin `epp` (aprendizaje) o modelo sin `casco`, `chaleco` y `cabeza` | Emitir `prueba` e instalar el modelo afinado (§2) |
| La cámara no muestra detecciones tras instalar un modelo | Firma o sha256 del modelo instalado no coinciden | Volver a firmar el manifiesto con el `.onnx` que se copió |

## 6. Qué falta para la demo con el comprador

1. **Modelo EPP base (T-10).** No existe todavía un modelo que vea casco, chaleco y cabeza: se
   entrena en la PC con GPU siguiendo el [runbook de entrenamiento](entrenamiento.md). Sin él la
   app abre, sigue personas y muestra la prueba, pero no evalúa EPP.
2. **Rotar la llave (§0)** y **construir el ejecutable** en Windows (T-12,
   [runbook A-16](a16_contraer_motor.md) y [piloto en sombra](piloto_sombra.md)).
3. **Retirar `data/faces/` del repositorio (T-08)** y los documentos legales (SPEC/10 §8).
