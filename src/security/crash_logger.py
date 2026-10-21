# src/security/crash_logger.py
# ===================================================================
# TASK-5.1: Manejo de Excepciones Globales Ofuscadas + Crash Log cifrado
#
# Intercepta cualquier excepcion no controlada (sys.excepthook) para que
# el usuario final B2B NUNCA vea un traceback que revele la arquitectura
# ofuscada. El traceback completo se guarda cifrado simetricamente
# (AES-256-GCM) en %APPDATA%/OficinaEficiencia/Config/crash_logs.dat.
#
# El usuario solo ve "Contacte a Soporte B2B". Soporte puede descifrar el
# log con la clave derivada del hardware (decrypt_crash_logs).
#
# ANTI-VIBE HACKING: el log en disco debe ser ilegible a simple vista;
# no se escribe traceback en texto plano (SPEC 5.1 DoD).
# ===================================================================

import hashlib
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Optional

from Crypto.Cipher import AES  # nosec B413  # WAIVER-#6: es pycryptodome

_logger = logging.getLogger(__name__)

# Etiqueta de derivacion del salt para la clave AES del crash log.
_CRASH_KEY_INFO = b"oe_crash_log_aes256_v1"

# Formato de registro en disco (por cada entrada):
#   MAGIC(4) | nonce(12) | tag(16) | len(4, big-endian) | ciphertext(len)
_MAGIC = b"OEC1"


def _derive_key(machine_id: Optional[str] = None) -> bytes:
    """
    Deriva una clave AES-256 de 32 bytes ligada al hardware.

    Usa el Machine ID del DRM (huella de hardware) como material base, de modo
    que el crash log de una PC no sea descifrable en otra. Si el DRM no esta
    disponible (entorno de prueba), cae a un identificador local estable.
    """
    if machine_id is None:
        try:
            from src.security.drm import DRMValidator
            machine_id = DRMValidator().machine_id
        except Exception:
            import uuid
            machine_id = f"FALLBACK_{uuid.getnode()}"
    return hashlib.sha256(machine_id.encode("utf-8") + _CRASH_KEY_INFO).digest()


def _crash_log_path() -> str:
    """Ruta canonica del crash log cifrado: Config/crash_logs.dat."""
    try:
        from config.path_utils import ConfigManager
        config_dir = ConfigManager.get_appdata_path("Config")
    except Exception:
        config_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "OficinaEficiencia", "Config",
        )
        os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "crash_logs.dat")


def encrypt_entry(plaintext: bytes, machine_id: Optional[str] = None) -> bytes:
    """Cifra una entrada con AES-256-GCM y la enmarca con MAGIC|nonce|tag|len|ct."""
    key = _derive_key(machine_id)
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    length = len(ciphertext).to_bytes(4, "big")
    return _MAGIC + nonce + tag + length + ciphertext


def write_crash(exc_type, exc_value, exc_tb, machine_id: Optional[str] = None) -> str:
    """
    Serializa el traceback, lo cifra y lo anexa al crash log en disco.
    Retorna la ruta del archivo de log.
    """
    header = f"\n===== CRASH {datetime.now().isoformat()} =====\n"
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    record = (header + tb_text).encode("utf-8", errors="replace")

    blob = encrypt_entry(record, machine_id)
    path = _crash_log_path()
    with open(path, "ab") as fh:
        fh.write(blob)
    return path


def decrypt_crash_logs(machine_id: Optional[str] = None, path: Optional[str] = None) -> str:
    """
    Herramienta de Soporte B2B: descifra y concatena todas las entradas del log.
    Solo funciona en la misma maquina (clave derivada del hardware).
    """
    path = path or _crash_log_path()
    if not os.path.exists(path):
        return ""
    key = _derive_key(machine_id)
    out = []
    with open(path, "rb") as fh:
        data = fh.read()

    offset = 0
    while offset < len(data):
        if data[offset:offset + 4] != _MAGIC:
            break
        offset += 4
        nonce = data[offset:offset + 12]; offset += 12
        tag = data[offset:offset + 16]; offset += 16
        length = int.from_bytes(data[offset:offset + 4], "big"); offset += 4
        ciphertext = data[offset:offset + length]; offset += length
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        try:
            out.append(cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="replace"))
        except (ValueError, KeyError):
            out.append("[entrada ilegible: clave incorrecta o log manipulado]")
    return "".join(out)


def install_global_excepthook(notify=None) -> None:
    """
    Instala sys.excepthook para capturar excepciones no controladas.

    Args:
        notify: callback opcional (msg:str) para mostrar un dialogo generico al
                usuario. Si es None, intenta tkinter.messagebox; si falla, imprime.
    """
    def _handler(exc_type, exc_value, exc_tb):
        # KeyboardInterrupt se deja pasar para no romper Ctrl+C en consola.
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            path = write_crash(exc_type, exc_value, exc_tb)
            _logger.error("[CrashLogger] Crash cifrado registrado en %s", path)
        except Exception:
            # Nunca debe fallar el handler de fallos.
            pass

        message = "La aplicación encontró un error inesperado.\n\nContacte a Soporte B2B."
        if notify is not None:
            try:
                notify(message)
                return
            except Exception:
                pass
        try:
            import tkinter as tk
            import tkinter.messagebox
            root = tk.Tk()
            root.withdraw()
            tkinter.messagebox.showerror("Error", message)
            root.destroy()
        except Exception:
            print(message)

    sys.excepthook = _handler
