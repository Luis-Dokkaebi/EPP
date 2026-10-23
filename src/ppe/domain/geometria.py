"""Geometría propia del dominio de EPP (SPEC/9 §4.1).

El dominio define sus propios tipos: no depende de los tipos del motor de inferencia.
"""

import math
from dataclasses import dataclass

from src.ppe.domain.errores import CajaInvalidaError


@dataclass(frozen=True)
class Caja:
    """Caja alineada a los ejes, en coordenadas de imagen (y crece hacia abajo).

    Admite coordenadas negativas (cajas que salen del cuadro) y cajas degeneradas (ancho o alto
    cero): estas no tienen área, así que nunca cubren nada.
    """

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if not all(map(math.isfinite, (self.x1, self.y1, self.x2, self.y2))):
            raise CajaInvalidaError(f"Caja con coordenadas no finitas: {self}")
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise CajaInvalidaError(f"Caja con esquinas invertidas (x2 < x1 o y2 < y1): {self}")

    @property
    def ancho(self) -> float:
        return self.x2 - self.x1

    @property
    def alto(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.ancho * self.alto

    @property
    def es_degenerada(self) -> bool:
        return self.area == 0

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def area_interseccion(self, otra: "Caja") -> float:
        ancho = min(self.x2, otra.x2) - max(self.x1, otra.x1)
        alto = min(self.y2, otra.y2) - max(self.y1, otra.y1)
        return max(ancho, 0.0) * max(alto, 0.0)

    def ioa(self, region: "Caja") -> float:
        """Intersección con `region` sobre el área propia; 0 si esta caja es degenerada."""
        if self.es_degenerada:
            return 0.0
        return self.area_interseccion(region) / self.area

    def distancia_entre_centros(self, otra: "Caja") -> float:
        return math.dist(self.centro, otra.centro)

    def franja_vertical(self, desde: float, hasta: float) -> "Caja":
        """Franja entre las fracciones `desde` y `hasta` del alto (0 = borde superior)."""
        return Caja(self.x1, self.y1 + self.alto * desde, self.x2, self.y1 + self.alto * hasta)
