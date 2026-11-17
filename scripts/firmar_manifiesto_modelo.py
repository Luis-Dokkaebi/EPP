"""Firma el manifiesto de un modelo afinado para un cliente (SPEC/10 F-05). Solo del proveedor.

Con el `modelo.manifest` firmado, la app del cliente carga el modelo nuevo sin recompilar el
ejecutable. El modelo debe estar declarado en el manifiesto en claro (lo escribe
`ml/export_onnx.py`) y su sha256 debe coincidir con el archivo.

Uso:
  python scripts/firmar_manifiesto_modelo.py --modelo models/epp_acme.onnx \
      --manifiesto models/manifest.json --cliente acme-planta1 \
      --llave <llave privada .pem> --salida <carpeta de entrega>/modelo.manifest
"""

import argparse
import base64
import getpass
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

SEPARADOR_DE_FIRMA = b"||SIGNATURE||"
MOTOR_FIRMABLE = "onnx"
VERSION_DEL_ESQUEMA = 1
BLOQUE_DE_LECTURA = 1 << 20
CLIENTE_VALIDO = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
CODIGO_DE_RECHAZO = 2


class ModeloNoFirmableError(ValueError):
    """El modelo no coincide con lo que declara el manifiesto en claro."""


def _sha256(archivo: Path) -> str:
    resumen = hashlib.sha256()
    with archivo.open("rb") as contenido:
        for bloque in iter(lambda: contenido.read(BLOQUE_DE_LECTURA), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def entrada_del_modelo(modelo: Path, manifiesto: Mapping[str, Any]) -> Mapping[str, Any]:
    """La entrada del manifiesto en claro que declara `modelo`, con su hash comprobado."""
    entrada: Mapping[str, Any] | None = next(
        (m for m in manifiesto.get("modelos", []) if PurePath(m["archivo"]).name == modelo.name),
        None,
    )
    if entrada is None:
        raise ModeloNoFirmableError(f"{modelo.name} no está declarado en el manifiesto.")
    if entrada["motor"] != MOTOR_FIRMABLE:
        raise ModeloNoFirmableError(
            f"Solo se firman modelos del motor {MOTOR_FIRMABLE}; "
            f"{modelo.name} declara {entrada['motor']}."
        )
    if _sha256(modelo) != entrada["sha256"]:
        raise ModeloNoFirmableError(
            f"El sha256 de {modelo.name} no coincide con el del manifiesto: exporta de nuevo."
        )
    return entrada


def contenido_a_firmar(entrada: Mapping[str, Any], cliente: str, fecha: datetime) -> dict[str, Any]:
    """Lo que la app lee del manifiesto firmado: el modelo vive junto a él, sin carpetas."""
    if not CLIENTE_VALIDO.fullmatch(cliente):
        raise ModeloNoFirmableError(
            "El cliente es un código corto: minúsculas, números y guiones (máximo 40)."
        )
    return {
        "version_esquema": VERSION_DEL_ESQUEMA,
        "cliente": cliente,
        "fecha": fecha.isoformat(),
        "modelos": [{**entrada, "archivo": PurePath(entrada["archivo"]).name}],
    }


def _firmar(contenido: Mapping[str, Any], llave: RSA.RsaKey) -> str:
    carga = json.dumps(contenido, separators=(",", ":")).encode("utf-8")
    firma = pkcs1_15.new(llave).sign(SHA256.new(carga))
    return base64.b64encode(carga + SEPARADOR_DE_FIRMA + firma).decode("ascii")


def _cargar_llave(ruta: Path) -> RSA.RsaKey:
    contenido = ruta.read_bytes()
    cifrada = b"ENCRYPTED" in contenido
    clave = getpass.getpass("Contraseña de la llave: ") if cifrada else None
    return RSA.import_key(contenido, passphrase=clave)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for opcion in ("--modelo", "--manifiesto", "--llave", "--salida"):
        parser.add_argument(opcion, required=True, type=Path)
    parser.add_argument("--cliente", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    opciones = _argumentos(argv)
    try:
        manifiesto = json.loads(opciones.manifiesto.read_text(encoding="utf-8"))
        entrada = entrada_del_modelo(opciones.modelo, manifiesto)
        contenido = contenido_a_firmar(entrada, opciones.cliente, _ahora())
        firmado = _firmar(contenido, _cargar_llave(opciones.llave))
    except (ValueError, OSError) as error:
        sys.stderr.write(f"No se firmó el manifiesto: {error}\n")
        return CODIGO_DE_RECHAZO
    opciones.salida.parent.mkdir(parents=True, exist_ok=True)
    opciones.salida.write_text(firmado, encoding="utf-8")
    sys.stdout.write(
        f"Manifiesto firmado en {opciones.salida}.\n"
        f"Copie ese archivo y {opciones.modelo.name} a la carpeta OficinaEficiencia\\modelo "
        "dentro de %APPDATA% del equipo del cliente y reinicie la aplicación.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
