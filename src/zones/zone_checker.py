"""Pertenencia de un punto a las zonas configuradas (Shapely).

Lee el archivo con el lector dual de SPEC/9 §6.3: acepta v1 y v2. El EPP exigido de v2 no cambia
la pertenencia; lo usa el módulo de EPP.
"""

import logging
from pathlib import Path

from shapely.geometry import Point, Polygon

from src.zones.formato_zonas import leer_zonas

ZONAS_POR_DEFECTO = "data/zonas/zonas.json"
LOGGER = logging.getLogger(__name__)


class ZoneChecker:
    def __init__(self, zones_path: str | None = None) -> None:
        ruta = Path(ZONAS_POR_DEFECTO if zones_path is None else zones_path)
        if not ruta.exists():
            LOGGER.warning(
                "Archivo de zonas '%s' no encontrado: se asume que no hay zonas. "
                "Configúrelas en la GUI.",
                ruta,
            )
        self.polygons = {zona.nombre: Polygon(zona.poligono) for zona in leer_zonas(ruta)}

    def check(self, x: float, y: float) -> dict[str, bool]:
        punto = Point(x, y)
        return {nombre: poligono.contains(punto) for nombre, poligono in self.polygons.items()}
