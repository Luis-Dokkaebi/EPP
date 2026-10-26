# src/security/drm.py
# ===================================================================
# DRM Validator B2B — Licenciamiento Offline RSA-2048 + Hardware Fingerprint
# ANTI-VIBE HACKING: No mover la PUBLIC_KEY a texto plano fuera de este modulo.
# PyArmor ofuscara este archivo en produccion (Sprint 4, TASK-4.4).
# ===================================================================

import hashlib
import platform
import os
import json
import time
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any

_logger = logging.getLogger(__name__)

# --- RSA-2048 Public Key (Embebida y ofuscada por PyArmor en produccion) ---
# Generada por scripts/generar_llaves_maestras.py — NUNCA distribuir la privada.
_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAm1XdR7BdC1WcE8TsYP7P
OWnTFr54h2XAsJpEQnBRaZKNI1Q+kV+FoaEY6u1cAvzZ0NiAj0EtRD7hHCWYJIdO
In07HldVeFzWWBfl5F2Dkp6yNp96UydSahh5Lc0HPIgBHRHRA60T4fB/h5UtuiT9
FA/TuaMZGDPKq9U0/34Xbl92A0b9sGP+67eR4W/yWztbOzUZU0g8+2jneof1B7Jy
YhKTpxozNoKBVtqSd8hGm29SRtvclWocVUGBmIP1HhjuV2n+NSHkfrxpxxTGRA/u
LUehSTLkk2Kwx5s7LXxkG/hPzZvzJlhV4yOamL1JnNX/PAoQ1xGlILTjshjN/aWl
SQIDAQAB
-----END PUBLIC KEY-----"""

# Salt ofuscado para derivar el Machine Hash (SPEC 1.6.1)
# En produccion PyArmor lo convertira en bytecode C irreversible.
_HARDWARE_SALT = b"0f1c1n4_3f1c13nc14_V1"


class DRMValidator:
    """
    Validador DRM Offline B2B.

    Flujo:
    1. Extrae fingerprint inmutable del hardware (WMI: Board + CPU + Disk).
    2. Valida licencias RSA-2048 firmadas por el proveedor (llave privada).
    3. Compara el Machine ID de la licencia contra el hardware local.
    4. Verifica fecha de expiracion (Epoch).
    5. Extrae el tier de la licencia (max_cams, etc.).
    """

    def __init__(self):
        self.machine_id = self._generate_machine_id()
        # Licencia en APPDATA raiz (abarca todos los Tenants)
        from config.path_utils import ConfigManager
        self.license_path = os.path.join(ConfigManager.get_appdata_path(), "license.key")
        # Datos extraidos de la ultima licencia validada
        self.license_data: Optional[Dict[str, Any]] = None

    # ==================================================================
    # TASK-4.1: Hardware Fingerprint Inmutable (WMI + SHA-256 + Salt)
    # ==================================================================
    def _generate_machine_id(self) -> str:
        """
        Genera un hash SHA-256 determinista del hardware fisico.

        Componentes (SPEC 1.6.1):
        - Win32_BaseBoard.SerialNumber  (Tarjeta madre)
        - Win32_Processor.ProcessorId   (CPU)
        - Win32_DiskDrive.SerialNumber  (Disco principal)

        Fallback: MAC Address + BIOS UUID si WMI falla.
        """
        try:
            import wmi
            c = wmi.WMI()

            # Componente 1: Tarjeta Madre
            boards = c.Win32_BaseBoard()
            board_sn = boards[0].SerialNumber.strip() if boards and boards[0].SerialNumber else "UNKNOWN_BOARD"

            # Componente 2: CPU
            processors = c.Win32_Processor()
            cpu_id = processors[0].ProcessorId.strip() if processors and processors[0].ProcessorId else "UNKNOWN_CPU"

            # Componente 3: Disco de Arranque Principal
            disks = c.Win32_DiskDrive()
            disk_sn = disks[0].SerialNumber.strip() if disks and disks[0].SerialNumber else "UNKNOWN_DISK"

            raw = f"B2B_{cpu_id}_{board_sn}_{disk_sn}"

        except Exception:
            # Fallback: MAC Address + BIOS UUID (SPEC 1.6.1 - Plan B)
            import uuid
            mac = uuid.getnode()
            try:
                import wmi as wmi_fallback
                c2 = wmi_fallback.WMI()
                bios_entries = c2.Win32_ComputerSystemProduct()
                bios_uuid = bios_entries[0].UUID.strip() if bios_entries and bios_entries[0].UUID else "NO_BIOS"
            except Exception:
                bios_uuid = platform.node()

            raw = f"B2B_FALLBACK_{mac}_{bios_uuid}"

        # Derivacion criptografica con Salt ofuscado (SPEC 1.6.1)
        hw_hash = hashlib.sha256(raw.encode('utf-8') + _HARDWARE_SALT).hexdigest()
        return hw_hash

    # ==================================================================
    # TASK-4.2: Validacion de Licencia RSA-2048 (Challenge-Response Offline)
    # ==================================================================
    def validate_license(self) -> bool:
        """
        Lee la licencia almacenada en disco y la valida criptograficamente.
        Retorna True si la licencia es valida, no ha expirado, y coincide con este hardware.
        """
        if not os.path.exists(self.license_path):
            return False

        try:
            with open(self.license_path, "r", encoding="utf-8") as f:
                license_b64 = f.read().strip()

            payload, data = self._verify_and_extract(license_b64)
            if payload is None:
                return False

            self.license_data = data
            return True

        except Exception as exc:
            _logger.warning("[DRM] License validation failed: %s", type(exc).__name__)
            return False

    def activate_license(self, key_input: str) -> bool:
        """
        Valida una licencia Base64 ingresada por el usuario y la persiste en disco.
        Retorna True si la activacion fue exitosa.
        """
        key_input = key_input.strip()
        if not key_input:
            return False

        payload, data = self._verify_and_extract(key_input)
        if payload is None:
            return False

        # Persistir licencia validada en disco
        os.makedirs(os.path.dirname(self.license_path), exist_ok=True)
        with open(self.license_path, "w", encoding="utf-8") as f:
            f.write(key_input)

        self.license_data = data
        return True

    def _verify_and_extract(self, license_b64: str) -> tuple:
        """
        Nucleo criptografico: Decodifica Base64, separa payload de firma,
        verifica la firma RSA-2048 con la llave publica embebida,
        y valida que Machine ID + Fecha de Expiracion sean correctos.

        Retorna (payload_str, data_dict) si es valida, o (None, None) si falla.
        """
        from Crypto.PublicKey import RSA  # nosec B413  # WAIVER-#6: es pycryptodome
        from Crypto.Signature import pkcs1_15  # nosec B413  # WAIVER-#6: es pycryptodome
        from Crypto.Hash import SHA256  # nosec B413  # WAIVER-#6: es pycryptodome

        try:
            # 1. Decodificar Base64
            raw_bytes = base64.b64decode(license_b64)

            # 2. Separar payload de firma (delimitador: ||SIGNATURE||)
            separator = b"||SIGNATURE||"
            if separator not in raw_bytes:
                return None, None

            parts = raw_bytes.split(separator, 1)
            if len(parts) != 2:
                return None, None

            payload_bytes = parts[0]
            signature_bytes = parts[1]

            # 3. Verificar firma RSA-2048 con la llave publica
            public_key = RSA.import_key(_PUBLIC_KEY_PEM)
            hash_obj = SHA256.new(payload_bytes)

            try:
                pkcs1_15.new(public_key).verify(hash_obj, signature_bytes)
            except (ValueError, TypeError):
                # Firma invalida — licencia falsificada o corrompida
                return None, None

            # 4. Parsear payload JSON
            payload_str = payload_bytes.decode('utf-8')
            data = json.loads(payload_str)

            # 5. Validar Machine ID (hw_id debe coincidir con este hardware)
            if data.get("hw_id") != self.machine_id:
                return None, None

            # 6. Validar fecha de expiracion (Epoch)
            exp_epoch = data.get("exp", 0)
            if datetime.now().timestamp() > exp_epoch:
                return None, None

            return payload_str, data

        except Exception as exc:
            _logger.warning("[DRM] Cryptographic verification failed: %s", type(exc).__name__)
            return None, None

    def incluye_modulo(self, modulo: str) -> bool:
        """Si la licencia activa habilita el módulo opcional (D10); sin licencia, ninguno."""
        if self.license_data:
            return modulo in self.license_data.get("modulos", ())
        return False

    def get_max_cameras(self) -> int:
        """Retorna el limite de camaras segun la licencia activa."""
        if self.license_data:
            return self.license_data.get("max_cams", 4)
        return 4

    def get_tier(self) -> str:
        """Retorna el tier de la licencia (enterprise, basic, etc.)."""
        if self.license_data:
            return self.license_data.get("tier", "basic")
        return "basic"

    def get_expiration_date(self) -> Optional[str]:
        """Retorna la fecha de expiracion formateada de la licencia activa."""
        if self.license_data:
            exp = self.license_data.get("exp", 0)
            try:
                return datetime.fromtimestamp(exp).strftime("%Y-%m-%d")
            except (OSError, ValueError):
                return None
        return None
