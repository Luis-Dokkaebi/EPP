"""Raíz de composición única (SPEC/9 §1.3.6).

La GUI (`main_ui.py`) y el modo headless (`main.py`) crean el detector con esta función: la
lección de CR-04 es no volver a tener dos caminos que divergen.
"""

from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.ports import DetectorPort
from src.inference.types import CATALOGO_COCO


def crear_detector(ruta_modelo: str, confianza_minima: float) -> DetectorPort:
    """Detector del motor vigente; hoy Ultralytics hasta que A-15 haga ONNX el motor por defecto."""
    # Import diferido: el motor AGPL solo se carga al crear el detector y se elimina en A-16 (D8).
    from ultralytics import YOLO

    return DetectorUltralytics(YOLO(ruta_modelo), CATALOGO_COCO, confianza_minima)
