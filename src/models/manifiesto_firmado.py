"""Manifiesto de modelo firmado por el proveedor (SPEC/10 F-05).

Un modelo afinado para un cliente se instala sin recompilar el ejecutable: viaja con un
`modelo.manifest` firmado con la misma llave RSA de las licencias. Aquí se comprueba la firma con
la llave pública y la forma del contenido. Falla cerrado: sin firma válida no hay manifiesto, y
sin manifiesto el modelo no carga. El hash del archivo lo comprueba `model_verifier`.
"""

import base64
import binascii
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from Crypto.Hash import SHA256  # nosec B413  # WAIVER-#6: es pycryptodome
from Crypto.PublicKey import RSA  # nosec B413  # WAIVER-#6: es pycryptodome
from Crypto.Signature import pkcs1_15  # nosec B413  # WAIVER-#6: es pycryptodome

SEPARADOR_DE_FIRMA = b"||SIGNATURE||"
MOTOR_EXIGIDO = "onnx"
CAMPOS_DEL_MODELO = ("archivo", "sha256", "motor", "version", "clases", "media", "desviacion")


class ManifiestoFirmadoInvalidoError(ValueError):
    """El manifiesto instalado no lleva la firma del proveedor o no describe un modelo ONNX."""


def leer_manifiesto_firmado(ruta: Path, llave_publica: bytes) -> dict[str, Any]:
    """El manifiesto de `ruta` si lo firmó el proveedor y declara un solo modelo ONNX."""
    try:
        carga, separador, firma = base64.b64decode(ruta.read_bytes(), validate=False).partition(
            SEPARADOR_DE_FIRMA
        )
    except (binascii.Error, ValueError) as error:
        raise ManifiestoFirmadoInvalidoError(f"{ruta}: no es un manifiesto firmado.") from error
    if not separador:
        raise ManifiestoFirmadoInvalidoError(f"{ruta}: no es un manifiesto firmado.")
    try:
        pkcs1_15.new(RSA.import_key(llave_publica)).verify(SHA256.new(carga), firma)
    except (ValueError, TypeError) as error:
        raise ManifiestoFirmadoInvalidoError(f"{ruta}: la firma no es del proveedor.") from error
    manifiesto: dict[str, Any] = json.loads(carga)
    if problema := _problema(manifiesto):
        raise ManifiestoFirmadoInvalidoError(f"{ruta}: {problema}")
    return manifiesto


def entrada_del_manifiesto(manifiesto: Mapping[str, Any]) -> Mapping[str, Any]:
    """La única entrada de modelo de un manifiesto firmado ya validado."""
    entrada: Mapping[str, Any] = manifiesto["modelos"][0]
    return entrada


def _problema(manifiesto: Mapping[str, Any]) -> str | None:
    modelos = manifiesto.get("modelos", [])
    if len(modelos) != 1:
        return "debe declarar exactamente un modelo."
    entrada = modelos[0]
    faltante = next((campo for campo in CAMPOS_DEL_MODELO if campo not in entrada), None)
    if faltante is not None:
        return f"al modelo le falta {faltante}."
    if entrada["motor"] != MOTOR_EXIGIDO:
        return f"el motor debe ser {MOTOR_EXIGIDO}."
    if not _es_nombre_sin_carpetas(entrada["archivo"]):
        return "el archivo del modelo debe ser un nombre sin carpetas."
    return None


def _es_nombre_sin_carpetas(archivo: str) -> bool:
    """Ni rutas de Windows ni de Linux: el modelo vive junto a su manifiesto."""
    return archivo not in ("", "..") and all(
        tipo(archivo).name == archivo for tipo in (PurePosixPath, PureWindowsPath)
    )
