"""Lo que el dominio de EPP observa en un frame (SPEC/9 §4.1).

El adaptador de inferencia traduce sus detecciones a estos tipos; el dominio no conoce el motor.
"""

from dataclasses import dataclass

from src.ppe.domain.elementos import ElementoEPP, TipoAncla
from src.ppe.domain.errores import ObservacionInvalidaError
from src.ppe.domain.geometria import Caja

ANCLAS_DETECTABLES = frozenset({TipoAncla.CABEZA, TipoAncla.MANOS})


@dataclass(frozen=True)
class PersonaDetectada:
    """Persona seguida en el frame (track_id de ByteTrack)."""

    track_id: int
    caja: Caja


@dataclass(frozen=True)
class AnclaDetectada:
    """Parte del cuerpo detectada (cabeza o manos) que todavía no se asignó a nadie."""

    tipo: TipoAncla
    caja: Caja

    def __post_init__(self) -> None:
        if self.tipo not in ANCLAS_DETECTABLES:
            raise ObservacionInvalidaError(
                f"El ancla {self.tipo.name} no se detecta: se deriva de la caja de la persona"
            )


@dataclass(frozen=True)
class DeteccionEPP:
    """Elemento de EPP detectado, todavía sin dueño."""

    elemento: ElementoEPP
    caja: Caja


@dataclass(frozen=True)
class ObservacionFrame:
    """Todo lo detectado en un frame: personas seguidas, anclas corporales y EPP."""

    personas: tuple[PersonaDetectada, ...]
    anclas: tuple[AnclaDetectada, ...]
    epp: tuple[DeteccionEPP, ...]

    def __post_init__(self) -> None:
        track_ids = sorted(persona.track_id for persona in self.personas)
        if len(set(track_ids)) != len(track_ids):
            raise ObservacionInvalidaError(f"track_id repetido en el frame: {track_ids}")
