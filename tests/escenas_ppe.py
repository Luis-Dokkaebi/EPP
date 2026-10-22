"""Escenas sintéticas para probar el dominio de EPP sin modelos ni cámaras (CLAUDE.md §16).

Un operario estándar mide 100 x 300 píxeles, con la cabeza en el tercio superior y una mano a
cada lado a media altura.
"""

from dataclasses import dataclass

from src.ppe.domain.elementos import TipoAncla
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import AnclaDetectada, PersonaDetectada

Rectangulo = tuple[float, float, float, float]

PERSONA: Rectangulo = (0.0, 0.0, 100.0, 300.0)
CABEZA: Rectangulo = (35.0, 5.0, 65.0, 40.0)
MANOS: tuple[Rectangulo, ...] = ((5.0, 140.0, 20.0, 160.0), (80.0, 140.0, 95.0, 160.0))


@dataclass(frozen=True)
class Operario:
    """Operario estándar desplazado a (x, y) dentro del cuadro."""

    track_id: int
    x: float = 0.0
    y: float = 0.0

    def caja(self, rectangulo: Rectangulo) -> Caja:
        x1, y1, x2, y2 = rectangulo
        return Caja(self.x + x1, self.y + y1, self.x + x2, self.y + y2)

    @property
    def persona(self) -> PersonaDetectada:
        return PersonaDetectada(track_id=self.track_id, caja=self.caja(PERSONA))

    @property
    def cabeza(self) -> AnclaDetectada:
        return AnclaDetectada(tipo=TipoAncla.CABEZA, caja=self.caja(CABEZA))

    @property
    def manos(self) -> tuple[AnclaDetectada, ...]:
        return tuple(AnclaDetectada(tipo=TipoAncla.MANOS, caja=self.caja(m)) for m in MANOS)

    @property
    def anclas(self) -> tuple[AnclaDetectada, ...]:
        return (self.cabeza, *self.manos)
