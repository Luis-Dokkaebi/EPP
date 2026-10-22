"""Conversión del COCO de CVAT o Label Studio al COCO del contrato (SPEC/9 §3.1, B-03)."""

from typing import Any

import pytest

from ml.contrato_datos import TAXONOMIA_V1, categorias, validar_anotaciones
from ml.convertir_etiquetas import ConversionInvalidaError, convertir
from tests.coco_sintetico import ARCHIVO, imagen

METADATOS = imagen(sha256="ab" * 32, eliminar_despues_de="2026-11-20")
LADO_MINIMO = 10.0


def _exportado(*anotaciones: dict[str, Any], **cambios_de_imagen: Any) -> dict[str, Any]:
    return {
        "images": [
            {"id": 31, "file_name": f"images/{ARCHIVO}", "width": 640, "height": 480}
            | cambios_de_imagen
        ],
        "annotations": list(anotaciones),
        "categories": [
            {"id": 1, "name": "chaleco", "supercategory": ""},
            {"id": 2, "name": "casco", "supercategory": ""},
        ],
    }


def _anotacion(**cambios: Any) -> dict[str, Any]:
    base = {
        "id": 900,
        "image_id": 31,
        "category_id": 2,
        "bbox": [10.5, 20.0, 30.0, 40.0],
        "area": 1200.0,
        "segmentation": [],
        "iscrowd": 0,
        "attributes": {"occluded": False},
    }
    return base | cambios


def test_convertir_traduce_las_categorias_por_nombre_a_los_ids_de_la_taxonomia() -> None:
    convertido = convertir(_exportado(_anotacion()), [METADATOS], TAXONOMIA_V1)

    assert convertido["categories"] == categorias(TAXONOMIA_V1)
    assert convertido["annotations"] == [
        {
            "id": 1,
            "image_id": 1,
            "category_id": 3,
            "bbox": [10.5, 20.0, 30.0, 40.0],
            "area": 1200.0,
            "iscrowd": 0,
        }
    ]


def test_convertir_agrega_los_metadatos_de_la_captura_a_cada_imagen() -> None:
    convertido = convertir(_exportado(), [METADATOS], TAXONOMIA_V1)

    assert convertido["images"] == [{**METADATOS, "id": 1}]


def test_convertir_produce_un_coco_que_cumple_el_contrato_de_datos() -> None:
    convertido = convertir(_exportado(_anotacion()), [METADATOS], TAXONOMIA_V1)

    validar_anotaciones(convertido, TAXONOMIA_V1, LADO_MINIMO)


@pytest.mark.parametrize(
    "marca",
    [
        {"iscrowd": 1},
        {"attributes": {"ignorar": True}},
        {"attributes": {"ignorar": "true"}},
        {"attributes": {"ignorar": "True"}},
        {"attributes": {"ignorar": "1"}},
        {"attributes": {"ignorar": 1}},
    ],
    ids=["iscrowd", "atributo-bool", "texto", "texto-mayuscula", "texto-uno", "entero-uno"],
)
def test_convertir_marca_como_ignorar_lo_que_el_etiquetador_ignoro(marca: dict[str, Any]) -> None:
    convertido = convertir(_exportado(_anotacion(**marca)), [METADATOS], TAXONOMIA_V1)

    assert convertido["annotations"][0]["iscrowd"] == 1


@pytest.mark.parametrize("valor", [False, "false", "no"])
def test_convertir_no_ignora_si_el_atributo_dice_que_no(valor: object) -> None:
    anotacion = _anotacion(attributes={"ignorar": valor})

    convertido = convertir(_exportado(anotacion), [METADATOS], TAXONOMIA_V1)

    assert convertido["annotations"][0]["iscrowd"] == 0


def test_convertir_rechaza_etiquetas_fuera_de_la_taxonomia() -> None:
    exportado = _exportado(_anotacion(category_id=3))
    exportado["categories"].append({"id": 3, "name": "Casco"})

    with pytest.raises(ConversionInvalidaError) as error:
        convertir(exportado, [METADATOS], TAXONOMIA_V1)

    assert str(error.value) == (
        'Etiqueta "Casco" fuera de la taxonomía (persona, cabeza, casco, chaleco): renómbrala en '
        "la herramienta de etiquetado (docs/ml/guia_etiquetado.md §1)."
    )


def test_convertir_acepta_rutas_de_windows_en_el_exportado() -> None:
    exportado = _exportado(file_name=f"images\\{ARCHIVO}")

    assert convertir(exportado, [METADATOS], TAXONOMIA_V1)["images"][0]["file_name"] == ARCHIVO


def test_convertir_acepta_etiquetas_de_la_herramienta_que_no_se_usaron() -> None:
    exportado = _exportado()
    exportado["categories"].append({"id": 3, "name": "guantes"})

    assert convertir(exportado, [METADATOS], TAXONOMIA_V1)["annotations"] == []


def test_convertir_rechaza_imagenes_sin_metadatos_de_captura() -> None:
    with pytest.raises(ConversionInvalidaError) as error:
        convertir(_exportado(), [], TAXONOMIA_V1)

    assert str(error.value) == (
        f"{ARCHIVO} no tiene metadatos de captura: solo entran imágenes capturadas con "
        "tools/capturar_dataset.py y su autorización."
    )


@pytest.mark.parametrize(
    ("campo", "valor", "capturado"), [("width", 641, 640), ("height", 479, 480)]
)
def test_convertir_rechaza_tamanos_distintos_de_los_capturados(
    campo: str, valor: int, capturado: int
) -> None:
    with pytest.raises(ConversionInvalidaError) as error:
        convertir(_exportado(**{campo: valor}), [METADATOS], TAXONOMIA_V1)

    assert str(error.value) == (
        f'{ARCHIVO}: "{campo}" ({valor}) no coincide con la captura ({capturado}).'
    )


def test_convertir_renumera_imagenes_y_cajas_en_orden_de_nombre() -> None:
    otra = imagen(file_name="cam-01_20261021_083006_0002.jpg", hora="08:30:06")
    exportado = _exportado(_anotacion(id=5), _anotacion(id=6, image_id=32))
    exportado["images"].insert(
        0, {"id": 32, "file_name": otra["file_name"], "width": 640, "height": 480}
    )

    convertido = convertir(exportado, [otra, METADATOS], TAXONOMIA_V1)

    assert [item["file_name"] for item in convertido["images"]] == [ARCHIVO, otra["file_name"]]
    assert [(caja["id"], caja["image_id"]) for caja in convertido["annotations"]] == [
        (1, 1),
        (2, 2),
    ]
