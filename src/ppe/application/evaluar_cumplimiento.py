"""Caso de uso por frame: asociación, ventana temporal, reglas e infracciones (SPEC/9 §4.5).

Recibe las personas seguidas (con sus zonas y su nombre si fueron reconocidas), las anclas y el
EPP del frame, y devuelve el estado por persona para que la UI lo dibuje.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import AnclaDetectada, DeteccionEPP


@dataclass(frozen=True)
class PersonaEnEscena:
    """Persona seguida, las zonas donde está y su nombre si fue reconocida."""

    track_id: int
    caja: Caja
    zonas: frozenset[str]
    nombre: str | None


@dataclass(frozen=True)
class FotogramaEPP:
    """Lo que el pipeline entrega por frame; la imagen es opaca para el dominio."""

    personas: tuple[PersonaEnEscena, ...]
    anclas: tuple[AnclaDetectada, ...]
    epp: tuple[DeteccionEPP, ...]
    imagen: object


@dataclass(frozen=True)
class EstadoCumplimiento:
    """Estado filtrado de cada elemento de una persona y lo que se le exige."""

    track_id: int
    estados: Mapping[ElementoEPP, EstadoElemento]
    exigidos: frozenset[ElementoEPP]

    @property
    def cumple(self) -> bool:
        """Todo lo exigido está presente (lo no verificable no cuenta como cumplido)."""
        return all(self.estados[elemento] is EstadoElemento.PRESENTE for elemento in self.exigidos)
