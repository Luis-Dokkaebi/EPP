"""Despacho de la bandeja de salida de avisos (SPEC/9 §7.1, AC-016).

Configuración de las pruebas: reintento a los 10 s, factor 2, tope 1 min y 5 intentos como
máximo; el circuito se abre con 3 fallas seguidas y pausa 5 minutos.
"""

import logging
from collections.abc import Iterable
from datetime import timedelta

import pytest

from src.alerts.application.despachar_notificaciones import (
    DespacharNotificaciones,
    PuertosDespacho,
)
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.circuito import CircuitBreaker
from src.alerts.domain.reintentos import PoliticaReintentos
from tests.dobles_alertas import BandejaFalsa, CanalFalso, aviso
from tests.dobles_ppe import INICIO, RelojFalso

POLITICA = PoliticaReintentos(
    espera_inicial=timedelta(seconds=10),
    factor=2.0,
    espera_maxima=timedelta(minutes=1),
    intentos_maximos=5,
)
PAUSA = timedelta(minutes=5)


class Despacho:
    """Despachador armado con dobles, más los dobles para inspeccionarlos."""

    def __init__(
        self, avisos: Iterable[Aviso], respuestas: Iterable[bool], circuito: CircuitBreaker
    ) -> None:
        self.bandeja = BandejaFalsa(avisos)
        self.canal = CanalFalso(respuestas)
        self.reloj = RelojFalso()
        self.circuito = circuito
        self.caso = DespacharNotificaciones(
            PuertosDespacho(bandeja=self.bandeja, notificador=self.canal, reloj=self.reloj),
            politica=POLITICA,
            circuito=circuito,
        )


def _despacho(avisos: Iterable[Aviso], respuestas: Iterable[bool]) -> Despacho:
    return Despacho(avisos, respuestas, CircuitBreaker(fallas_para_abrir=3, pausa=PAUSA))


def test_despachar_entrega_los_pendientes_en_orden_y_los_marca_enviados() -> None:
    despacho = _despacho([aviso(1), aviso(2)], [True, True])

    despacho.caso.despachar_pendientes()

    assert despacho.canal.intentos == [1, 2]
    assert despacho.bandeja.cambios == [("enviada", 1), ("enviada", 2)]


def test_despachar_consulta_los_pendientes_con_la_hora_del_reloj() -> None:
    despacho = _despacho([], [])
    despacho.reloj.avanzar(timedelta(hours=1))

    despacho.caso.despachar_pendientes()

    assert despacho.bandeja.consultas == [INICIO + timedelta(hours=1)]


@pytest.mark.parametrize(
    ("intentos_previos", "espera"),
    [(0, timedelta(seconds=10)), (2, timedelta(seconds=40)), (3, timedelta(minutes=1))],
    ids=["primer-fallo", "tercer-fallo", "cuarto-fallo-con-tope"],
)
def test_despachar_un_fallo_reprograma_el_aviso_con_backoff(
    intentos_previos: int, espera: timedelta
) -> None:
    despacho = _despacho([aviso(7, intentos=intentos_previos)], [False])

    despacho.caso.despachar_pendientes()

    assert despacho.bandeja.cambios == [
        ("reprogramada", 7, intentos_previos + 1, INICIO + espera),
    ]


def test_despachar_al_agotar_los_intentos_marca_el_aviso_como_fallido(
    caplog: pytest.LogCaptureFixture,
) -> None:
    despacho = _despacho([aviso(7, intentos=4)], [False])

    with caplog.at_level(logging.ERROR):
        despacho.caso.despachar_pendientes()

    assert despacho.bandeja.cambios == [("fallida", 7, 5)]
    assert caplog.messages == [
        "Aviso 7 FALLIDO tras 5 intentos: canal caído al enviar el aviso 7",
    ]


def test_despachar_registra_cada_reintento_sin_datos_personales(
    caplog: pytest.LogCaptureFixture,
) -> None:
    despacho = _despacho([aviso(7, persona="Ana")], [False])

    with caplog.at_level(logging.WARNING):
        despacho.caso.despachar_pendientes()

    assert caplog.messages == [
        "Aviso 7 no entregado (intento 1); se reintenta a las "
        "2026-10-22T08:00:10+00:00: canal caído al enviar el aviso 7",
    ]
    assert "Ana" not in caplog.text


def test_despachar_con_el_canal_caido_se_detiene_al_abrirse_el_circuito(
    caplog: pytest.LogCaptureFixture,
) -> None:
    despacho = _despacho([aviso(numero) for numero in range(1, 6)], [False] * 5)

    with caplog.at_level(logging.WARNING):
        despacho.caso.despachar_pendientes()

    assert despacho.canal.intentos == [1, 2, 3]
    assert [cambio[1] for cambio in despacho.bandeja.cambios] == [1, 2, 3]
    assert caplog.messages[-1] == "Despacho en espera (canal en pausa): quedan avisos pendientes"


def test_despachar_con_el_circuito_abierto_no_intenta_ni_cambia_nada() -> None:
    circuito = CircuitBreaker(fallas_para_abrir=1, pausa=PAUSA)
    circuito.registrar_falla(INICIO)
    despacho = Despacho([aviso(1)], [], circuito)

    despacho.caso.despachar_pendientes()

    assert despacho.canal.intentos == []
    assert despacho.bandeja.cambios == []


def test_despachar_una_entrega_reinicia_la_cuenta_de_fallas_del_circuito() -> None:
    respuestas = [False, False, True, False, False]
    despacho = _despacho([aviso(numero) for numero in range(1, 6)], respuestas)

    despacho.caso.despachar_pendientes()

    assert despacho.canal.intentos == [1, 2, 3, 4, 5]


def test_despachar_vencida_la_pausa_prueba_el_canal_y_entrega() -> None:
    circuito = CircuitBreaker(fallas_para_abrir=1, pausa=PAUSA)
    circuito.registrar_falla(INICIO)
    despacho = Despacho([aviso(1), aviso(2)], [True, True], circuito)
    despacho.reloj.avanzar(PAUSA)

    despacho.caso.despachar_pendientes()

    assert despacho.bandeja.cambios == [("enviada", 1), ("enviada", 2)]


class CanalRoto:
    """Canal con un defecto de programación: lanza algo que no es una falla de entrega."""

    def enviar(self, aviso: Aviso) -> None:
        raise RuntimeError(f"defecto en el adaptador con el aviso {aviso.id_aviso}")


def test_despachar_un_error_inesperado_del_canal_no_se_silencia_ni_cambia_el_aviso() -> None:
    bandeja = BandejaFalsa([aviso(1)])
    caso = DespacharNotificaciones(
        PuertosDespacho(bandeja=bandeja, notificador=CanalRoto(), reloj=RelojFalso()),
        politica=POLITICA,
        circuito=CircuitBreaker(fallas_para_abrir=3, pausa=PAUSA),
    )

    with pytest.raises(RuntimeError, match=r"^defecto en el adaptador con el aviso 1$"):
        caso.despachar_pendientes()

    assert bandeja.cambios == []
