"""Licencias firmadas con una llave generada en la corrida (SPEC/10 T-01, AC-T04).

Ninguna prueba lee una llave privada del repositorio: el par se genera aquí y la pública se
inyecta en `DRMValidator`.
"""

import base64
import json
from datetime import datetime
from typing import Any

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

SEPARADOR = b"||SIGNATURE||"
LARGO_DE_LLAVE = 2048  # el mismo largo que la llave del producto


def generar_llave() -> RSA.RsaKey:
    return RSA.generate(LARGO_DE_LLAVE)


def publica_de(llave: RSA.RsaKey) -> bytes:
    return llave.public_key().export_key()


def firmar(llave: RSA.RsaKey, carga: dict[str, Any]) -> str:
    """La licencia en Base64 tal como la entrega el proveedor: carga, separador y firma."""
    texto = json.dumps(carga).encode("utf-8")
    firma = pkcs1_15.new(llave).sign(SHA256.new(texto))
    return base64.b64encode(texto + SEPARADOR + firma).decode("ascii")


class RelojEn:
    """Reemplaza `datetime` en drm: `now()` devuelve siempre el mismo instante."""

    def __init__(self, instante: float) -> None:
        self._instante = instante

    def now(self) -> datetime:
        return datetime.fromtimestamp(self._instante)

    @staticmethod
    def fromtimestamp(instante: float) -> datetime:
        return datetime.fromtimestamp(instante)
