"""Buzón que lleva al hilo de la interfaz lo que piden los hilos de trabajo.

Regresión de la prueba de humo del 24/10/2026: «Exportar Excel» cerraba la aplicación porque el
aviso de fin se dibujaba desde el hilo de la exportación.
"""

import threading
from collections.abc import Callable

import pytest

from src.gui.buzon_hilo_ui import BuzonHiloUI

INTERVALO_MS = 50
DOS_PUBLICADAS = 2


class ProgramadorFalso:
    """Reemplaza a `widget.after`: anota cada pedido y no ejecuta nada."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[int, Callable[[], None]]] = []

    def __call__(self, demora_ms: int, accion: Callable[[], None]) -> str:
        self.pedidos.append((demora_ms, accion))
        return f"after#{len(self.pedidos)}"


@pytest.fixture
def programador() -> ProgramadorFalso:
    return ProgramadorFalso()


@pytest.fixture
def buzon(programador: ProgramadorFalso) -> BuzonHiloUI:
    return BuzonHiloUI(programador, INTERVALO_MS)


def test_publicar_no_ejecuta_la_accion(buzon: BuzonHiloUI) -> None:
    hechas: list[str] = []

    buzon.publicar(lambda: hechas.append("aviso"))

    assert hechas == []


def test_atender_ejecuta_las_acciones_pendientes_en_orden(buzon: BuzonHiloUI) -> None:
    hechas: list[str] = []
    buzon.publicar(lambda: hechas.append("primera"))
    buzon.publicar(lambda: hechas.append("segunda"))

    buzon.atender()

    assert hechas == ["primera", "segunda"]


def test_atender_ejecuta_cada_accion_una_sola_vez(buzon: BuzonHiloUI) -> None:
    hechas: list[str] = []
    buzon.publicar(lambda: hechas.append("aviso"))
    buzon.atender()

    buzon.atender()

    assert hechas == ["aviso"]


def test_atender_sin_pendientes_no_hace_nada(buzon: BuzonHiloUI) -> None:
    buzon.atender()

    assert buzon.pendientes() == 0


def test_lo_publicado_desde_otro_hilo_corre_en_el_hilo_que_atiende(buzon: BuzonHiloUI) -> None:
    hilos: list[threading.Thread] = []
    trabajador = threading.Thread(
        target=buzon.publicar, args=(lambda: hilos.append(threading.current_thread()),)
    )
    trabajador.start()
    trabajador.join()

    buzon.atender()

    assert hilos == [threading.current_thread()]


def test_pendientes_cuenta_lo_publicado_sin_atender(buzon: BuzonHiloUI) -> None:
    buzon.publicar(lambda: None)
    buzon.publicar(lambda: None)

    assert buzon.pendientes() == DOS_PUBLICADAS


def test_vigilar_atiende_y_se_vuelve_a_programar(
    buzon: BuzonHiloUI, programador: ProgramadorFalso
) -> None:
    hechas: list[str] = []
    buzon.publicar(lambda: hechas.append("aviso"))

    buzon.vigilar()

    assert hechas == ["aviso"]
    assert programador.pedidos == [(INTERVALO_MS, buzon.vigilar)]


def test_vigilar_sigue_programado_aunque_una_accion_falle(
    buzon: BuzonHiloUI, programador: ProgramadorFalso
) -> None:
    def falla() -> None:
        raise RuntimeError("widget destruido")

    buzon.publicar(falla)

    with pytest.raises(RuntimeError, match="widget destruido"):
        buzon.vigilar()

    assert programador.pedidos == [(INTERVALO_MS, buzon.vigilar)]


def test_una_accion_que_falla_no_descarta_las_siguientes(buzon: BuzonHiloUI) -> None:
    hechas: list[str] = []

    def falla() -> None:
        raise RuntimeError("falló")

    buzon.publicar(falla)
    buzon.publicar(lambda: hechas.append("siguiente"))
    with pytest.raises(RuntimeError):
        buzon.atender()

    buzon.atender()

    assert hechas == ["siguiente"]


@pytest.mark.parametrize("intervalo_ms", [0, -1], ids=["cero", "negativo"])
def test_intervalo_que_no_es_positivo_es_invalido(
    programador: ProgramadorFalso, intervalo_ms: int
) -> None:
    mensaje = rf"^El intervalo debe ser positivo: {intervalo_ms} ms\.$"

    with pytest.raises(ValueError, match=mensaje):
        BuzonHiloUI(programador, intervalo_ms)


def test_intervalo_de_un_milisegundo_es_valido(programador: ProgramadorFalso) -> None:
    buzon = BuzonHiloUI(programador, 1)

    buzon.vigilar()

    assert programador.pedidos == [(1, buzon.vigilar)]
