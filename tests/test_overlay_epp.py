"""Overlay de cumplimiento de EPP sobre el video (SPEC/9 §8.1)."""

import hashlib

import numpy as np
import pytest

from src.ppe.application.vista_cumplimiento import SituacionVisual, VistaPersona
from src.ppe.domain.geometria import Caja
from src.tracking.overlay_epp import dibujar_cumplimiento

CAJA = Caja(40.0, 30.0, 200.0, 220.0)
NEGRO = [0, 0, 0]
ALTO_DE_UNA_LINEA = 16
# sha256 del overlay de _dos_personas() con opencv-python-headless 4.9.0.80 (fijado): fija
# colores, grosores, fuente, escala, interlineado y margen de las etiquetas. Si cambia el dibujo
# a propósito, revisa la imagen y actualiza el valor.
# pragma: allowlist nextline secret
HUELLA_OVERLAY = "381c3b7f0d38275b9459fea80a484d0a9e1139623b434243f5426311de3340a1"


def _frame() -> np.ndarray:
    return np.zeros((240, 320, 3), dtype=np.uint8)


@pytest.mark.parametrize(
    ("situacion", "color"),
    [
        (SituacionVisual.CUMPLE, [0, 255, 0]),
        (SituacionVisual.INFRACCION, [0, 0, 255]),
        (SituacionVisual.NO_VERIFICABLE, [128, 128, 128]),
    ],
    ids=["verde", "rojo", "gris"],
)
def test_overlay_pinta_la_caja_con_el_color_de_la_situacion(
    situacion: SituacionVisual, color: list[int]
) -> None:
    frame = _frame()

    dibujado = dibujar_cumplimiento(frame, [(CAJA, VistaPersona(situacion, ()))])

    bordes = [dibujado[120, 40].tolist(), dibujado[220, 120].tolist(), dibujado[30, 200].tolist()]
    assert bordes == [color] * 3
    assert dibujado[120, 120].tolist() == NEGRO
    assert frame.max() == 0


def test_overlay_escribe_las_etiquetas_dentro_de_la_caja_una_debajo_de_otra() -> None:
    vista = VistaPersona(SituacionVisual.INFRACCION, ("Sin casco", "Chaleco"))

    dibujado = dibujar_cumplimiento(_frame(), [(CAJA, vista)])

    filas_con_texto = np.flatnonzero(dibujado[32:100, 42:198].any(axis=(1, 2)))
    assert filas_con_texto.size > 0
    assert filas_con_texto.max() - filas_con_texto.min() > ALTO_DE_UNA_LINEA


def test_overlay_sin_personas_devuelve_una_copia_igual() -> None:
    frame = _frame()

    dibujado = dibujar_cumplimiento(frame, [])

    assert dibujado is not frame
    assert np.array_equal(dibujado, frame)


def _dos_personas() -> np.ndarray:
    return dibujar_cumplimiento(
        _frame(),
        [
            (Caja(10.0, 10.0, 150.0, 200.0), VistaPersona(SituacionVisual.CUMPLE, ("Casco",))),
            (
                Caja(170.0, 20.0, 310.0, 230.0),
                VistaPersona(SituacionVisual.NO_VERIFICABLE, ("Casco ?", "Chaleco")),
            ),
        ],
    )


def test_overlay_dibuja_exactamente_lo_fijado() -> None:
    huella = hashlib.sha256(_dos_personas().tobytes()).hexdigest()

    assert huella == HUELLA_OVERLAY
