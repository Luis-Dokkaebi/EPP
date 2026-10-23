"""Caracterización del modo headless (`src/main.py`) antes de migrar el motor (SPEC/9 §1.3.5).

Mismo criterio que las pruebas de CameraWorker: la fixture cambia de motor, las aserciones no.
"""

import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from config.path_utils import ConfigManager
from src import main
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

CLASE_PERSONA = 0
CLASE_CELULAR = 67
UMBRAL = 0.4
MARCA_TIEMPO = 2_000.0


class CapturaFalsa:
    def __init__(self, frames: list[np.ndarray]) -> None:
        self._frames = frames
        self.liberada = False

    def isOpened(self) -> bool:  # noqa: N802 - interfaz de cv2.VideoCapture
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.liberada = True


@dataclass
class PipelineFalso:
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)

    def __init__(self, **_colaboradores: Any) -> None:
        self.llamadas = []

    def process(self, *argumentos: Any) -> list[dict[str, Any]]:
        self.llamadas.append(argumentos)
        return []


@dataclass
class Corrida:
    pipelines: list[PipelineFalso]
    capturas: list[CapturaFalsa]
    ventanas_cerradas: list[bool]

    def llamadas(self) -> list[tuple[Any, ...]]:
        [pipeline] = self.pipelines
        return pipeline.llamadas


@pytest.fixture
def correr_headless(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[..., Corrida]:
    def _correr(frames: list[np.ndarray], detecciones: list[DeteccionCruda]) -> Corrida:
        modelo = ModeloFalso(detecciones)
        # Paquete `ultralytics` falso: la prueba no importa el motor real ni carga pesos.
        monkeypatch.setitem(
            sys.modules, "ultralytics", types.SimpleNamespace(YOLO=lambda _r: modelo)
        )
        corrida = Corrida(pipelines=[], capturas=[], ventanas_cerradas=[])
        _aislar_entorno(monkeypatch, tmp_path)
        monkeypatch.setattr(main.time, "time", lambda: MARCA_TIEMPO)
        monkeypatch.setattr(main.cv2, "VideoCapture", _fabrica(corrida.capturas, frames))
        monkeypatch.setattr(main.cv2, "imshow", lambda *_argumentos: None)
        monkeypatch.setattr(main.cv2, "waitKey", lambda _ms: 0)
        monkeypatch.setattr(
            main.cv2, "destroyAllWindows", lambda: corrida.ventanas_cerradas.append(True)
        )
        monkeypatch.setattr(
            "src.tracking.tracking_pipeline.TrackingPipeline",
            lambda **colaboradores: _registrar(corrida.pipelines, PipelineFalso(**colaboradores)),
        )
        main.start_video_stream()
        return corrida

    return _correr


def _aislar_entorno(monkeypatch: pytest.MonkeyPatch, carpeta: Path) -> None:
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Prueba_Headless")
    monkeypatch.setenv("SELECTED_CAMERA_INDEX", "0")
    monkeypatch.setattr(main.config, "get_zonas_file", lambda: str(carpeta / "zonas.json"))
    monkeypatch.setattr(main.config, "get_snapshots_dir", lambda: str(carpeta / "capturas"))
    monkeypatch.setattr(main.config, "get_db_path", lambda: str(carpeta / "bd.sqlite"))
    monkeypatch.setattr(main.config, "CONFIDENCE_THRESHOLD", UMBRAL)
    monkeypatch.setattr(main, "DatabaseManager", lambda db_path: object())
    monkeypatch.setattr(main, "FaceRecognizer", lambda: object())
    monkeypatch.setattr(main, "StateManager", lambda _bd: object())


def _fabrica(capturas: list[CapturaFalsa], frames: list[np.ndarray]) -> Callable[..., Any]:
    def _abrir(_fuente: object) -> CapturaFalsa:
        captura = CapturaFalsa([np.zeros((4, 4, 3), dtype=np.uint8), *frames])
        capturas.append(captura)
        return captura

    return _abrir


def _registrar(pipelines: list[PipelineFalso], pipeline: PipelineFalso) -> PipelineFalso:
    pipelines.append(pipeline)
    return pipeline


def test_headless_procesa_cada_frame_leido_despues_del_frame_de_prueba(
    correr_headless: Callable[..., Corrida],
) -> None:
    frames = [np.full((4, 4, 3), valor, dtype=np.uint8) for valor in (1, 2)]

    corrida = correr_headless(frames=list(frames), detecciones=[])

    assert [llamada[0] for llamada in corrida.llamadas()] == frames
    assert [llamada[3] for llamada in corrida.llamadas()] == [MARCA_TIEMPO] * 2


def test_headless_entrega_personas_y_celulares_por_encima_del_umbral(
    correr_headless: Callable[..., Corrida],
) -> None:
    detecciones = [
        DeteccionCruda(CLASE_PERSONA, (10.0, 20.0, 110.0, 220.0), 0.9),
        DeteccionCruda(CLASE_PERSONA, (1.0, 1.0, 2.0, 2.0), 0.3),
        DeteccionCruda(CLASE_CELULAR, (5.7, 6.2, 30.9, 40.1), 0.8),
        DeteccionCruda(CLASE_CELULAR, (7.0, 7.0, 9.0, 9.0), 0.1),
    ]

    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=detecciones)

    [(_, personas, celulares, _)] = corrida.llamadas()
    assert personas.xyxy.tolist() == [[10.0, 20.0, 110.0, 220.0]]
    assert celulares == [(5, 6, 30, 40)]


def test_headless_libera_la_camara_y_cierra_las_ventanas_al_terminar(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[], detecciones=[])

    assert [captura.liberada for captura in corrida.capturas] == [True]
    assert corrida.ventanas_cerradas == [True]
