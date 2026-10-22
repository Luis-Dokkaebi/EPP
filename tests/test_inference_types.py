"""Tipos neutrales de detección (SPEC/9 §1.3.2): sin dependencia de ningún motor de IA."""

import math

import pytest

from src.inference.types import (
    CATALOGO_COCO,
    Caja,
    CajaInvalidaError,
    CatalogoDeClases,
    ClaseObjeto,
    ConfianzaInvalidaError,
    Deteccion,
)

ID_COCO_PERSONA = 0
ID_COCO_AUTO = 2
ID_COCO_CELULAR = 67


def test_caja_valida_conserva_sus_coordenadas() -> None:
    caja = Caja(x1=-5.0, y1=-2.5, x2=10.0, y2=0.5)

    assert (caja.x1, caja.y1, caja.x2, caja.y2) == (-5.0, -2.5, 10.0, 0.5)


@pytest.mark.parametrize(
    "coordenadas",
    [(0, 0, 0, 10), (0, 0, 10, 0), (5, 0, 4, 10), (0, 5, 10, 4), (0, 0, math.nan, 10)],
    ids=["ancho-cero", "alto-cero", "x-invertida", "y-invertida", "nan"],
)
def test_caja_degenerada_lanza_error_tipado(coordenadas: tuple[float, ...]) -> None:
    with pytest.raises(CajaInvalidaError, match="x2 > x1 y y2 > y1"):
        Caja(*coordenadas)


def test_caja_es_inmutable() -> None:
    caja = Caja(0, 0, 1, 1)

    with pytest.raises(AttributeError):
        caja.x1 = 5  # type: ignore[misc]  # se verifica justamente que no se pueda asignar


def test_clase_objeto_usa_nombres_semanticos() -> None:
    assert [clase.value for clase in ClaseObjeto] == ["persona", "celular"]


@pytest.mark.parametrize("confianza", [0.0, 0.5, 1.0])
def test_deteccion_acepta_confianza_entre_cero_y_uno(confianza: float) -> None:
    deteccion = Deteccion(ClaseObjeto.PERSONA, confianza, Caja(0, 0, 1, 1))

    assert deteccion.confianza == confianza


@pytest.mark.parametrize("confianza", [-0.01, 1.01, math.nan])
def test_deteccion_con_confianza_fuera_de_rango_lanza_error_tipado(confianza: float) -> None:
    with pytest.raises(ConfianzaInvalidaError, match="entre 0 y 1"):
        Deteccion(ClaseObjeto.PERSONA, confianza, Caja(0, 0, 1, 1))


@pytest.mark.parametrize(
    ("id_modelo", "clase"),
    [(ID_COCO_PERSONA, ClaseObjeto.PERSONA), (ID_COCO_CELULAR, ClaseObjeto.CELULAR)],
)
def test_catalogo_coco_traduce_ids_a_clases(id_modelo: int, clase: ClaseObjeto) -> None:
    assert CATALOGO_COCO.clase_de(id_modelo) is clase


def test_catalogo_ignora_ids_que_no_son_del_dominio() -> None:
    assert CATALOGO_COCO.clase_de(ID_COCO_AUTO) is None


def test_catalogo_no_cambia_si_se_modifica_el_diccionario_original() -> None:
    ids = {7: ClaseObjeto.PERSONA}
    catalogo = CatalogoDeClases(ids)

    ids[7] = ClaseObjeto.CELULAR

    assert catalogo.clase_de(7) is ClaseObjeto.PERSONA
