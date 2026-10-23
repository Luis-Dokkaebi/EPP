"""Validación de la configuración del dominio de EPP en el borde (CLAUDE.md §9)."""

import math

import pytest

from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.validacion import exigir_fraccion


@pytest.mark.parametrize(
    "valor", [0.0, -0.1, 1.01, math.nan], ids=["cero", "negativa", "mayor_que_uno", "nan"]
)
def test_exigir_fraccion_fuera_de_rango_falla_nombrando_el_parametro(valor: float) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=r"^ioa_minimo debe estar en \(0, 1\]: "):
        exigir_fraccion("ioa_minimo", valor)


@pytest.mark.parametrize("valor", [1e-9, 0.5, 1.0], ids=["casi_cero", "media", "uno"])
def test_exigir_fraccion_en_rango_devuelve_el_valor(valor: float) -> None:
    assert exigir_fraccion("ioa_minimo", valor) == valor
