"""Validación de la configuración del dominio de EPP en el borde (CLAUDE.md §9)."""

import math
from datetime import timedelta

import pytest

from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.validacion import (
    exigir_al_menos_uno,
    exigir_duracion_positiva,
    exigir_fraccion,
)


@pytest.mark.parametrize(
    "valor", [0.0, -0.1, 1.01, math.nan], ids=["cero", "negativa", "mayor_que_uno", "nan"]
)
def test_exigir_fraccion_fuera_de_rango_falla_nombrando_el_parametro(valor: float) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=r"^ioa_minimo debe estar en \(0, 1\]: "):
        exigir_fraccion("ioa_minimo", valor)


@pytest.mark.parametrize("valor", [1e-9, 0.5, 1.0], ids=["casi_cero", "media", "uno"])
def test_exigir_fraccion_en_rango_devuelve_el_valor(valor: float) -> None:
    assert exigir_fraccion("ioa_minimo", valor) == valor


@pytest.mark.parametrize("valor", [timedelta(0), timedelta(seconds=-1)], ids=["cero", "negativa"])
def test_exigir_duracion_positiva_rechaza_cero_y_negativas(valor: timedelta) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=r"^tiempo debe ser positivo: "):
        exigir_duracion_positiva("tiempo", valor)


def test_exigir_duracion_positiva_acepta_un_microsegundo() -> None:
    un_microsegundo = timedelta(microseconds=1)

    assert exigir_duracion_positiva("tiempo", un_microsegundo) == un_microsegundo


@pytest.mark.parametrize("valor", [0, -1], ids=["cero", "negativo"])
def test_exigir_al_menos_uno_rechaza_menos_de_uno(valor: int) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=rf"^frames debe ser al menos 1: {valor}$"):
        exigir_al_menos_uno("frames", valor)


@pytest.mark.parametrize("valor", [1, 2], ids=["uno", "dos"])
def test_exigir_al_menos_uno_acepta_uno_o_mas(valor: int) -> None:
    assert exigir_al_menos_uno("frames", valor) == valor
