"""EPP exigido por zona y regla global (SPEC/9 §4.3, AC-013).

- Fuera de toda zona configurada solo rige la regla global (opcional).
- En varias zonas se exige la **unión** de sus requisitos; cada elemento se atribuye a cada zona
  que lo exige, porque la infracción y su enfriamiento son por (persona, elemento, zona).
- Un elemento que exige la regla global y también alguna zona de la persona se atribuye a la
  zona (lo más específico), para no duplicar la alerta.

El orden de las exigencias es determinista: zonas en el orden de la configuración, elementos en
el orden de ElementoEPP y al final los de la regla global.
"""

from collections.abc import Set
from dataclasses import dataclass

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ZonaSinPoligonoError

VERTICES_MINIMOS = 3


@dataclass(frozen=True)
class Exigencia:
    """Un elemento exigido y la zona que lo exige (None: la regla global)."""

    elemento: ElementoEPP
    zona: str | None


@dataclass(frozen=True)
class ReglaZona:
    """Zona poligonal y el EPP que exige."""

    nombre: str
    poligono: tuple[tuple[float, float], ...]
    exigidos: frozenset[ElementoEPP]

    def __post_init__(self) -> None:
        if len(self.poligono) < VERTICES_MINIMOS:
            raise ZonaSinPoligonoError(
                f'La zona "{self.nombre}" necesita un polígono de al menos {VERTICES_MINIMOS} '
                f"vértices; tiene {len(self.poligono)}"
            )


@dataclass(frozen=True)
class ReglasEPP:
    """Regla global más reglas por zona."""

    globales: frozenset[ElementoEPP]
    zonas: tuple[ReglaZona, ...]

    def exigencias(self, zonas_de_la_persona: Set[str]) -> tuple[Exigencia, ...]:
        """Lo que se le exige a una persona que está en `zonas_de_la_persona`."""
        por_zona = [
            Exigencia(elemento, zona.nombre)
            for zona in self.zonas
            if zona.nombre in zonas_de_la_persona
            for elemento in ElementoEPP
            if elemento in zona.exigidos
        ]
        cubiertos = {exigencia.elemento for exigencia in por_zona}
        globales = [
            Exigencia(elemento, None)
            for elemento in ElementoEPP
            if elemento in self.globales and elemento not in cubiertos
        ]
        return (*por_zona, *globales)
