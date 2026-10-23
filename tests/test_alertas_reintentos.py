"""Política de reintentos con backoff exponencial y tope (SPEC/9 §7.1, AC-016).

Los valores salen de la configuración de quien despliega: la política no tiene valores por
omisión y falla en voz alta ante un valor fuera de rango.
"""

import dataclasses
from datetime import timedelta

import pytest

from src.alerts.domain.errores import ConfiguracionAlertasError
from src.alerts.domain.reintentos import PoliticaReintentos

DIEZ_SEGUNDOS = timedelta(seconds=10)
UN_MINUTO = timedelta(minutes=1)


def _politica(
    espera_inicial: timedelta = DIEZ_SEGUNDOS,
    factor: float = 2.0,
    espera_maxima: timedelta = UN_MINUTO,
    intentos_maximos: int = 5,
) -> PoliticaReintentos:
    return PoliticaReintentos(
        espera_inicial=espera_inicial,
        factor=factor,
        espera_maxima=espera_maxima,
        intentos_maximos=intentos_maximos,
    )


@pytest.mark.parametrize(
    ("intentos", "segundos"),
    [(1, 10), (2, 20), (3, 40), (4, 60), (5, 60)],
    ids=["primer-fallo", "segundo", "tercero", "llega-al-tope", "no-pasa-el-tope"],
)
def test_politica_la_espera_crece_exponencialmente_hasta_el_tope(
    intentos: int, segundos: int
) -> None:
    politica = _politica()

    espera = politica.espera_tras(intentos)

    assert espera == timedelta(seconds=segundos)


def test_politica_con_factor_uno_espera_siempre_lo_mismo() -> None:
    politica = _politica(factor=1.0)

    esperas = [politica.espera_tras(intentos) for intentos in (1, 2, 3)]

    assert esperas == [DIEZ_SEGUNDOS] * 3


def test_politica_con_muchos_intentos_no_desborda_y_respeta_el_tope() -> None:
    politica = _politica(factor=10.0)

    espera = politica.espera_tras(10_000)

    assert espera == UN_MINUTO


@pytest.mark.parametrize("intentos", [0, -1], ids=["cero", "negativo"])
def test_politica_la_espera_exige_al_menos_un_intento(intentos: int) -> None:
    politica = _politica()

    with pytest.raises(ValueError, match=rf"^intentos debe ser al menos 1: {intentos}$"):
        politica.espera_tras(intentos)


@pytest.mark.parametrize(
    ("intentos", "agotada"),
    [(1, False), (4, False), (5, True), (6, True)],
    ids=["primero", "antes-del-maximo", "en-el-maximo", "despues-del-maximo"],
)
def test_politica_se_agota_al_llegar_a_los_intentos_maximos(intentos: int, agotada: bool) -> None:
    politica = _politica(intentos_maximos=5)

    assert politica.agotada(intentos) is agotada


def test_politica_validada_no_se_puede_modificar() -> None:
    politica = _politica()

    with pytest.raises(dataclasses.FrozenInstanceError):
        politica.intentos_maximos = 0


def test_politica_acepta_los_valores_limite() -> None:
    politica = _politica(factor=1.0, espera_maxima=DIEZ_SEGUNDOS, intentos_maximos=1)

    assert politica.espera_tras(1) == DIEZ_SEGUNDOS
    assert politica.agotada(1) is True


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"espera_inicial": timedelta(0)}, r"^espera_inicial debe ser positiva: 0:00:00$"),
        (
            {"espera_inicial": -DIEZ_SEGUNDOS},
            r"^espera_inicial debe ser positiva: -1 day, 23:59:50$",
        ),
        ({"factor": 0.99}, r"^factor debe ser al menos 1: 0\.99$"),
        (
            {"espera_maxima": timedelta(seconds=9)},
            r"^espera_maxima no puede ser menor que espera_inicial: 0:00:09 < 0:00:10$",
        ),
        ({"intentos_maximos": 0}, r"^intentos_maximos debe ser al menos 1: 0$"),
    ],
    ids=["espera-cero", "espera-negativa", "factor-menor-a-uno", "tope-bajo", "sin-intentos"],
)
def test_politica_rechaza_valores_fuera_de_rango(cambios: dict[str, object], mensaje: str) -> None:
    with pytest.raises(ConfiguracionAlertasError, match=mensaje):
        _politica(**cambios)
