# 6. KEYGEN_GUIDE: Sistema Proveedor de Licencias DRM (Offline B2B)

> **Actualización 2026-11-13 (SPEC/10 T-01 a T-07):** el código de este documento es el diseño
> original. Las herramientas vigentes son `scripts/generar_llaves_maestras.py` (llave privada
> cifrada y fuera del repositorio), `scripts/keygen_b2b.py` (tiers `aprendizaje`, `prueba` y
> `comercial`, módulos y registro de emisiones) y `scripts/firmar_manifiesto_modelo.py`. El uso
> paso a paso está en [`docs/runbooks/prueba_14_dias.md`](../docs/runbooks/prueba_14_dias.md).

Este documento es **ESTRICTAMENTE CONFIDENCIAL** para el dueño del negocio (Propietario de "Oficina Eficiencia") y su Agente Inteligente constructor. Detalla cómo desarrollar el **Software Generador de Claves (Keygen B2B)**.

Este programa es *independiente* de "Oficina Eficiencia" y NUNCA se entrega a los clientes. Es tu herramienta interna para emitir licencias cifradas y vender el software.

**🚨 DIRECTIVA ESTRICTA PARA LA IA (ANTI-VIBE HACKING) 🚨**
> *La Inteligencia Artificial encargada de desarrollar esto DEBE mantener este código en un repositorio o carpeta separada (`/tools/keygen_b2b/`). Las Llaves Privadas (Private Keys) generadas por este script NUNCA deben compilarse dentro de `gui_app.spec` ni enviarse al cliente final. El cliente final (Oficina Eficiencia B2B) SOLO debe contener la Llave Pública (Public Key).*

---

## 6.1 Arquitectura Criptográfica del Negocio (RSA-2048)

El modelo de negocio se basa en Criptografía Asimétrica.
1.  **Tú (El Vendedor):** Tienes un par de llaves matemáticas (Privada y Pública).
2.  **La Llave Privada (`private.pem`):** Se usa para FIRMAR (Crear) la licencia de suscripción. *Nadie más en el mundo la tiene.*
3.  **La Llave Pública (`public.pem`):** Se incrusta y ofusca (con PyArmor) dentro del ejecutable del cliente (`OficinaEficiencia_B2B.exe`).
4.  **Validación Offline:** Cuando el cliente ingresa tu Licencia generada, su ejecutable usa la Llave Pública para abrir matemáticamente la licencia. Si la licencia no se generó con TU Llave Privada exacta, o el código de su computadora (Hardware ID) no coincide, el acceso es denegado. Es matemáticamente inquebrantable sin conexión a internet.

---

## 6.2 Código Fuente de Tu "Generador de Licencias B2B" (Tu Herramienta)

Para esta herramienta usaremos la librería estándar y robusta `pycryptodome` (debes instalarla con `pip install pycryptodome`).

### 6.2.1 Script 1: Creación de las Llaves Maestras (Solo se corre 1 vez en tu vida)
Este código genera las llaves `private.pem` (Mantenla en secreto) y `public.pem` (Incrústala en el código fuente de los clientes, en `src/security/drm.py`).

```python
# tools/keygen_b2b/generar_llaves_maestras.py
from Crypto.PublicKey import RSA

def generar_par_de_llaves():
    print("Generando tus llaves B2B de 2048 bits... Esto puede tomar unos segundos.")
    key = RSA.generate(2048)
    
    # 1. Tu Llave Privada (SECRETA - Nunca la envies a nadie)
    private_key = key.export_key()
    with open("tu_llave_maestra_privada.pem", "wb") as f:
        f.write(private_key)
        
    # 2. Tu Llave Publica (DISTRIBUCION - Esta ira dentro del .exe de los clientes)
    public_key = key.publickey().export_key()
    with open("llave_publica_clientes.pem", "wb") as f:
        f.write(public_key)
        
    print("Exito. Guarda 'tu_llave_maestra_privada.pem' en una USB o lugar muy seguro.")

if __name__ == "__main__":
    generar_par_de_llaves()
```

### 6.2.2 Script 2: El Emisor de Suscripciones (Tu Keygen Diario)
Este es el programa que abrirás cuando un cliente te deposite dinero y te envíe su Código de Hardware.

```python
# tools/keygen_b2b/emisor_suscripciones.py
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
import base64
import json
import datetime

class B2B_Keygen:
    def __init__(self, private_key_path: str = "tu_llave_maestra_privada.pem"):
        """Carga tu llave secreta."""
        with open(private_key_path, "rb") as f:
            self.private_key = RSA.import_key(f.read())

    def emitir_licencia(self, client_hardware_id: str, dias_validez: int = 365, max_camaras: int = 4) -> str:
        """
        Genera el bloque de licencia oficial para el cliente.
        
        Args:
            client_hardware_id (str): El codigo que el cliente copio de la app (ej. B2B_A1B2_C3D4)
            dias_validez (int): Tiempo de la suscripcion que el cliente pago.
            max_camaras (int): Limite de licencias de camaras vendidas (Upselling).
        """
        # 1. Calcular Fecha de Vencimiento
        fecha_expiracion = datetime.datetime.now() + datetime.timedelta(days=dias_validez)
        epoch_expiracion = int(fecha_expiracion.timestamp()) # Formato numerico seguro
        
        # 2. Crear el Contrato (Payload)
        payload = {
            "hw_id": client_hardware_id,
            "exp": epoch_expiracion,
            "tier": "enterprise",
            "max_cams": max_camaras
        }
        payload_str = json.dumps(payload, separators=(',', ':')) # Minificado sin espacios
        
        # 3. Firmar el Contrato Matematicamente (Imposible de falsificar)
        hash_obj = SHA256.new(payload_str.encode('utf-8'))
        firma = pkcs1_15.new(self.private_key).sign(hash_obj)
        
        # 4. Empaquetar para el Cliente (Payload + Firma unidos y convertidos a Base64)
        licencia_cruda = payload_str.encode('utf-8') + b"||SIGNATURE||" + firma
        licencia_final_base64 = base64.b64encode(licencia_cruda).decode('utf-8')
        
        print("\n--- NUEVA SUSCRIPCION B2B VENDIDA ---")
        print(f"Cliente Hardware: {client_hardware_id}")
        print(f"Valido hasta: {fecha_expiracion.strftime('%Y-%m-%d')}")
        print(f"Camaras Permitidas: {max_camaras}")
        print("\nCopia este bloque enorme de texto y enviaselo al cliente por correo:")
        print("--------------------------------------------------")
        print(licencia_final_base64)
        print("--------------------------------------------------")
        
        return licencia_final_base64

# Simular una venta en la vida real
if __name__ == "__main__":
    keygen = B2B_Keygen()
    
    print("BIENVENIDO AL PORTAL DE VENTAS (MODO PROPIETARIO)")
    hw_cliente = input("Ingresa el Codigo de Hardware que te envio el cliente: ")
    dias = int(input("Dias de suscripcion pagados (ej. 30, 365): "))
    cams = int(input("Limite de camaras a activar (ej. 4, 16): "))
    
    # Generar la llave Base64
    llave = keygen.emitir_licencia(hw_cliente, dias, cams)
```

---

## 6.3 Cómo el Software del Cliente Valida Esto (Recepción B2B)

Solo como referencia de cómo se cierra el ciclo, esto es lo que el agente (Antigravity) implementará dentro del ejecutable ofuscado del cliente (en `src/security/drm.py` detallado en el Paso 4_IMPLEMENTATION):

1. El cliente pega ese texto Base64 gigante en el campo "Licencia" de `CustomTkinter`.
2. El software extrae el "Payload" y la "Firma" (`||SIGNATURE||`).
3. Compara el `hw_id` del Payload contra el Hardware de la PC en ese instante exacto.
4. Aplica la `llave_publica_clientes.pem`. Si la firma RSA es matemáticamente verdadera y no ha expirado el `exp` (Epoch), el programa se desbloquea.
5. El cliente jamás puede cambiar `"exp": 1735689600` a `"exp": 1900000000` para "hackear" la fecha, porque al cambiar un solo número en el Payload, la Firma Matemática de 2048 bits colapsa y arroja "Licencia Corrupta" al intentar validar con tu Llave Pública.