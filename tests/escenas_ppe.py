"""Escenas sintéticas para probar el dominio de EPP sin modelos ni cámaras (CLAUDE.md §16).

Un operario estándar mide 100 x 300 píxeles, con la cabeza en el tercio superior, una mano a
cada lado a media altura y cada EPP bien colocado sobre su ancla.
"""

from dataclasses import dataclass

from src.ppe.domain.elementos import ElementoEPP, TipoAncla
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import AnclaDetectada, DeteccionEPP, PersonaDetectada

TODO_EL_EPP = tuple(ElementoEPP)

Rectangulo = tuple[float, float, float, float]

PERSONA: Rectangulo = (0.0, 0.0, 100.0, 300.0)
CABEZA: Rectangulo = (35.0, 5.0, 65.0, 40.0)
MANOS: tuple[Rectangulo, ...] = ((5.0, 140.0, 20.0, 160.0), (80.0, 140.0, 95.0, 160.0))
EPP_COLOCADO: dict[ElementoEPP, tuple[Rectangulo, ...]] = {
    ElementoEPP.CASCO: ((33.0, 0.0, 67.0, 20.0),),
    ElementoEPP.GAFAS: ((38.0, 15.0, 62.0, 22.0),),
    ElementoEPP.BARBIJO: ((40.0, 25.0, 60.0, 38.0),),
    ElementoEPP.CHALECO: ((10.0, 60.0, 90.0, 180.0),),
    ElementoEPP.GUANTES: ((4.0, 139.0, 21.0, 161.0), (79.0, 139.0, 96.0, 161.0)),
}
CASCO_EN_LA_MANO: Rectangulo = (0.0, 130.0, 30.0, 170.0)


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

    def epp(self, *elementos: ElementoEPP) -> tuple[DeteccionEPP, ...]:
        return tuple(
            DeteccionEPP(elemento=elemento, caja=self.caja(rectangulo))
            for elemento in elementos
            for rectangulo in EPP_COLOCADO[elemento]
        )

    def casco_en_la_mano(self) -> DeteccionEPP:
        return DeteccionEPP(elemento=ElementoEPP.CASCO, caja=self.caja(CASCO_EN_LA_MANO))
