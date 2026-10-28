"""Herramienta técnica para dibujar una zona con clics sobre una foto de la cámara.

Uso: python src/zones/zone_editor.py <sucursal>. Los clics marcan las esquinas y la tecla 's'
guarda la zona en el archivo de zonas de la sucursal (formato v2, conserva su EPP exigido).
"""

import logging
import os
import sys
from pathlib import Path

import cv2

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from config.config import get_zonas_file
from src.zones.edicion_zonas import guardar_poligono

LOGGER = logging.getLogger(__name__)
VENTANA = "Seleccione puntos (presione 's' para guardar)"
TECLA_GUARDAR = ord("s")
RADIO_PUNTO = 3
VERDE = (0, 255, 0)


class ZoneEditor:
    def __init__(self, output_path: str | None = None) -> None:
        # Las zonas de la sucursal activa: las mismas que leen la cámara y el módulo de EPP.
        self.output_path = get_zonas_file() if output_path is None else output_path
        # Raíz del proyecto, solo para resolver la ruta de la foto de referencia.
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.points: list[tuple[int, int]] = []

    def click_event(self, event: int, x: int, y: int, *_banderas_y_parametro: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            LOGGER.info("Punto agregado: (%d, %d)", x, y)
            self.points.append((x, y))

    def save_zone(self, zone_name: str) -> None:
        # v2 conservando el EPP exigido de la zona (SPEC/9 §8.3); valida el nombre (TASK-5.3).
        guardar_poligono(Path(self.output_path), zone_name, self.points)
        LOGGER.info("Zona '%s' guardada en %s", zone_name, self.output_path)

    def run(self, image_path: str, zone_name: str) -> None:
        ruta_imagen = os.path.abspath(os.path.join(self.project_root, image_path))
        image = cv2.imread(ruta_imagen)
        if image is None:
            LOGGER.error("No se pudo cargar la imagen %s: verifique la ruta", ruta_imagen)
            return
        clone = image.copy()
        cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(VENTANA, self.click_event)
        while cv2.waitKey(1) & 0xFF != TECLA_GUARDAR:
            image = clone.copy()
            for point in self.points:
                cv2.circle(image, point, RADIO_PUNTO, VERDE, -1)
            cv2.imshow(VENTANA, image)
        cv2.destroyAllWindows()
        self.save_zone(zone_name)


if __name__ == "__main__":
    from config.path_utils import ConfigManager

    logging.basicConfig(level=logging.INFO)
    ConfigManager.set_active_tenant(sys.argv[1])
    ZoneEditor().run("data/zonas/frame_referencia.jpg", "Zona")
