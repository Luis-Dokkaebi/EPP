"""Presentador del editor de EPP por zona (SPEC/9 §8.3): toda la lógica, sin Tk.

Muestra cada zona con casillas para los elementos que ofrece la instalación (D3: casco y
chaleco primero) y guarda el formato v2 con escribir_zonas, que respalda un v1 y nunca pisa un
archivo corrupto. Los polígonos no se tocan aquí: se dibujan con el editor de zonas.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import FormatoZonasError, escribir_zonas, leer_zonas


class FilaZona(NamedTuple):
    nombre: str
    exigidos: frozenset[ElementoEPP]


class PresentadorZonas:
    """Estado y comandos del editor de EPP por zona."""

    # None: el archivo todavía no se leyó o no se pudo leer; entonces no se puede guardar, porque
    # se pisarían las zonas con una lista vacía.
    _zonas: list[ReglaZona] | None
    hay_cambios: bool
    mensaje: str | None

    def __init__(self, ruta: Path, ofrecidos: Sequence[ElementoEPP]) -> None:
        if not ofrecidos:
            raise ValueError("El editor debe ofrecer al menos un elemento de EPP")
        self._ruta = ruta
        self._ofrecidos = tuple(ofrecidos)
        self._zonas = None
        self.hay_cambios = False
        self.mensaje = None

    @property
    def casillas(self) -> list[tuple[ElementoEPP, str]]:
        return [(elemento, elemento.value.capitalize()) for elemento in self._ofrecidos]

    @property
    def filas(self) -> list[FilaZona]:
        return [FilaZona(zona.nombre, zona.exigidos) for zona in self._zonas or []]

    def cargar(self) -> None:
        """Lee el archivo de zonas y descarta los cambios sin guardar."""
        self.hay_cambios = False
        try:
            self._zonas = list(leer_zonas(self._ruta))
        except FormatoZonasError as error:
            self._zonas = None
            self.mensaje = f"No se pudo leer el archivo de zonas: {error}"
            return
        self.mensaje = None if self._zonas else "No hay zonas configuradas para esta sucursal"

    def alternar(self, nombre: str, elemento: ElementoEPP) -> None:
        zonas = self._zonas or []
        posicion = _posicion(zonas, nombre)
        zona = zonas[posicion]
        zonas[posicion] = ReglaZona(zona.nombre, zona.poligono, zona.exigidos ^ {elemento})
        self.hay_cambios = True

    def guardar(self) -> None:
        if self._zonas is None:
            return
        try:
            escribir_zonas(self._ruta, self._zonas)
        except OSError as error:
            self.mensaje = f"No se pudieron guardar las zonas: {error}"
            return
        self.hay_cambios = False
        self.mensaje = "Zonas guardadas"


def _posicion(zonas: list[ReglaZona], nombre: str) -> int:
    for posicion, zona in enumerate(zonas):
        if zona.nombre == nombre:
            return posicion
    raise KeyError(f"Zona desconocida: {nombre}")
