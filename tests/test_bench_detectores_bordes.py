"""Bordes del benchmark de motores (SPEC/9 §1.5): umbrales, IoU y percentiles."""

import dataclasses
import types

import numpy as np
import pytest

from src.inference.types import Caja, ClaseObjeto, Deteccion
from tools.bench_detectores import (
    Medicion,
    emparejar,
    evaluar_puerta,
    iou,
    medir_variante,
    percentil,
)

FRAME = np.zeros((4, 4, 3), dtype=np.uint8)
PERSONA = Caja(0, 5, 10, 15)


def _medicion(fps: float = 10.0, p95: float = 100.0, recall: float = 0.9) -> Medicion:
    return Medicion("v", fps, 50.0, p95, 300.0, recall, 0.8)


def test_percentil_95_de_doscientos_valores_es_el_valor_190() -> None:
    assert percentil([float(valor) for valor in range(1, 201)], 95) == 190.0  # noqa: PLR2004


@pytest.mark.parametrize(
    ("otra", "esperado"),
    [(Caja(20, 5, 30, 15), 0.0), (Caja(0, 20, 10, 30), 0.0), (Caja(0, 10, 10, 20), 1 / 3)],
    ids=["solapa-solo-en-y", "solapa-solo-en-x", "mitad-vertical"],
)
def test_iou_con_coordenadas_no_nulas(otra: Caja, esperado: float) -> None:
    assert iou(PERSONA, otra) == pytest.approx(esperado)


def test_emparejar_resuelve_conflictos_dando_prioridad_al_par_de_mayor_iou() -> None:
    """Greedy por IoU descendente, como la evaluación estándar: el par más parecido gana."""
    reales = [Caja(0, 0, 10, 10), Caja(4, 0, 14, 10)]
    predichas = [Caja(1, 0, 11, 10), Caja(-3, 0, 7, 10)]  # IoU: 0.82 y 0.54 con la primera real

    assert emparejar(predichas, reales) == 1


def test_medir_variante_usa_el_tiempo_transcurrido_y_el_p95_de_veinte_frames() -> None:
    persona = [Deteccion(ClaseObjeto.PERSONA, 0.9, PERSONA)]
    marcas = iter([100.0, *(m for i in range(1, 21) for m in (100.0, 100.0 + i / 1000)), 102.0])
    detector = types.SimpleNamespace(detectar=lambda _frame: persona)

    medicion = medir_variante(
        "v", detector, [(FRAME, [PERSONA])] * 20, reloj=lambda: next(marcas), memoria_mb=lambda: 0.0
    )

    assert medicion.fps == pytest.approx(10.0)
    assert medicion.latencia_p95_ms == pytest.approx(19.0)


@pytest.mark.parametrize(
    ("frames", "mensaje"),
    [([], "Benchmark sin frames etiquetados."),
     ([(FRAME, [])], "Benchmark sin personas etiquetadas: el recall no está definido.")],
    ids=["sin-frames", "sin-personas"],
)  # fmt: skip
def test_medir_variante_explica_por_que_no_puede_medir(frames: list, mensaje: str) -> None:
    detector = types.SimpleNamespace(detectar=lambda _frame: [])

    with pytest.raises(ValueError) as error:
        medir_variante("v", detector, frames, reloj=lambda: 0.0, memoria_mb=lambda: 0.0)

    assert str(error.value) == mensaje


def test_percentil_explica_que_no_hay_valores() -> None:
    with pytest.raises(ValueError) as error:
        percentil([], 50)

    assert str(error.value) == "Percentil sin valores medidos."


def test_la_medicion_es_inmutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _medicion().fps = 1.0  # type: ignore[misc]  # se verifica que no se pueda asignar


def test_puerta_acepta_valores_iguales_al_umbral() -> None:
    umbrales = {"fps": ("min", 10.0), "latencia_p95_ms": ("max", 100.0)}

    assert evaluar_puerta(_medicion(), _medicion(), umbrales) == []
