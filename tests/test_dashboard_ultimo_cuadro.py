"""El monitoreo guarda el último cuadro de la cámara para dibujar zonas sobre él (SPEC/9 §8.3).

Integración con Tk real (el gate corre bajo xvfb); sin cámaras: los cuadros se encolan a mano.
"""

import queue
from collections.abc import Iterator

import customtkinter as ctk
import numpy as np
import pytest

from src.gui.dashboard import DashboardFrame

pytestmark = pytest.mark.integration


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


def _cuadro(valor: int) -> np.ndarray:
    return np.full((4, 6, 3), valor, dtype=np.uint8)


def test_antes_del_primer_cuadro_no_hay_imagen(raiz: ctk.CTk) -> None:
    tablero = DashboardFrame(raiz, {})

    assert tablero.ultimo_cuadro() is None


def test_guarda_el_cuadro_mas_reciente_de_la_camara(raiz: ctk.CTk) -> None:
    cola: queue.Queue[tuple[str, np.ndarray]] = queue.Queue()
    tablero = DashboardFrame(raiz, {"Cámara Local": cola})
    cola.put(("Cámara Local", _cuadro(1)))
    cola.put(("Cámara Local", _cuadro(2)))

    tablero.update_frames()

    cuadro = tablero.ultimo_cuadro()
    assert cuadro is not None
    assert np.array_equal(cuadro, _cuadro(2))


def test_el_cuadro_entregado_es_una_copia(raiz: ctk.CTk) -> None:
    cola: queue.Queue[tuple[str, np.ndarray]] = queue.Queue()
    tablero = DashboardFrame(raiz, {"Cámara Local": cola})
    cola.put(("Cámara Local", _cuadro(2)))
    tablero.update_frames()

    entregado = tablero.ultimo_cuadro()
    assert entregado is not None
    entregado[:] = 0

    assert np.array_equal(tablero.ultimo_cuadro(), _cuadro(2))
