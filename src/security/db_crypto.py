# src/security/db_crypto.py
# ===================================================================
# TASK-4.3: Cifrado de Base de Datos en Reposo (At-Rest)
#
# La SPEC 1.6.3 exige SQLCipher (PRAGMA key). Como pysqlcipher3 a menudo
# no compila en Windows sin Build Tools + OpenSSL, TASK-0.1 autoriza el
# *fallback* de cifrado a nivel de aplicacion con AES-256.
#
# Estrategia (At-Rest Whole-File Vault):
#   - En reposo, en disco SOLO existe `local_tracking.enc_db` (blob AES-256-GCM
#     ilegible: DB Browser for SQLite lo ve "corrupto" — cumple Auditoria 5.3.2).
#   - Al montar el Tenant, se descifra a `local_tracking.db` (working file).
#   - Al cerrar la app, se re-cifra y se elimina el working file en claro.
#
# La clave se deriva del Machine_Hash (huella de hardware WMI). Si el archivo
# .enc_db se copia a otra PC, la clave no coincide y es indescifrable
# (SPEC 1.6.3). Acceso serializado por el DatabaseWorker (Riesgo 4).
#
# ANTI-VIBE HACKING: la clave NUNCA se guarda en disco en claro; se deriva
# en runtime del hardware.
# ===================================================================

import hashlib
import logging
import os
import sqlite3
from typing import Optional

from Crypto.Cipher import AES  # nosec B413  # WAIVER-#6: es pycryptodome

_logger = logging.getLogger(__name__)

_VAULT_MAGIC = b"OEDB"          # cabecera del blob cifrado
_DB_KEY_INFO = b"oe_db_at_rest_aes256_v1"


def derive_db_key(machine_id: Optional[str] = None) -> bytes:
    """
    Deriva la clave AES-256 (32 bytes) de cifrado de la BD a partir del
    Machine_Hash del DRM. Fallback a un id local estable en entornos de prueba.
    """
    if machine_id is None:
        try:
            from src.security.drm import DRMValidator
            machine_id = DRMValidator().machine_id
        except Exception:
            import uuid
            machine_id = f"FALLBACK_{uuid.getnode()}"
    return hashlib.sha256(machine_id.encode("utf-8") + _DB_KEY_INFO).digest()


def enc_path_for(db_path: str) -> str:
    """Ruta del artefacto cifrado en reposo (.enc_db) para una BD dada."""
    base, _ = os.path.splitext(db_path)
    return base + ".enc_db"


class EncryptedDBVault:
    """
    Boveda de cifrado at-rest para el archivo SQLite del Tenant.

    Uso tipico en el bootstrap del VMS:
        vault = EncryptedDBVault(get_db_path())
        vault.unlock()         # al montar Tenant: .enc_db -> .db (en claro, working)
        ... la app trabaja sobre el .db en claro ...
        vault.lock()           # al cerrar: .db -> .enc_db y borra el .db
    """

    def __init__(self, db_path: str, key: Optional[bytes] = None):
        self.db_path = db_path
        self.enc_path = enc_path_for(db_path)
        self._key = key or derive_db_key()

    # ---- cifrado / descifrado de bytes ----
    def _encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return _VAULT_MAGIC + nonce + tag + ciphertext

    def _decrypt(self, blob: bytes) -> bytes:
        if blob[:4] != _VAULT_MAGIC:
            raise ValueError("Formato de boveda invalido (cabecera no reconocida).")
        nonce = blob[4:16]
        tag = blob[16:32]
        ciphertext = blob[32:]
        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    # ---- operaciones de archivo ----
    def lock(self, remove_plaintext: bool = True) -> str:
        """
        Cifra el working .db a .enc_db. Por defecto elimina el .db en claro
        para que en reposo no quede informacion biometrica legible.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"No existe BD en claro para cifrar: {self.db_path}")
        with open(self.db_path, "rb") as fh:
            plaintext = fh.read()
        blob = self._encrypt(plaintext)
        tmp = self.enc_path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, self.enc_path)
        if remove_plaintext:
            try:
                os.remove(self.db_path)
            except OSError:
                _logger.warning("[DBVault] No se pudo borrar el .db en claro (en uso?).")
        _logger.info("[DBVault] BD cifrada en reposo -> %s", self.enc_path)
        return self.enc_path

    def unlock(self) -> str:
        """
        Descifra .enc_db -> working .db. Si no existe .enc_db, no hace nada
        (primera ejecucion: el DatabaseManager creara la BD desde cero).
        Retorna la ruta del .db en claro.
        """
        if not os.path.exists(self.enc_path):
            return self.db_path
        with open(self.enc_path, "rb") as fh:
            blob = fh.read()
        plaintext = self._decrypt(blob)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with open(self.db_path, "wb") as fh:
            fh.write(plaintext)
        _logger.info("[DBVault] BD descifrada para uso -> %s", self.db_path)
        return self.db_path


def is_sqlite_file(path: str) -> bool:
    """
    True si `path` es un archivo SQLite valido y legible (sin contraseña).
    Usado en pruebas para demostrar que el .enc_db NO es legible (DoD 5.3.2).
    """
    if not os.path.exists(path):
        return False
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("SELECT count(*) FROM sqlite_master;")
            return True
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
