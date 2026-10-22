"""Evidencia anotada de las infracciones de EPP (SPEC/9 §6.2, C-08; AC-015)."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.tracking import evidencias_epp
from src.tracking.evidencias_epp import (
    AlmacenEvidenciasCv2,
    EvidenciaNoGuardadaError,
    anotar_evidencia,
)

ROJO = [0, 0, 255]
# sha256 de la evidencia anotada de CAJA con opencv-python-headless 4.9.0.80 (fijado): fija color,
# grosores, fuente, escala, texto y posición del rótulo. Si cambia el dibujo a propósito, revisa la
# imagen y actualiza el valor.
# pragma: allowlist nextline secret
HUELLA_EVIDENCIA = "b23a414c594805e2b7f6e91bced88a61f80381d84010ded07566a60f32c91e87"
NEGRO = [0, 0, 0]
CAJA = Caja(40.0, 60.0, 140.0, 180.0)
INICIO = datetime(2026, 10, 22, 8, 5, 30, 123456, tzinfo=UTC)
INFRACCION = InfraccionIniciada(
    Incumplimiento(7, "Ana", ElementoEPP.CASCO, "Boca de pozo"), INICIO, "epp-0.1.0", None
)


def _frame() -> np.ndarray:
    return np.zeros((240, 320, 3), dtype=np.uint8)


def test_anotar_evidencia_marca_a_la_persona_en_rojo_sin_tocar_el_original() -> None:
    frame = _frame()

    anotada = anotar_evidencia(frame, CAJA, ElementoEPP.CASCO)

    bordes = [anotada[120, 40].tolist(), anotada[120, 140].tolist(), anotada[60, 90].tolist()]
    assert (bordes, anotada[120, 90].tolist(), frame.max()) == ([ROJO] * 3, NEGRO, 0)


def test_anotar_evidencia_rotula_el_elemento_faltante_sobre_la_caja() -> None:
    anotada = anotar_evidencia(_frame(), CAJA, ElementoEPP.CASCO)

    assert (anotada[40:56, 40:140].any(), anotada[0:35, :].any()) == (True, False)


def test_anotar_evidencia_usa_bordes_gruesos_centrados_en_la_coordenada() -> None:
    # Grosor 3 de OpenCV 4.9 (fijado): 5 píxeles, de x=38 a x=42 para un borde en x=40.
    anotada = anotar_evidencia(_frame(), CAJA, ElementoEPP.CASCO)

    assert anotada[120, 36:45, 2].tolist() == [0, 0, 255, 255, 255, 255, 255, 0, 0]


def test_almacen_guarda_la_evidencia_por_fecha_sin_el_nombre_del_empleado(tmp_path: Path) -> None:
    ruta = AlmacenEvidenciasCv2(tmp_path).guardar_evidencia(_frame(), CAJA, INFRACCION)

    esperada = tmp_path / "epp" / "2026-10-22" / "080530_123456_t7_casco.jpg"
    leida = cv2.imread(ruta)
    assert (ruta, leida.shape, "Ana" in ruta) == (str(esperada), (240, 320, 3), False)


def test_almacen_falla_si_no_puede_escribir_la_imagen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evidencias_epp.cv2, "imwrite", lambda _ruta, _imagen: False)

    with pytest.raises(
        EvidenciaNoGuardadaError, match=r"^No se pudo guardar la evidencia en .+\.jpg$"
    ):
        AlmacenEvidenciasCv2(tmp_path).guardar_evidencia(_frame(), CAJA, INFRACCION)


def test_almacen_rechaza_una_imagen_que_no_es_un_frame(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match=r"^La evidencia necesita un frame numpy; llegó str$"):
        AlmacenEvidenciasCv2(tmp_path).guardar_evidencia("frame-3", CAJA, INFRACCION)


def test_anotar_evidencia_produce_exactamente_la_imagen_de_referencia() -> None:
    anotada = anotar_evidencia(_frame(), CAJA, ElementoEPP.CASCO)

    assert hashlib.sha256(anotada.tobytes()).hexdigest() == HUELLA_EVIDENCIA


def test_almacen_guarda_dos_evidencias_del_mismo_dia(tmp_path: Path) -> None:
    almacen = AlmacenEvidenciasCv2(tmp_path)
    siguiente = InfraccionIniciada(
        INFRACCION.incumplimiento, INICIO + timedelta(minutes=1), "epp-0.1.0", None
    )

    rutas = [almacen.guardar_evidencia(_frame(), CAJA, i) for i in (INFRACCION, siguiente)]

    assert [Path(ruta).exists() for ruta in rutas] == [True, True]
