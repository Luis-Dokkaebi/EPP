# src/tracking/person_tracker.py

from collections.abc import Sequence

import numpy as np
import supervision as sv

from src.inference.types import ClaseObjeto, Deteccion

_ORDINALES = {clase: ordinal for ordinal, clase in enumerate(ClaseObjeto)}


class PersonTracker:
    def __init__(self):
        self.tracker = sv.ByteTrack()

    def update(self, detections):
        # Recibe detecciones en formato de supervision (ya las adaptaremos desde YOLO)
        tracked_detections = self.tracker.update_with_detections(detections)
        return tracked_detections


def separar_personas_y_celulares(
    detecciones: Sequence[Deteccion],
) -> tuple[sv.Detections, list[tuple[int, int, int, int]]]:
    """Personas en el formato de ByteTrack y celulares como rectángulos de enteros."""
    personas = [d for d in detecciones if d.clase is ClaseObjeto.PERSONA]
    celulares = [_rectangulo(d) for d in detecciones if d.clase is ClaseObjeto.CELULAR]
    return _a_supervision(personas), celulares


def _a_supervision(detecciones: Sequence[Deteccion]) -> sv.Detections:
    cajas = [(d.caja.x1, d.caja.y1, d.caja.x2, d.caja.y2) for d in detecciones]
    return sv.Detections(
        xyxy=np.asarray(cajas, dtype=np.float32).reshape(len(cajas), 4),
        confidence=np.asarray([d.confianza for d in detecciones], dtype=np.float32),
        # El ordinal de la clase semántica, no un ID de COCO: ByteTrack solo lo transporta.
        class_id=np.asarray([_ORDINALES[d.clase] for d in detecciones], dtype=int),
    )


def _rectangulo(deteccion: Deteccion) -> tuple[int, int, int, int]:
    caja = deteccion.caja
    return int(caja.x1), int(caja.y1), int(caja.x2), int(caja.y2)
