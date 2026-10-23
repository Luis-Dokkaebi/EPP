"""Acuerdo entre etiquetadores: mensajes exactos y bordes geométricos (mutantes de B-03)."""

import pytest

from ml.contrato_datos import categorias
from tests.coco_sintetico import ID_CASCO, etiquetado
from tools.acuerdo_etiquetado import (
    AcuerdoDeClase,
    AcuerdoInvalidoError,
    Caja,
    UmbralDeAcuerdoPendienteError,
    clases_bajo_el_umbral,
    iou,
    medir_acuerdo,
)

CUADRADO = Caja("casco", 0, 0, 10, 10)


@pytest.mark.parametrize(
    ("b", "esperado"),
    [(Caja("casco", 0, 5, 10, 10), 50 / 150), (Caja("casco", 0, 20, 10, 10), 0.0)],
    ids=["mitad-vertical", "separadas-en-vertical"],
)
def test_iou_tambien_mide_el_solapamiento_vertical(b: Caja, esperado: float) -> None:
    assert iou(CUADRADO, b) == pytest.approx(esperado)


def test_acuerdo_de_clase_con_varias_coincidencias() -> None:
    resultado = AcuerdoDeClase("casco", cajas_a=2, cajas_b=3, coincidencias=2, iou_medio=1.0)

    assert resultado.acuerdo == pytest.approx(0.8)


def test_iou_medio_promedia_los_pares_de_la_misma_clase() -> None:
    a = etiquetado((ID_CASCO, [0, 0, 10, 10]), (ID_CASCO, [100, 0, 10, 10]))
    b = etiquetado((ID_CASCO, [0, 0, 10, 10]), (ID_CASCO, [100, 0, 10, 15]))

    assert medir_acuerdo(a, b).por_clase["casco"].iou_medio == pytest.approx((1 + 100 / 150) / 2)


def test_informe_de_acuerdo_es_inmutable() -> None:
    informe = medir_acuerdo(etiquetado(), etiquetado())

    with pytest.raises(AttributeError, match="cannot assign"):
        informe.kappa = 1.0


def test_medir_acuerdo_explica_las_imagenes_que_difieren() -> None:
    b = etiquetado()
    b["images"] = [{"id": 7, "file_name": "cam-02_20261021_083005_0001.jpg"}]

    with pytest.raises(AcuerdoInvalidoError) as error:
        medir_acuerdo(etiquetado(), b)

    assert str(error.value) == (
        "Los dos etiquetados deben cubrir las mismas imágenes; difieren en: "
        "cam-01_20261021_083005_0001.jpg, cam-02_20261021_083005_0001.jpg."
    )


def test_medir_acuerdo_explica_las_categorias_distintas() -> None:
    b = {**etiquetado(), "categories": categorias(("persona", "casco"))}

    with pytest.raises(AcuerdoInvalidoError) as error:
        medir_acuerdo(etiquetado(), b)

    assert str(error.value) == "Los dos etiquetados deben usar las mismas categorías."


def test_clases_bajo_el_umbral_explica_que_el_umbral_esta_pendiente() -> None:
    with pytest.raises(UmbralDeAcuerdoPendienteError) as error:
        clases_bajo_el_umbral(medir_acuerdo(etiquetado(), etiquetado()), None)

    assert str(error.value) == (
        "Umbral de acuerdo PENDIENTE: lo aprueba el responsable de producto junto con la guía "
        "de etiquetado (docs/ml/guia_etiquetado.md §6). Sin él, nada se aprueba."
    )
