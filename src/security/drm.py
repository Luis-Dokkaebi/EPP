# src/security/drm.py
# ===================================================================
# DRM Validator B2B — Licenciamiento Offline RSA-2048 + Hardware Fingerprint
# ANTI-VIBE HACKING: No mover la PUBLIC_KEY a texto plano fuera de este modulo.
# PyArmor ofuscara este archivo en produccion (Sprint 4, TASK-4.4).
# ===================================================================

import base64
import hashlib
import json
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from src.security.vigencia_licencia import (
    MotivoDeRechazo,
    RegistroDeRelojAlteradoError,
    UltimaHoraVista,
    dias_restantes,
    es_de_prueba,
    motivo_de_rechazo_por_fecha,
)

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
_SEPARADOR = b"||SIGNATURE||"


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

    def __init__(self, llave_publica: bytes = _PUBLIC_KEY_PEM) -> None:
        # SPEC/10 T-01: la llave embebida rige en producción; las pruebas inyectan la suya.
        self._llave_publica = llave_publica
        self.machine_id = self._generate_machine_id()
        # Licencia en APPDATA raiz (abarca todos los Tenants)
        from config.path_utils import ConfigManager

        appdata = ConfigManager.get_appdata_path()
        self.license_path = os.path.join(appdata, "license.key")
        # Datos extraidos de la ultima licencia validada
        self.license_data: dict[str, Any] | None = None
        # Por que no rige la licencia tras la ultima validacion o activacion (SPEC/10 §4.2)
        self.motivo_de_rechazo: MotivoDeRechazo | None = None
        self._ultima_hora_vista = UltimaHoraVista(Path(appdata) / "reloj.sig", self.machine_id)

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
            board_sn = (
                boards[0].SerialNumber.strip()
                if boards and boards[0].SerialNumber
                else "UNKNOWN_BOARD"
            )

            # Componente 2: CPU
            processors = c.Win32_Processor()
            cpu_id = (
                processors[0].ProcessorId.strip()
                if processors and processors[0].ProcessorId
                else "UNKNOWN_CPU"
            )

            # Componente 3: Disco de Arranque Principal
            disks = c.Win32_DiskDrive()
            disk_sn = (
                disks[0].SerialNumber.strip() if disks and disks[0].SerialNumber else "UNKNOWN_DISK"
            )

            raw = f"B2B_{cpu_id}_{board_sn}_{disk_sn}"

        except Exception:
            # Fallback: MAC Address + BIOS UUID (SPEC 1.6.1 - Plan B)
            import uuid

            mac = uuid.getnode()
            try:
                import wmi as wmi_fallback

                c2 = wmi_fallback.WMI()
                bios_entries = c2.Win32_ComputerSystemProduct()
                bios_uuid = (
                    bios_entries[0].UUID.strip()
                    if bios_entries and bios_entries[0].UUID
                    else "NO_BIOS"
                )
            except Exception:
                bios_uuid = platform.node()

            raw = f"B2B_FALLBACK_{mac}_{bios_uuid}"

        # Derivacion criptografica con Salt ofuscado (SPEC 1.6.1)
        hw_hash = hashlib.sha256(raw.encode("utf-8") + _HARDWARE_SALT).hexdigest()
        return hw_hash

    # ==================================================================
    # TASK-4.2: Validacion de Licencia RSA-2048 (Challenge-Response Offline)
    # ==================================================================
    def validate_license(self) -> bool:
        """
        Lee la licencia almacenada en disco y la valida criptograficamente.
        Retorna True si la licencia es valida, no ha expirado, y coincide con este hardware.
        Si deja de regir (SPEC/10 §4.2), ya no habilita modulos y `motivo_de_rechazo` dice por que.
        """
        if not os.path.exists(self.license_path):
            self.license_data = None
            self.motivo_de_rechazo = MotivoDeRechazo.SIN_LICENCIA
            return False

        try:
            with open(self.license_path, encoding="utf-8") as f:
                self.license_data = self._vigente(f.read().strip())
        except (OSError, ValueError) as exc:
            _logger.warning("[DRM] License validation failed: %s", type(exc).__name__)
            self.license_data = None
            self.motivo_de_rechazo = MotivoDeRechazo.INVALIDA
        return self.license_data is not None

    def activate_license(self, key_input: str) -> bool:
        """
        Valida una licencia Base64 ingresada por el usuario y la persiste en disco.
        Retorna True si la activacion fue exitosa; si no, la licencia que ya regia se conserva.
        """
        key_input = key_input.strip()
        data = self._vigente(key_input)
        if data is None:
            return False

        # Persistir licencia validada en disco
        os.makedirs(os.path.dirname(self.license_path), exist_ok=True)
        with open(self.license_path, "w", encoding="utf-8") as f:
            f.write(key_input)

        self.license_data = data
        return True

    def _vigente(self, license_b64: str) -> dict[str, Any] | None:
        """Datos de la licencia si rige ahora; si no, None y el motivo en `motivo_de_rechazo`."""
        data = self._contenido_firmado(license_b64)
        if data is None:
            self.motivo_de_rechazo = MotivoDeRechazo.INVALIDA
            return None
        ahora = datetime.now().timestamp()
        self.motivo_de_rechazo = self._motivo_por_fecha(data, ahora)
        if self.motivo_de_rechazo is not None:
            return None
        self._ultima_hora_vista.anotar(ahora)
        return data

    def _motivo_por_fecha(self, data: dict[str, Any], ahora: float) -> MotivoDeRechazo | None:
        try:
            ultima_vista = self._ultima_hora_vista.leer()
        except RegistroDeRelojAlteradoError:
            return MotivoDeRechazo.FECHA_INCORRECTA
        return motivo_de_rechazo_por_fecha(data, ahora, ultima_vista)

    def _contenido_firmado(self, license_b64: str) -> dict[str, Any] | None:
        """
        Nucleo criptografico: decodifica Base64, separa payload de firma (||SIGNATURE||) y
        verifica la firma RSA-2048 con la llave publica.

        Retorna el contenido solo si la firma es valida y el Machine ID es el de este hardware.
        """
        from Crypto.Hash import SHA256  # nosec B413  # WAIVER-#6: es pycryptodome
        from Crypto.PublicKey import RSA  # nosec B413  # WAIVER-#6: es pycryptodome
        from Crypto.Signature import pkcs1_15  # nosec B413  # WAIVER-#6: es pycryptodome

        try:
            payload, separador, firma = base64.b64decode(license_b64).partition(_SEPARADOR)
            if not separador:
                return None
            try:
                llave = RSA.import_key(self._llave_publica)
                pkcs1_15.new(llave).verify(SHA256.new(payload), firma)
            except (ValueError, TypeError):
                # Firma invalida — licencia falsificada o corrompida
                return None
            data: dict[str, Any] = json.loads(payload.decode("utf-8"))
            return data if data.get("hw_id") == self.machine_id else None
        except Exception as exc:
            _logger.warning("[DRM] Cryptographic verification failed: %s", type(exc).__name__)
            return None

    def dias_restantes(self) -> int | None:
        """Dias que le quedan a la licencia activa (el dia empezado cuenta); None sin licencia."""
        if not self.license_data:
            return None
        return dias_restantes(self.license_data, datetime.now().timestamp())

    def es_prueba(self) -> bool:
        """Si la licencia activa es la prueba gratuita (SPEC/10 §4.1)."""
        return es_de_prueba(self.license_data or {})

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

    def get_expiration_date(self) -> str | None:
        """Retorna la fecha de expiracion formateada de la licencia activa."""
        if self.license_data:
            exp = self.license_data.get("exp", 0)
            try:
                return datetime.fromtimestamp(exp).strftime("%Y-%m-%d")
            except (OSError, ValueError):
                return None
        return None
