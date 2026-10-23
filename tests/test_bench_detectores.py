"""Métricas y puerta de promoción del benchmark de motores (SPEC/9 §1.5, A-13)."""

from collections.abc import Iterator

import numpy as np
import pytest

from src.inference.types import Caja, ClaseObjeto, Deteccion
from tools.bench_detectores import (
    UMBRALES_DE_PROMOCION,
    Medicion,
    emparejar,
    evaluar_puerta,
    fila_bitacora,
    iou,
    medir_variante,
    percentil,
)

PERSONA = Caja(0, 0, 10, 10)
FRAME = np.zeros((4, 4, 3), dtype=np.uint8)


def _medicion(
    nombre: str = "v", fps: float = 12.0, p95: float = 80.0, recall: float = 0.9
) -> Medicion:
    return Medicion(nombre, fps, 50.0, p95, 300.0, recall, 0.8)


class DetectorFijo:
    def __init__(self, *respuestas: list[Deteccion]) -> None:
        self._respuestas = iter(respuestas)

    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        return next(self._respuestas)


def _reloj(*marcas: float) -> Iterator[float]:
    return iter(marcas)


@pytest.mark.parametrize(
    ("valores", "p", "esperado"),
    [([5.0], 95, 5.0), ([1.0, 2.0, 3.0, 4.0], 50, 2.0), ([4.0, 1.0, 3.0, 2.0], 95, 4.0)],
)
def test_percentil_usa_el_rango_mas_cercano(valores: list[float], p: int, esperado: float) -> None:
    assert percentil(valores, p) == esperado


def test_percentil_de_una_lista_vacia_falla() -> None:
    with pytest.raises(ValueError, match="sin valores"):
        percentil([], 50)


@pytest.mark.parametrize(
    ("otra", "esperado"),
    [(Caja(0, 0, 10, 10), 1.0), (Caja(5, 0, 15, 10), 1 / 3), (Caja(20, 20, 30, 30), 0.0)],
    ids=["identica", "mitad", "disjunta"],
)
def test_iou_entre_cajas(otra: Caja, esperado: float) -> None:
    assert iou(PERSONA, otra) == pytest.approx(esperado)


def test_emparejar_cuenta_cada_caja_real_una_sola_vez() -> None:
    predichas = [Caja(0, 0, 10, 10), Caja(1, 0, 11, 10), Caja(50, 50, 60, 60)]

    assert emparejar(predichas, [PERSONA]) == 1


def test_emparejar_exige_iou_de_al_menos_un_medio() -> None:
    assert emparejar([Caja(5, 0, 15, 10)], [PERSONA]) == 0
    assert emparejar([Caja(0, 0, 10, 20)], [PERSONA]) == 1


def test_medir_variante_calcula_fps_latencias_recall_y_precision() -> None:
    persona = Deteccion(ClaseObjeto.PERSONA, 0.9, PERSONA)
    celular = Deteccion(ClaseObjeto.CELULAR, 0.9, Caja(50, 50, 60, 60))
    falsa = Deteccion(ClaseObjeto.PERSONA, 0.9, Caja(80, 80, 90, 90))
    detector = DetectorFijo([persona, celular], [falsa])
    reloj = _reloj(0.0, 0.0, 0.1, 0.1, 0.3, 0.5)

    medicion = medir_variante(
        "rfdetr",
        detector,
        [(FRAME, [PERSONA]), (FRAME, [PERSONA])],
        reloj=lambda: next(reloj),
        memoria_mb=lambda: 256.0,
    )

    assert medicion == Medicion(
        nombre="rfdetr",
        fps=4.0,
        latencia_p50_ms=pytest.approx(100.0),
        latencia_p95_ms=pytest.approx(200.0),
        ram_mb=256.0,
        recall=0.5,
        precision=0.5,
    )


def test_medir_variante_sin_frames_etiquetados_falla() -> None:
    with pytest.raises(ValueError, match="sin frames etiquetados"):
        medir_variante("v", DetectorFijo(), [], reloj=lambda: 0.0, memoria_mb=lambda: 0.0)


def test_medir_variante_sin_personas_etiquetadas_falla() -> None:
    reloj = _reloj(0.0, 0.0, 1.0, 1.0)

    with pytest.raises(ValueError, match="sin personas etiquetadas"):
        medir_variante(
            "v", DetectorFijo([]), [(FRAME, [])], reloj=lambda: next(reloj), memoria_mb=lambda: 0.0
        )


def test_medir_variante_sin_predicciones_tiene_precision_cero() -> None:
    reloj = _reloj(0.0, 0.0, 1.0, 1.0)

    medicion = medir_variante(
        "v",
        DetectorFijo([]),
        [(FRAME, [PERSONA])],
        reloj=lambda: next(reloj),
        memoria_mb=lambda: 0.0,
    )

    assert (medicion.recall, medicion.precision) == (0.0, 0.0)


def test_puerta_falla_cerrada_mientras_d2_no_fija_los_umbrales() -> None:
    razones = evaluar_puerta(_medicion(), baseline=_medicion("baseline"))

    assert razones == [
        "fps: umbral sin definir (decisión D2)",
        "latencia_p95_ms: umbral sin definir (decisión D2)",
    ]


def test_puerta_pasa_con_umbrales_cumplidos_y_recall_no_peor_que_el_baseline() -> None:
    umbrales = {"fps": ("min", 10.0), "latencia_p95_ms": ("max", 100.0)}

    assert evaluar_puerta(_medicion(recall=0.9), _medicion("baseline", recall=0.9), umbrales) == []


def test_puerta_falla_por_cada_umbral_incumplido_y_por_peor_recall() -> None:
    umbrales = {"fps": ("min", 15.0), "latencia_p95_ms": ("max", 50.0)}

    razones = evaluar_puerta(_medicion(recall=0.8), _medicion("baseline", recall=0.9), umbrales)

    assert razones == [
        "fps: 12.0 < 15.0",
        "latencia_p95_ms: 80.0 > 50.0",
        "recall de persona 0.800 < baseline 0.900",
    ]


def test_puerta_sin_baseline_no_puede_aprobar() -> None:
    umbrales = {"fps": ("min", 10.0)}

    assert evaluar_puerta(_medicion(), None, umbrales) == ["sin baseline para comparar el recall"]


def test_los_umbrales_de_promocion_no_tienen_valores_inventados() -> None:
    assert UMBRALES_DE_PROMOCION == {"fps": ("min", None), "latencia_p95_ms": ("max", None)}


def test_fila_bitacora_sigue_el_formato_de_la_bitacora() -> None:
    fila = fila_bitacora(_medicion("rfdetr-nano-onnx"), "más preciso", "i5 CPU", "no")

    assert fila == (
        "rfdetr-nano-onnx | más preciso | i5 CPU | 12.0 | 80 | 300 | 0.900 | no | "
        "precisión 0.800"
    )
