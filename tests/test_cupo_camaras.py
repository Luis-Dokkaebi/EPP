"""Cupo de cámaras de la licencia (SPEC/1: 1 a 16 cámaras según el plan contratado).

`get_max_cameras()` de la licencia solo se mostraba al activar; nada impedía conectar más.
"""

import pytest

from src.acquisition.cupo_camaras import CupoDeCamarasAgotadoError, exigir_cupo_de_camaras


@pytest.mark.parametrize(
    ("conectadas", "maximo"),
    [(0, 1), (3, 4), (15, 16)],
    ids=["primera_de_una", "ultima_de_cuatro", "ultima_de_dieciseis"],
)
def test_con_cupo_disponible_se_puede_conectar(conectadas: int, maximo: int) -> None:
    exigir_cupo_de_camaras(conectadas, maximo)


@pytest.mark.parametrize(
    ("conectadas", "maximo"),
    [(1, 1), (4, 4), (5, 4), (0, 0)],
    ids=["una_de_una", "cuatro_de_cuatro", "por_encima", "licencia_sin_camaras"],
)
def test_sin_cupo_no_se_puede_conectar(conectadas: int, maximo: int) -> None:
    with pytest.raises(CupoDeCamarasAgotadoError):
        exigir_cupo_de_camaras(conectadas, maximo)


def test_el_error_dice_cuantas_camaras_permite_la_licencia() -> None:
    with pytest.raises(CupoDeCamarasAgotadoError) as error:
        exigir_cupo_de_camaras(2, 2)

    assert str(error.value) == "La licencia permite 2 cámara(s) a la vez"
