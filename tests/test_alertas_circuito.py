"""Circuit breaker del canal de aviso (SPEC/9 §7.1 punto 5; skill error-handling).

Configuración de las pruebas: el circuito se abre con 3 fallas consecutivas y pausa 5 minutos.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.alerts.domain.circuito import CircuitBreaker, EstadoCircuito
from src.alerts.domain.errores import ConfiguracionAlertasError

AHORA = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
PAUSA = timedelta(minutes=5)
UN_MICROSEGUNDO = timedelta(microseconds=1)


def _circuito_con_fallas(fallas: int) -> CircuitBreaker:
    circuito = CircuitBreaker(fallas_para_abrir=3, pausa=PAUSA)
    for _ in range(fallas):
        circuito.registrar_falla(AHORA)
    return circuito


@pytest.mark.parametrize(
    ("texto", "estado"),
    [
        ("canal disponible", EstadoCircuito.CERRADO),
        ("canal en pausa", EstadoCircuito.ABIERTO),
        ("canal en prueba", EstadoCircuito.SEMIABIERTO),
    ],
)
def test_estado_circuito_tiene_un_texto_para_el_usuario(texto: str, estado: EstadoCircuito) -> None:
    assert EstadoCircuito(texto) is estado


@pytest.mark.parametrize("fallas", [0, 2], ids=["sin-fallas", "una-menos-del-umbral"])
def test_circuito_por_debajo_del_umbral_sigue_cerrado(fallas: int) -> None:
    circuito = _circuito_con_fallas(fallas)

    assert circuito.estado(AHORA) is EstadoCircuito.CERRADO
    assert circuito.permite_intento(AHORA) is True


def test_circuito_se_abre_al_llegar_al_umbral_de_fallas_consecutivas() -> None:
    circuito = _circuito_con_fallas(3)

    assert circuito.estado(AHORA) is EstadoCircuito.ABIERTO
    assert circuito.permite_intento(AHORA) is False


def test_circuito_un_exito_reinicia_la_cuenta_de_fallas() -> None:
    circuito = _circuito_con_fallas(2)

    circuito.registrar_exito()
    circuito.registrar_falla(AHORA)
    circuito.registrar_falla(AHORA)

    assert circuito.estado(AHORA) is EstadoCircuito.CERRADO


def test_circuito_abierto_sigue_abierto_hasta_el_ultimo_instante_de_la_pausa() -> None:
    circuito = _circuito_con_fallas(3)

    instante = AHORA + PAUSA - UN_MICROSEGUNDO

    assert circuito.estado(instante) is EstadoCircuito.ABIERTO
    assert circuito.permite_intento(instante) is False


def test_circuito_al_vencer_la_pausa_queda_semiabierto_y_permite_un_intento() -> None:
    circuito = _circuito_con_fallas(3)

    instante = AHORA + PAUSA

    assert circuito.estado(instante) is EstadoCircuito.SEMIABIERTO
    assert circuito.permite_intento(instante) is True


def test_circuito_una_falla_semiabierto_lo_reabre_por_otra_pausa_completa() -> None:
    circuito = _circuito_con_fallas(3)
    reintento = AHORA + PAUSA

    circuito.registrar_falla(reintento)

    assert circuito.estado(reintento + PAUSA - UN_MICROSEGUNDO) is EstadoCircuito.ABIERTO
    assert circuito.estado(reintento + PAUSA) is EstadoCircuito.SEMIABIERTO


def test_circuito_un_exito_semiabierto_lo_cierra_y_reinicia_la_cuenta() -> None:
    circuito = _circuito_con_fallas(3)
    reintento = AHORA + PAUSA

    circuito.registrar_exito()
    circuito.registrar_falla(reintento)
    circuito.registrar_falla(reintento)

    assert circuito.estado(reintento) is EstadoCircuito.CERRADO


def test_circuito_con_umbral_uno_se_abre_con_la_primera_falla() -> None:
    circuito = CircuitBreaker(fallas_para_abrir=1, pausa=PAUSA)

    circuito.registrar_falla(AHORA)

    assert circuito.estado(AHORA) is EstadoCircuito.ABIERTO


@pytest.mark.parametrize(
    ("fallas_para_abrir", "pausa", "mensaje"),
    [
        (0, PAUSA, r"^fallas_para_abrir debe ser al menos 1: 0$"),
        (3, timedelta(0), r"^pausa debe ser positiva: 0:00:00$"),
        (3, -PAUSA, r"^pausa debe ser positiva: -1 day, 23:55:00$"),
    ],
    ids=["sin-fallas", "pausa-cero", "pausa-negativa"],
)
def test_circuito_rechaza_configuracion_fuera_de_rango(
    fallas_para_abrir: int, pausa: timedelta, mensaje: str
) -> None:
    with pytest.raises(ConfiguracionAlertasError, match=mensaje):
        CircuitBreaker(fallas_para_abrir=fallas_para_abrir, pausa=pausa)
