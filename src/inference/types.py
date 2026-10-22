"""Tipos neutrales de detección (SPEC/9 §1.3.2).

Nombran las clases por su significado y no por el ID de un dataset: cada modelo trae su
`CatalogoDeClases`, así el resto del sistema no depende del orden de clases de COCO ni del EPP.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class CajaInvalidaError(ValueError):
    """La caja no tiene ancho y alto positivos."""


class ConfianzaInvalidaError(ValueError):
    """La confianza no está en el intervalo [0, 1]."""


@dataclass(frozen=True)
class Caja:
    """Caja alineada a los ejes en píxeles del frame (x1, y1) arriba-izquierda."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if not (self.x2 > self.x1 and self.y2 > self.y1):
            raise CajaInvalidaError(
                f"Caja degenerada ({self.x1}, {self.y1}, {self.x2}, {self.y2}): "
                "se necesita x2 > x1 y y2 > y1."
            )


class ClaseObjeto(StrEnum):
    PERSONA = "persona"
    CELULAR = "celular"


def validar_confianza(confianza: float) -> None:
    """Lanza ConfianzaInvalidaError si la confianza no está entre 0 y 1 (NaN incluido)."""
    if not 0.0 <= confianza <= 1.0:
        raise ConfianzaInvalidaError(f"La confianza debe estar entre 0 y 1; llegó {confianza}.")


@dataclass(frozen=True)
class Deteccion:
    clase: ClaseObjeto
    confianza: float
    caja: Caja

    def __post_init__(self) -> None:
        validar_confianza(self.confianza)


class CatalogoDeClases:
    """Traduce el ID de clase de un modelo a una ClaseObjeto; ignora las clases ajenas."""

    def __init__(self, ids: Mapping[int, ClaseObjeto]) -> None:
        self._ids = MappingProxyType(dict(ids))

    def clase_de(self, id_modelo: int) -> ClaseObjeto | None:
        return self._ids.get(id_modelo)


ID_COCO_PERSONA = 0
ID_COCO_CELULAR = 67
CATALOGO_COCO = CatalogoDeClases(
    {ID_COCO_PERSONA: ClaseObjeto.PERSONA, ID_COCO_CELULAR: ClaseObjeto.CELULAR}
)
