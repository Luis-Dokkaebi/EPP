"""Geometría propia del dominio de EPP: cajas en coordenadas de imagen (SPEC/9 §4.1)."""

import dataclasses
import math

import pytest

from src.ppe.domain.errores import CajaInvalidaError
from src.ppe.domain.geometria import Caja

CAJA_10X20 = Caja(x1=0.0, y1=0.0, x2=10.0, y2=20.0)
HIPOTENUSA_3_4 = 5.0


def test_caja_mide_ancho_alto_y_area() -> None:
    caja = Caja(x1=2.0, y1=3.0, x2=7.0, y2=11.0)

    medidas = (caja.ancho, caja.alto, caja.area)

    assert medidas == (5.0, 8.0, 40.0)


def test_caja_con_coordenadas_negativas_es_valida() -> None:
    caja = Caja(x1=-30.0, y1=-10.0, x2=-20.0, y2=10.0)

    assert (caja.ancho, caja.alto, caja.centro) == (10.0, 20.0, (-25.0, 0.0))


def test_caja_centro_es_el_punto_medio_de_sus_esquinas() -> None:
    caja = Caja(x1=2.0, y1=4.0, x2=10.0, y2=20.0)

    assert caja.centro == (6.0, 12.0)


@pytest.mark.parametrize(
    "caja",
    [Caja(x1=5.0, y1=5.0, x2=5.0, y2=9.0), Caja(x1=5.0, y1=5.0, x2=9.0, y2=5.0)],
    ids=["ancho_cero", "alto_cero"],
)
def test_caja_degenerada_es_valida_y_no_tiene_area(caja: Caja) -> None:
    assert caja.area == 0.0


@pytest.mark.parametrize(
    "esquinas",
    [(10.0, 0.0, 9.0, 5.0), (0.0, 10.0, 5.0, 9.0)],
    ids=["x_invertida", "y_invertida"],
)
def test_caja_con_esquinas_invertidas_es_invalida(
    esquinas: tuple[float, float, float, float],
) -> None:
    with pytest.raises(CajaInvalidaError, match=r"^Caja con esquinas invertidas .*\)$"):
        Caja(*esquinas)


@pytest.mark.parametrize("coordenada", [0, 1, 2, 3], ids=["x1", "y1", "x2", "y2"])
@pytest.mark.parametrize("valor", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_caja_con_coordenada_no_finita_es_invalida(coordenada: int, valor: float) -> None:
    esquinas = [0.0, 0.0, 10.0, 10.0]
    esquinas[coordenada] = valor

    with pytest.raises(CajaInvalidaError, match=r"^Caja con coordenadas no finitas: Caja\(.*\)$"):
        Caja(*esquinas)


@pytest.mark.parametrize(
    ("otra", "area_esperada"),
    [
        (Caja(x1=5.0, y1=10.0, x2=15.0, y2=30.0), 50.0),
        (Caja(x1=2.0, y1=2.0, x2=4.0, y2=6.0), 8.0),
        (Caja(x1=10.0, y1=0.0, x2=20.0, y2=20.0), 0.0),
        (Caja(x1=11.0, y1=0.0, x2=20.0, y2=20.0), 0.0),
        (Caja(x1=0.0, y1=21.0, x2=10.0, y2=30.0), 0.0),
        (Caja(x1=12.0, y1=22.0, x2=20.0, y2=30.0), 0.0),
        (Caja(x1=-5.0, y1=-5.0, x2=0.5, y2=0.5), 0.25),
    ],
    ids=[
        "solapada",
        "contenida",
        "tocando_el_borde",
        "separada_en_x",
        "separada_en_y",
        "separada_en_ambos_ejes",
        "solape_menor_que_uno",
    ],
)
def test_caja_area_de_interseccion(otra: Caja, area_esperada: float) -> None:
    assert CAJA_10X20.area_interseccion(otra) == area_esperada
    assert otra.area_interseccion(CAJA_10X20) == area_esperada


@pytest.mark.parametrize(
    ("region", "ioa_esperado"),
    [
        (Caja(x1=-5.0, y1=-5.0, x2=50.0, y2=50.0), 1.0),
        (Caja(x1=0.0, y1=0.0, x2=10.0, y2=5.0), 0.25),
        (Caja(x1=20.0, y1=0.0, x2=30.0, y2=20.0), 0.0),
    ],
    ids=["dentro", "un_cuarto", "fuera"],
)
def test_caja_ioa_es_interseccion_sobre_el_area_propia(region: Caja, ioa_esperado: float) -> None:
    assert CAJA_10X20.ioa(region) == ioa_esperado


def test_caja_ioa_de_una_caja_degenerada_es_cero() -> None:
    degenerada = Caja(x1=5.0, y1=5.0, x2=5.0, y2=9.0)

    assert degenerada.ioa(CAJA_10X20) == 0.0


def test_caja_distancia_entre_centros_es_euclidea() -> None:
    otra = Caja(x1=3.0, y1=4.0, x2=13.0, y2=24.0)

    assert CAJA_10X20.distancia_entre_centros(otra) == HIPOTENUSA_3_4


@pytest.mark.parametrize(
    ("desde", "hasta", "esperada"),
    [
        (0.0, 0.25, Caja(x1=10.0, y1=20.0, x2=30.0, y2=30.0)),
        (0.5, 1.0, Caja(x1=10.0, y1=40.0, x2=30.0, y2=60.0)),
    ],
    ids=["cuarto_superior", "mitad_inferior"],
)
def test_caja_franja_vertical_recorta_entre_fracciones_del_alto(
    desde: float, hasta: float, esperada: Caja
) -> None:
    caja = Caja(x1=10.0, y1=20.0, x2=30.0, y2=60.0)

    assert caja.franja_vertical(desde, hasta) == esperada


def test_caja_es_inmutable() -> None:
    caja = Caja(x1=0.0, y1=0.0, x2=1.0, y2=1.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        caja.x1 = 2.0
