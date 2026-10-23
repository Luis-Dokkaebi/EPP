"""Raíz de composición única (SPEC/9 §1.3.6): GUI y headless crean el detector del mismo modo."""

import sys
import types

import numpy as np
import pytest

from src.composition import crear_detector
from src.inference.types import Caja, ClaseObjeto, Deteccion
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

ID_PERSONA = 0


@pytest.fixture
def modelos_cargados(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModeloFalso]:
    """Reemplaza el paquete `ultralytics`: la prueba no carga pesos reales (CLAUDE.md §16)."""
    cargados: dict[str, ModeloFalso] = {}

    def yolo(ruta: str) -> ModeloFalso:
        cargados[ruta] = ModeloFalso([DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0), 0.5)])
        return cargados[ruta]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=yolo))
    return cargados


def test_crear_detector_carga_el_modelo_de_la_ruta_indicada(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    crear_detector("modelos/personas.pt", confianza_minima=0.0)

    assert list(modelos_cargados) == ["modelos/personas.pt"]


def test_crear_detector_devuelve_un_puerto_con_clases_semanticas(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.0)

    detecciones = detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8))

    assert detecciones == [Deteccion(ClaseObjeto.PERSONA, 0.5, Caja(1.0, 2.0, 3.0, 4.0))]


def test_crear_detector_aplica_la_confianza_minima(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.6)

    assert detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8)) == []
