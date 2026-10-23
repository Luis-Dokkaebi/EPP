"""Caracterización de enumerate_cameras con capturas falsas (sin cámaras reales, CLAUDE.md §16).

Su cobertura venía de un cv2 falso que otras pruebas dejaban en sys.modules; se reemplaza por
dobles explícitos de cv2.VideoCapture.
"""

from collections.abc import Callable

import numpy as np
import pytest

from src.acquisition import camera_enumerator
from src.acquisition.camera_enumerator import enumerate_cameras

ANCHO, ALTO = 640, 480
FRAME = np.zeros((2, 2, 3), dtype=np.uint8)
SEGUNDOS_MAXIMOS = 5.0


class CapturaFalsa:
    def __init__(self, abierta: bool = True, lectura: object = (True, FRAME)) -> None:
        self._abierta = abierta
        self._lectura = lectura
        self.liberada = False

    def isOpened(self) -> bool:  # noqa: N802 - API de OpenCV
        return self._abierta

    def get(self, propiedad: int) -> float:
        return {camera_enumerator.cv2.CAP_PROP_FRAME_WIDTH: ANCHO}.get(propiedad, ALTO)

    def getBackendName(self) -> str:  # noqa: N802 - API de OpenCV
        return "DSHOW"

    def read(self) -> object:
        if isinstance(self._lectura, Exception):
            raise self._lectura
        return self._lectura

    def release(self) -> None:
        self.liberada = True


def _con_capturas(
    monkeypatch: pytest.MonkeyPatch, fabrica: Callable[..., CapturaFalsa]
) -> list[tuple[object, ...]]:
    llamadas: list[tuple[object, ...]] = []

    def video_capture(*argumentos: object) -> CapturaFalsa:
        llamadas.append(argumentos)
        return fabrica(*argumentos)

    monkeypatch.setattr(camera_enumerator.cv2, "VideoCapture", video_capture)
    return llamadas


def test_enumera_la_camara_que_entrega_un_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_capturas(monkeypatch, lambda indice, *_: CapturaFalsa(abierta=indice == 1))

    assert enumerate_cameras(max_index=3) == [
        {"index": 1, "name": "Cámara 1", "width": ANCHO, "height": ALTO, "backend": "DSHOW",
         "label": "Cámara 1 (640x480, DSHOW)"}
    ]  # fmt: skip


@pytest.mark.parametrize(
    "lectura", [(False, None), (True, None), (True, np.zeros((0,))), ValueError("sin frame")],
    ids=["lectura-fallida", "frame-nulo", "frame-vacio", "excepcion"],
)  # fmt: skip
def test_descarta_la_camara_que_no_entrega_un_frame_util(
    monkeypatch: pytest.MonkeyPatch, lectura: object
) -> None:
    capturas: list[CapturaFalsa] = []
    _con_capturas(
        monkeypatch, lambda *_: capturas.append(CapturaFalsa(lectura=lectura)) or capturas[-1]
    )

    assert enumerate_cameras(max_index=1) == []
    assert all(captura.liberada for captura in capturas)


def test_sin_directshow_reintenta_con_el_backend_por_omision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = _con_capturas(monkeypatch, lambda *argumentos: CapturaFalsa(len(argumentos) == 1))

    camaras = enumerate_cameras(max_index=2)

    assert [camara["index"] for camara in camaras] == [0, 1]
    assert llamadas == [(0, camera_enumerator.cv2.CAP_DSHOW), (1, camera_enumerator.cv2.CAP_DSHOW),
                        (0,), (1,)]  # fmt: skip


def test_una_captura_que_falla_al_abrir_no_detiene_el_escaneo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fabrica(indice: int, *_: object) -> CapturaFalsa:
        if indice == 0:
            raise RuntimeError("driver roto")
        return CapturaFalsa()

    _con_capturas(monkeypatch, fabrica)

    assert [camara["index"] for camara in enumerate_cameras(max_index=2)] == [1]


def test_el_reintento_sin_directshow_tambien_descarta_y_tolera_fallos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fabrica(indice: int, *backend: object) -> CapturaFalsa:
        if not backend and indice == 0:
            raise RuntimeError("driver roto")
        return CapturaFalsa(abierta=False)

    _con_capturas(monkeypatch, fabrica)

    assert enumerate_cameras(max_index=2) == []


def test_el_escaneo_asincrono_entrega_las_camaras_al_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _con_capturas(monkeypatch, lambda *_: CapturaFalsa(abierta=False))
    recibidas: list[list[dict[str, object]]] = []

    hilo = camera_enumerator.enumerate_cameras_async(recibidas.append, max_index=1)
    hilo.join(timeout=SEGUNDOS_MAXIMOS)

    assert recibidas == [[]]
    assert hilo.daemon is True
