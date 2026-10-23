# src/models/model_verifier.py
# ===================================================================
# TASK-5.2 + SPEC/9 §1.8: Verificacion de Integridad de Modelos AI (Anti-Tamper)
#
# Calcula el SHA-256 del modelo en disco y lo compara con el hash aprobado
# para ese archivo en MODELOS_APROBADOS (generado desde models/manifest.json
# por scripts/generar_manifiesto_embebido.py). En produccion PyArmor
# (TASK-4.4) ofusca la tabla, como antes el hash fijo EXPECTED_MODEL_SHA256.
#
# Falla cerrada: modelo no declarado, hash distinto o tabla vacia => False,
# y el CameraWorker aborta la inferencia (SPEC 5.2 DoD).
#
# ANTI-VIBE HACKING: No relajar la verificacion devolviendo True por
# defecto ni capturar la excepcion de mismatch silenciosamente en el
# llamador.
# ===================================================================

import hashlib
import hmac
import logging
import os
from collections.abc import Mapping
from pathlib import PurePath

from src.models.manifiesto_aprobado import MODELOS_APROBADOS

_logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB — lectura por bloques para no cargar el modelo completo en RAM


class ModelIntegrityError(RuntimeError):
    """Se lanza cuando el modelo AI en disco no coincide con el hash pre-aprobado."""


def compute_model_hash(model_path: str) -> str:
    """
    Calcula el SHA-256 del archivo de modelo leyendo en bloques.

    Lee de forma binaria estricta (SPEC 5.2.2). Compatible con rutas
    resueltas por get_resource_path() (sys._MEIPASS en binarios B2B).
    """
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Modelo AI no encontrado para verificacion: {model_path}")

    sha = hashlib.sha256()
    with open(model_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _hash_aprobado(model_path: str, aprobados: Mapping[str, str]) -> str | None:
    """Hash de la entrada declarada más específica cuya ruta termina igual que model_path."""
    partes = PurePath(model_path).parts
    candidatas = [
        archivo
        for archivo in aprobados
        if partes[-len(PurePath(archivo).parts) :] == PurePath(archivo).parts
    ]
    if not candidatas:
        return None
    return aprobados[max(candidatas, key=lambda archivo: len(PurePath(archivo).parts))]


def verify_model(model_path: str, aprobados: Mapping[str, str] = MODELOS_APROBADOS) -> bool:
    """
    Verifica que el modelo en disco coincida con el hash aprobado para ese archivo.

    Args:
        model_path: Ruta al modelo (resuelta via get_resource_path).
        aprobados: archivo -> sha256; por defecto la tabla embebida del manifiesto.

    Returns:
        True solo si el archivo está declarado y su hash coincide exactamente.
    """
    actual = compute_model_hash(model_path).lower()
    esperado = _hash_aprobado(model_path, aprobados)
    if esperado is None:
        _logger.error("[ModelVerifier] Modelo no declarado en models/manifest.json: %s", model_path)
        return False
    if not hmac.compare_digest(actual, esperado.lower()):
        _logger.error(
            "[ModelVerifier] Integridad del modelo COMPROMETIDA. esperado=%s... actual=%s...",
            esperado[:12],
            actual[:12],
        )
        return False
    _logger.info("[ModelVerifier] Integridad del modelo AI verificada (SHA-256 OK).")
    return True


def assert_model_integrity(
    model_path: str, aprobados: Mapping[str, str] = MODELOS_APROBADOS
) -> None:
    """
    Igual que verify_model pero lanza ModelIntegrityError si no coincide.
    Usado por CameraWorker para abortar la inferencia ante manipulacion (SPEC 5.2 DoD).
    """
    if not verify_model(model_path, aprobados):
        raise ModelIntegrityError(
            "El modelo AI ha sido manipulado o reemplazado. "
            "Inferencia abortada por seguridad (TASK-5.2)."
        )
