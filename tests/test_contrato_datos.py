"""Contrato de datos: taxonomía, secciones y metadatos de imagen (docs/ml/contrato_datos.md)."""

from typing import Any

import pytest

from ml.contrato_datos import (
    TAXONOMIA_V1,
    TAXONOMIA_V2,
    TAXONOMIAS,
    ContratoDeDatosError,
    categorias,
    validar_anotaciones,
)
from tests.coco_sintetico import ARCHIVO, LADO_MINIMO, coco, imagen


def _violaciones(dataset: dict[str, Any]) -> list[str]:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_anotaciones(dataset, TAXONOMIA_V1, LADO_MINIMO)
    return error.value.violaciones


def test_taxonomia_v1_es_la_de_la_decision_d3() -> None:
    assert TAXONOMIA_V1 == ("persona", "cabeza", "casco", "chaleco")


def test_taxonomia_v2_agrega_clases_al_final_sin_renumerar_la_v1() -> None:
    assert TAXONOMIA_V2 == (*TAXONOMIA_V1, "manos", "guantes", "gafas", "barbijo")


def test_taxonomias_se_eligen_por_version() -> None:
    assert TAXONOMIAS == {"v1": TAXONOMIA_V1, "v2": TAXONOMIA_V2}


def test_categorias_numera_desde_uno_en_el_orden_de_la_taxonomia() -> None:
    assert categorias(("persona", "casco")) == [
        {"id": 1, "name": "persona"},
        {"id": 2, "name": "casco"},
    ]


def test_validar_anotaciones_acepta_un_coco_que_cumple_el_contrato() -> None:
    validar_anotaciones(coco(), TAXONOMIA_V1, LADO_MINIMO)


def test_validar_anotaciones_acepta_un_dataset_sin_cajas() -> None:
    dataset = {"images": [imagen()], "annotations": [], "categories": categorias(TAXONOMIA_V1)}

    validar_anotaciones(dataset, TAXONOMIA_V1, LADO_MINIMO)


@pytest.mark.parametrize("seccion", ["images", "annotations", "categories"])
def test_validar_anotaciones_exige_las_tres_secciones_de_coco(seccion: str) -> None:
    dataset = coco()
    del dataset[seccion]

    assert _violaciones(dataset) == [f'Falta la sección "{seccion}" del COCO.']


@pytest.mark.parametrize(
    "exportadas",
    [
        categorias(("persona", "cabeza", "chaleco", "casco")),
        categorias(TAXONOMIA_V2),
        categorias(("persona", "cabeza", "casco")),
        [{"id": 0, "name": "persona"}, *categorias(TAXONOMIA_V1)[1:]],
    ],
    ids=["orden-cambiado", "taxonomia-v2", "falta-una", "id-cero"],
)
def test_validar_anotaciones_rechaza_categorias_distintas_de_la_taxonomia(
    exportadas: list[dict[str, Any]],
) -> None:
    dataset = {**coco(), "categories": exportadas}

    assert _violaciones(dataset) == [
        "Las categorías no son las de la taxonomía (ids desde 1, en orden): "
        "persona, cabeza, casco, chaleco."
    ]


@pytest.mark.parametrize("campo", ["camara", "fecha", "hora", "turno", "autorizacion"])
def test_validar_anotaciones_exige_cada_metadato_de_la_captura(campo: str) -> None:
    sin_campo = imagen()
    del sin_campo[campo]

    assert _violaciones(coco(sin_campo)) == [f'{ARCHIVO}: falta el metadato "{campo}".']


@pytest.mark.parametrize("campo", ["turno", "autorizacion"])
@pytest.mark.parametrize("valor", ["", "   ", 7, None])
def test_validar_anotaciones_rechaza_metadatos_vacios(campo: str, valor: object) -> None:
    assert _violaciones(coco(imagen(**{campo: valor}))) == [
        f'{ARCHIVO}: falta el metadato "{campo}".'
    ]


@pytest.mark.parametrize(
    "nombre",
    [
        "Cam-01_20261021_083005_0001.jpg",
        "juan perez_20261021_083005_0001.jpg",
        "cam-01_20261021_083005_0001.png",
        "cam-01_20261021_0830_0001.jpg",
        "x/cam-01_20261021_083005_0001.jpg",
        "cam-01_20261021_083005_0001.jpg.bak",
        "_20261021_083005_0001.jpg",
    ],
)
def test_validar_anotaciones_rechaza_nombres_fuera_del_formato(nombre: str) -> None:
    assert _violaciones(coco(imagen(file_name=nombre))) == [
        f"{nombre}: el nombre no sigue <camara>_<AAAAMMDD>_<HHMMSS>_<nnnn>.jpg."
    ]


@pytest.mark.parametrize(
    "nombre", ["cam-01_20261321_083005_0001.jpg", "cam-01_20261021_250000_0001.jpg"]
)
def test_validar_anotaciones_rechaza_fechas_u_horas_imposibles_en_el_nombre(nombre: str) -> None:
    assert _violaciones(coco(imagen(file_name=nombre))) == [
        f"{nombre}: la fecha y hora del nombre no existen."
    ]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("camara", "cam-02"), ("fecha", "2026-10-22"), ("hora", "08:30:06")],
)
def test_validar_anotaciones_exige_metadatos_coherentes_con_el_nombre(
    campo: str, valor: str
) -> None:
    assert _violaciones(coco(imagen(**{campo: valor}))) == [
        f'{ARCHIVO}: el metadato "{campo}" ({valor}) no coincide con el nombre del archivo.'
    ]


def test_validar_anotaciones_informa_todas_las_violaciones_juntas() -> None:
    dataset = coco(imagen(turno="", camara="cam-09"))

    assert _violaciones(dataset) == [
        f'{ARCHIVO}: falta el metadato "turno".',
        f'{ARCHIVO}: el metadato "camara" (cam-09) no coincide con el nombre del archivo.',
    ]


def test_contrato_de_datos_error_conserva_la_lista_de_violaciones() -> None:
    error = ContratoDeDatosError(["a", "b"])

    assert error.violaciones == ["a", "b"]
    assert str(error) == "El dataset no cumple el contrato de datos:\na\nb"
