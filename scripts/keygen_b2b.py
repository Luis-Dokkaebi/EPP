"""Emisor de licencias del proveedor (SPEC/10 §4, T-03). NUNCA se entrega al cliente.

Firma con la llave privada RSA-2048 una licencia ligada al Machine ID del equipo del cliente y
anota cada emisión en un registro CSV que vive fuera del repositorio. Ese registro impide regalar
dos pruebas al mismo equipo.

Uso:
  python scripts/keygen_b2b.py --hw-id <Machine ID> --cliente acme-planta1 --tier prueba \
      --llave <llave privada .pem> --registro <emisiones.csv fuera del repositorio>

Tiers: aprendizaje (7 días, sin módulos), prueba (14 días, módulo epp) y comercial (365 días,
módulo epp). --dias, --camaras y --modulos cambian los valores por omisión del tier.
"""

import argparse
import base64
import csv
import getpass
import json
import re
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[1]
SEPARADOR_DE_FIRMA = b"||SIGNATURE||"
TIER_DE_PRUEBA = "prueba"
MODULOS_CONOCIDOS = frozenset({"epp", "eficiencia"})
CAMARAS_POR_OMISION = 4
DIAS_MAXIMOS = 3650
CAMARAS_MAXIMAS = 64
MACHINE_ID_VALIDO = re.compile(r"[0-9a-f]{64}")
CLIENTE_VALIDO = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
COLUMNAS_DEL_REGISTRO = (
    "id", "cliente", "hw_id", "tier", "emitida", "vence", "camaras", "modulos",
)  # fmt: skip
CODIGO_DE_RECHAZO = 2


class Tier(NamedTuple):
    dias: int
    modulos: tuple[str, ...]


TIERS = {
    "aprendizaje": Tier(7, ()),
    TIER_DE_PRUEBA: Tier(14, ("epp",)),
    "comercial": Tier(365, ("epp",)),
}


class PedidoInvalidoError(ValueError):
    """El pedido no se puede firmar tal como llegó."""


class PruebaRepetidaError(PedidoInvalidoError):
    """El equipo ya recibió su única licencia de prueba."""


@dataclass(frozen=True)
class Pedido:
    """Lo que el proveedor decide al emitir: para qué equipo, de quién, y con qué alcance."""

    hw_id: str
    cliente: str
    tier: str
    dias: int
    camaras: int
    modulos: tuple[str, ...]


def pedido_del_tier(hw_id: str, cliente: str, tier: str) -> Pedido:
    """Pedido con los días y módulos por omisión del tier."""
    if tier not in TIERS:
        raise PedidoInvalidoError(f"El tier {tier!r} no existe: usa {', '.join(TIERS)}.")
    return Pedido(hw_id, cliente, tier, TIERS[tier].dias, CAMARAS_POR_OMISION, TIERS[tier].modulos)


def _problemas(pedido: Pedido) -> list[str]:
    desconocidos = sorted(set(pedido.modulos) - MODULOS_CONOCIDOS)
    revisiones = (
        (MACHINE_ID_VALIDO.fullmatch(pedido.hw_id), "El Machine ID son 64 caracteres hex."),
        (
            CLIENTE_VALIDO.fullmatch(pedido.cliente),
            "El cliente es un código corto: minúsculas, números y guiones (máximo 40).",
        ),
        (pedido.tier in TIERS, f"El tier {pedido.tier!r} no existe: usa {', '.join(TIERS)}."),
        (1 <= pedido.dias <= DIAS_MAXIMOS, f"Los días van de 1 a {DIAS_MAXIMOS}."),
        (1 <= pedido.camaras <= CAMARAS_MAXIMAS, f"Las cámaras van de 1 a {CAMARAS_MAXIMAS}."),
        (not desconocidos, f"Módulos desconocidos: {', '.join(desconocidos)}."),
    )
    return [mensaje for cumple, mensaje in revisiones if not cumple]


def contenido_de_la_licencia(
    pedido: Pedido, emitida: datetime, identificador: str
) -> dict[str, Any]:
    """El contenido que firma RSA; todo lo que la app lee de la licencia está aquí."""
    return {
        "id": identificador,
        "cliente": pedido.cliente,
        "hw_id": pedido.hw_id,
        "tier": pedido.tier,
        "emitida": int(emitida.timestamp()),
        "exp": int((emitida + timedelta(days=pedido.dias)).timestamp()),
        "max_cams": pedido.camaras,
        "modulos": list(pedido.modulos),
    }


def _firmar(contenido: dict[str, Any], llave: RSA.RsaKey) -> str:
    carga = json.dumps(contenido, separators=(",", ":")).encode("utf-8")
    firma = pkcs1_15.new(llave).sign(SHA256.new(carga))
    return base64.b64encode(carga + SEPARADOR_DE_FIRMA + firma).decode("ascii")


class RegistroDeEmisiones:
    """CSV del proveedor con una fila por licencia emitida; nunca dentro del repositorio."""

    def __init__(self, ruta: Path) -> None:
        if ruta.resolve().is_relative_to(RAIZ_DEL_REPOSITORIO):
            raise PedidoInvalidoError(
                f"El registro de emisiones debe vivir fuera del repositorio, no en {ruta}."
            )
        self.ruta = ruta

    def tuvo_prueba(self, hw_id: str) -> bool:
        if not self.ruta.exists():
            return False
        with self.ruta.open(encoding="utf-8", newline="") as archivo:
            return any(
                fila["hw_id"] == hw_id and fila["tier"] == TIER_DE_PRUEBA
                for fila in csv.DictReader(archivo)
            )

    def anotar(self, contenido: dict[str, Any]) -> None:
        es_nuevo = not self.ruta.exists()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, COLUMNAS_DEL_REGISTRO)
            if es_nuevo:
                escritor.writeheader()
            escritor.writerow(_fila(contenido))


def _fila(contenido: dict[str, Any]) -> dict[str, str]:
    return {
        "id": contenido["id"],
        "cliente": contenido["cliente"],
        "hw_id": contenido["hw_id"],
        "tier": contenido["tier"],
        "emitida": datetime.fromtimestamp(contenido["emitida"], UTC).isoformat(),
        "vence": datetime.fromtimestamp(contenido["exp"], UTC).isoformat(),
        "camaras": str(contenido["max_cams"]),
        "modulos": ",".join(contenido["modulos"]),
    }


def emitir_licencia(
    pedido: Pedido,
    llave: RSA.RsaKey,
    registro: RegistroDeEmisiones,
    emitida: datetime,
    identificador: str,
) -> str:
    """Firma la licencia y la anota en el registro; devuelve la llave de activación Base64."""
    if problemas := _problemas(pedido):
        raise PedidoInvalidoError(" ".join(problemas))
    if pedido.tier == TIER_DE_PRUEBA and registro.tuvo_prueba(pedido.hw_id):
        raise PruebaRepetidaError(
            f"El equipo {pedido.hw_id[:12]}... ya recibió una licencia de prueba (SPEC/10 §4.2)."
        )
    contenido = contenido_de_la_licencia(pedido, emitida, identificador)
    licencia = _firmar(contenido, llave)
    registro.anotar(contenido)
    return licencia


def cargar_llave(ruta: Path, pedir_clave: Callable[[], str]) -> RSA.RsaKey:
    """Llave privada del proveedor; la contraseña solo se pide si el archivo está cifrado."""
    contenido = ruta.read_bytes()
    clave = pedir_clave() if b"ENCRYPTED" in contenido else None
    return RSA.import_key(contenido, passphrase=clave)


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--hw-id", required=True, help="Machine ID que muestra la app")
    parser.add_argument("--cliente", required=True, help="código corto, p. ej. acme-planta1")
    parser.add_argument("--tier", required=True, choices=list(TIERS))
    parser.add_argument("--llave", required=True, type=Path, help="llave privada .pem")
    parser.add_argument("--registro", required=True, type=Path, help="CSV fuera del repositorio")
    parser.add_argument("--dias", type=int, help="por omisión, los del tier")
    parser.add_argument("--camaras", type=int, default=CAMARAS_POR_OMISION)
    parser.add_argument("--modulos", help="separados por coma; por omisión, los del tier")
    return parser.parse_args(argv)


def _pedido(opciones: argparse.Namespace) -> Pedido:
    base = pedido_del_tier(opciones.hw_id, opciones.cliente, opciones.tier)
    modulos = base.modulos
    if opciones.modulos is not None:
        modulos = tuple(modulo for modulo in opciones.modulos.split(",") if modulo)
    dias = base.dias if opciones.dias is None else opciones.dias
    return Pedido(base.hw_id, base.cliente, base.tier, dias, opciones.camaras, modulos)


def _resumen(pedido: Pedido, licencia: str) -> str:
    modulos = ", ".join(pedido.modulos) or "ninguno"
    return (
        f"Licencia {pedido.tier} para {pedido.cliente}: {pedido.dias} días, "
        f"{pedido.camaras} cámaras, módulos: {modulos}.\n"
        "Llave de activación (copiar completa y enviar al cliente):\n"
        f"{licencia}\n"
    )


def main(argv: list[str] | None = None) -> int:
    opciones = _argumentos(argv)
    try:
        pedido = _pedido(opciones)
        registro = RegistroDeEmisiones(opciones.registro)
        llave = cargar_llave(opciones.llave, lambda: getpass.getpass("Contraseña de la llave: "))
        licencia = emitir_licencia(pedido, llave, registro, datetime.now(UTC), str(uuid.uuid4()))
    except (ValueError, OSError) as error:
        sys.stderr.write(f"No se emitió la licencia: {error}\n")
        return CODIGO_DE_RECHAZO
    sys.stdout.write(_resumen(pedido, licencia))
    return 0


if __name__ == "__main__":
    sys.exit(main())
