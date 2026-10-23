"""Hilo del despachador de avisos, separado de las cámaras (SPEC/9 §7.1 punto 2; CLAUDE.md §16).

Sin `sleep`: las pruebas se sincronizan con condiciones y eventos, y verifican que cada
`iniciar()` tenga su `detener()` sin dejar hilos vivos. La espera máxima es corta a propósito: lo
normal es que la condición se cumpla en milisegundos, y una falla debe aparecer pronto.
"""

import logging
import threading
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest

from src.alerts.domain.errores import ConfiguracionAlertasError
from src.alerts.hilo_despachador import HiloDespachador

UN_MILISEGUNDO = timedelta(milliseconds=1)
UNA_HORA = timedelta(hours=1)
ESPERA = timedelta(seconds=2)
CrearHilo = Callable[[Callable[[], None], timedelta], HiloDespachador]


class DespachoContado:
    """Despacho falso que cuenta sus ciclos; la prueba puede esperar a que lleguen a N."""

    def __init__(self) -> None:
        self.ciclos = 0
        self._cambio = threading.Condition()

    def __call__(self) -> None:
        with self._cambio:
            self.ciclos += 1
            self._cambio.notify_all()

    def esperar(self, ciclos: int) -> bool:
        with self._cambio:
            return self._cambio.wait_for(lambda: self.ciclos >= ciclos, ESPERA.total_seconds())


class DespachoQueFallaUnaVez(DespachoContado):
    """El primer ciclo falla como fallaría la base bloqueada; los siguientes andan."""

    def __call__(self) -> None:
        super().__call__()
        if self.ciclos == 1:
            raise OSError("base bloqueada")


class DespachoTrabado:
    """Despacho que no termina hasta que la prueba lo libera."""

    def __init__(self) -> None:
        self.en_curso = threading.Event()
        self.liberar = threading.Event()

    def __call__(self) -> None:
        self.en_curso.set()
        self.liberar.wait(ESPERA.total_seconds())


def _hilos_del_despachador() -> list[threading.Thread]:
    return [hilo for hilo in threading.enumerate() if hilo.name == "despachador-avisos"]


@pytest.fixture
def crear_hilo() -> Iterator[CrearHilo]:
    """Crea hilos que, pase lo que pase en la prueba, se detienen al final y sin fugas."""
    creados: list[HiloDespachador] = []

    def crear(despachar: Callable[[], None], intervalo: timedelta) -> HiloDespachador:
        creados.append(HiloDespachador(despachar, intervalo=intervalo))
        return creados[-1]

    yield crear
    for hilo in creados:
        hilo.detener(ESPERA)
    assert _hilos_del_despachador() == []


def test_hilo_repite_el_despacho_en_cada_intervalo(crear_hilo: CrearHilo) -> None:
    despacho = DespachoContado()
    hilo = crear_hilo(despacho, UN_MILISEGUNDO)

    hilo.iniciar()

    assert despacho.esperar(3) is True
    hilo.detener(ESPERA)


def test_hilo_despacha_apenas_arranca_aunque_el_intervalo_sea_largo(crear_hilo: CrearHilo) -> None:
    despacho = DespachoContado()
    hilo = crear_hilo(despacho, UNA_HORA)

    hilo.iniciar()

    assert despacho.esperar(1) is True
    hilo.detener(ESPERA)


def test_hilo_detener_libera_el_hilo_y_no_vuelve_a_despachar(crear_hilo: CrearHilo) -> None:
    despacho = DespachoContado()
    hilo = crear_hilo(despacho, UNA_HORA)
    hilo.iniciar()
    despacho.esperar(1)

    hilo.detener(ESPERA)

    assert hilo.en_marcha is False
    assert despacho.ciclos == 1


def test_hilo_corre_en_segundo_plano_sin_impedir_cerrar_la_aplicacion(
    crear_hilo: CrearHilo,
) -> None:
    hilo = crear_hilo(DespachoContado(), UNA_HORA)

    hilo.iniciar()

    assert hilo.en_marcha is True
    assert [corriendo.daemon for corriendo in _hilos_del_despachador()] == [True]
    hilo.detener(ESPERA)


def test_hilo_se_puede_volver_a_iniciar_despues_de_detenerlo(crear_hilo: CrearHilo) -> None:
    despacho = DespachoContado()
    hilo = crear_hilo(despacho, UN_MILISEGUNDO)
    hilo.iniciar()
    despacho.esperar(1)
    hilo.detener(ESPERA)
    ciclos_de_la_primera_vez = despacho.ciclos

    hilo.iniciar()

    assert despacho.esperar(ciclos_de_la_primera_vez + 2) is True
    hilo.detener(ESPERA)


def test_hilo_iniciar_dos_veces_falla_sin_lanzar_otro_hilo(crear_hilo: CrearHilo) -> None:
    hilo = crear_hilo(DespachoContado(), UNA_HORA)
    hilo.iniciar()

    with pytest.raises(RuntimeError, match=r"^El despachador de avisos ya está en marcha$"):
        hilo.iniciar()

    assert len(_hilos_del_despachador()) == 1
    hilo.detener(ESPERA)


def test_hilo_detener_sin_haber_iniciado_no_hace_nada(crear_hilo: CrearHilo) -> None:
    hilo = crear_hilo(DespachoContado(), UNA_HORA)

    hilo.detener(ESPERA)

    assert hilo.en_marcha is False


def test_hilo_un_ciclo_que_falla_se_registra_y_el_despacho_sigue(
    crear_hilo: CrearHilo, caplog: pytest.LogCaptureFixture
) -> None:
    despacho = DespachoQueFallaUnaVez()
    hilo = crear_hilo(despacho, UN_MILISEGUNDO)

    with caplog.at_level(logging.ERROR):
        hilo.iniciar()
        segundo_ciclo = despacho.esperar(2)
        hilo.detener(ESPERA)

    assert segundo_ciclo is True
    assert caplog.messages == [
        "Falló un ciclo del despacho de avisos; se reintenta en el próximo ciclo",
    ]
    assert "OSError: base bloqueada" in caplog.text


def test_hilo_que_no_termina_a_tiempo_falla_en_voz_alta(crear_hilo: CrearHilo) -> None:
    despacho = DespachoTrabado()
    hilo = crear_hilo(despacho, UNA_HORA)
    hilo.iniciar()
    despacho.en_curso.wait(ESPERA.total_seconds())

    with pytest.raises(
        RuntimeError, match=r"^El despachador de avisos no se detuvo en 0:00:00\.001000$"
    ):
        hilo.detener(UN_MILISEGUNDO)

    assert hilo.en_marcha is True
    despacho.liberar.set()
    hilo.detener(ESPERA)


@pytest.mark.parametrize(
    ("intervalo", "mensaje"),
    [
        (timedelta(0), r"^intervalo debe ser positivo: 0:00:00$"),
        (-UNA_HORA, r"^intervalo debe ser positivo: -1 day, 23:00:00$"),
    ],
    ids=["cero", "negativo"],
)
def test_hilo_rechaza_un_intervalo_que_no_es_positivo(intervalo: timedelta, mensaje: str) -> None:
    with pytest.raises(ConfiguracionAlertasError, match=mensaje):
        HiloDespachador(DespachoContado(), intervalo=intervalo)
