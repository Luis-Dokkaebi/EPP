"""Rota la llave maestra RSA-2048 del proveedor (SPEC/10 F-02). Solo la corre el dueño.

Genera un par nuevo, guarda la llave privada cifrada con contraseña FUERA del repositorio y deja
la llave pública embebida en `src/security/drm.py` y en `scripts/llave_publica_clientes.pem`.
Las licencias y los manifiestos de modelo firmados con la llave anterior dejan de valer.

Uso:
  python scripts/generar_llaves_maestras.py --salida <carpeta fuera del repositorio>

Guarde la carpeta de salida en una memoria USB cifrada y la contraseña en un gestor de
contraseñas. Sin la llave privada no se pueden emitir licencias.
"""

import argparse
import getpass
import re
import sys
from pathlib import Path

from Crypto.PublicKey import RSA

RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[1]
BITS_DE_LA_LLAVE = 2048
LARGO_MINIMO_DE_CONTRASENA = 12
ARCHIVO_PRIVADA = "llave_maestra_privada.pem"
ARCHIVO_PUBLICA = "llave_publica_clientes.pem"
MODULO_DRM = Path("src/security/drm.py")
PUBLICA_ENTREGADA = Path("scripts") / ARCHIVO_PUBLICA
PROTECCION = "scryptAndAES256-CBC"
BLOQUE_PEM = re.compile(r"-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----", re.DOTALL)
CODIGO_DE_RECHAZO = 2


class RotacionInvalidaError(ValueError):
    """La rotación no se puede hacer tal como se pidió."""


def guardar_par_de_llaves(llave: RSA.RsaKey, boveda: Path, contrasena: str) -> None:
    """Escribe en `boveda` la privada cifrada con `contrasena` y la pública en claro."""
    if boveda.resolve().is_relative_to(RAIZ_DEL_REPOSITORIO):
        raise RotacionInvalidaError(
            f"La llave privada no puede guardarse dentro del repositorio ({boveda})."
        )
    if len(contrasena) < LARGO_MINIMO_DE_CONTRASENA:
        raise RotacionInvalidaError(
            f"La contraseña debe tener al menos {LARGO_MINIMO_DE_CONTRASENA} caracteres."
        )
    if (boveda / ARCHIVO_PRIVADA).exists():
        raise RotacionInvalidaError(f"Ya hay una llave en {boveda}: no se sobrescribe.")
    boveda.mkdir(parents=True, exist_ok=True)
    cifrada = llave.export_key(passphrase=contrasena, pkcs=8, protection=PROTECCION)
    (boveda / ARCHIVO_PRIVADA).write_bytes(cifrada)
    (boveda / ARCHIVO_PUBLICA).write_bytes(llave.public_key().export_key())


def embeber_llave_publica(publica: bytes, raiz: Path) -> None:
    """Reemplaza la llave pública del DRM y la que se entrega con el producto."""
    modulo = raiz / MODULO_DRM
    codigo = modulo.read_text(encoding="utf-8")
    if len(BLOQUE_PEM.findall(codigo)) != 1:
        raise RotacionInvalidaError(
            f"{MODULO_DRM.as_posix()} debe tener exactamente una llave pública."
        )
    texto = publica.decode("ascii")
    modulo.write_text(BLOQUE_PEM.sub(lambda _bloque: texto, codigo), encoding="utf-8")
    (raiz / PUBLICA_ENTREGADA).write_bytes(publica)


def _generar() -> RSA.RsaKey:
    return RSA.generate(BITS_DE_LA_LLAVE)


def _pedir_contrasena() -> str:
    contrasena = getpass.getpass("Contraseña nueva para la llave privada: ")
    if getpass.getpass("Repita la contraseña: ") != contrasena:
        raise RotacionInvalidaError("las dos contraseñas no coinciden.")
    return contrasena


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--salida", required=True, type=Path, help="carpeta fuera del repositorio")
    boveda = parser.parse_args(argv).salida
    try:
        contrasena = _pedir_contrasena()
        llave = _generar()
        guardar_par_de_llaves(llave, boveda, contrasena)
        embeber_llave_publica(llave.public_key().export_key(), RAIZ_DEL_REPOSITORIO)
    except (RotacionInvalidaError, OSError) as error:
        sys.stderr.write(f"No se rotó la llave: {error}\n")
        return CODIGO_DE_RECHAZO
    sys.stdout.write(
        f"Par de llaves nuevo en {boveda} (la privada va cifrada con su contraseña).\n"
        f"La llave pública quedó embebida en {MODULO_DRM.as_posix()} y en "
        f"{PUBLICA_ENTREGADA.as_posix()}.\n"
        "Siguiente: borre del repositorio cualquier llave privada anterior, haga commit y "
        "reconstruya el ejecutable. Las licencias y manifiestos firmados con la llave "
        "anterior dejan de valer.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
