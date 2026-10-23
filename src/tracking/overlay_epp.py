"""Overlay de cumplimiento de EPP sobre el video (SPEC/9 §8.1).

Caja de la persona en verde si cumple, rojo si tiene una infracción y gris si algo exigido no se
puede verificar, con una etiqueta por elemento exigido dentro de la caja. Se activa o desactiva
llamándolo o no: la decisión es de la interfaz. Vive en la capa de adaptadores porque usa cv2.
"""

from collections.abc import Iterable

import cv2
import numpy as np

from src.ppe.application.vista_cumplimiento import SituacionVisual, VistaPersona
from src.ppe.domain.geometria import Caja

COLORES = {
    SituacionVisual.CUMPLE: (0, 255, 0),
    SituacionVisual.INFRACCION: (0, 0, 255),
    SituacionVisual.NO_VERIFICABLE: (128, 128, 128),
}
GROSOR_CAJA = 2
ESCALA_TEXTO = 0.5
GROSOR_TEXTO = 1
MARGEN = 4
INTERLINEA = 18


def dibujar_cumplimiento(
    frame: np.ndarray, personas: Iterable[tuple[Caja, VistaPersona]]
) -> np.ndarray:
    """Copia del frame con cada persona marcada; el frame original no se modifica."""
    dibujado = frame.copy()
    for caja, vista in personas:
        _dibujar(dibujado, caja, vista)
    return dibujado


def _dibujar(frame: np.ndarray, caja: Caja, vista: VistaPersona) -> None:
    color = COLORES[vista.situacion]
    esquina = (round(caja.x1), round(caja.y1))
    cv2.rectangle(frame, esquina, (round(caja.x2), round(caja.y2)), color, GROSOR_CAJA)
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    for numero, etiqueta in enumerate(vista.etiquetas, start=1):
        origen = (esquina[0] + MARGEN, esquina[1] + numero * INTERLINEA)
        cv2.putText(frame, etiqueta, origen, fuente, ESCALA_TEXTO, color, GROSOR_TEXTO)
