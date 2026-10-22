"""Acuerdo entre etiquetadores sobre el doble etiquetado (SPEC/9 §2.5; guía de etiquetado §6)."""

import pytest

from ml.contrato_datos import categorias
from tests.coco_sintetico import ID_CASCO as CASCO
from tests.coco_sintetico import ID_CHALECO as CHALECO
from tests.coco_sintetico import etiquetado
from tools.acuerdo_etiquetado import (
    AcuerdoInvalidoError,
    Caja,
    UmbralDeAcuerdoPendienteError,
    clases_bajo_el_umbral,
    emparejar,
    iou,
    kappa_de_cohen,
    medir_acuerdo,
)


@pytest.mark.parametrize(
    ("b", "esperado"),
    [
        (Caja("casco", 0, 0, 10, 10), 1.0),
        (Caja("casco", 5, 0, 10, 10), 50 / 150),
        (Caja("casco", 10, 0, 10, 10), 0.0),
        (Caja("casco", 50, 50, 5, 5), 0.0),
    ],
    ids=["identica", "mitad", "tocandose", "lejos"],
)
def test_iou_mide_interseccion_sobre_union(b: Caja, esperado: float) -> None:
    assert iou(Caja("casco", 0, 0, 10, 10), b) == pytest.approx(esperado)


def test_emparejar_une_primero_los_pares_de_mayor_iou_y_usa_cada_caja_una_vez() -> None:
    a = [Caja("casco", 0, 0, 10, 10), Caja("casco", 2, 0, 10, 10)]
    b = [Caja("casco", 2, 0, 10, 10)]

    assert emparejar(a, b) == [(1, 0), (0, None)]


@pytest.mark.parametrize(
    ("ancho", "pares"),
    [(20, [(0, 0)]), (20.5, [(0, None), (None, 0)])],
    ids=["iou-0.5", "iou-0.49"],
)
def test_emparejar_exige_un_iou_de_al_menos_la_mitad(
    ancho: float, pares: list[tuple[int | None, int | None]]
) -> None:
    a = [Caja("casco", 0, 0, 10, 10)]
    b = [Caja("casco", 0, 0, ancho, 10)]

    assert emparejar(a, b) == pares


def test_emparejar_deja_sin_pareja_las_cajas_de_b_que_sobran() -> None:
    assert emparejar([], [Caja("casco", 0, 0, 5, 5)]) == [(None, 0)]


def test_kappa_de_cohen_del_ejemplo_clasico_vale_cero_coma_cuatro() -> None:
    pares = [("x", "x")] * 20 + [("x", "y")] * 5 + [("y", "x")] * 10 + [("y", "y")] * 15

    assert kappa_de_cohen(pares) == pytest.approx(0.4)


@pytest.mark.parametrize("pares", [[], [("casco", "casco")] * 3], ids=["vacio", "una-clase"])
def test_kappa_de_cohen_no_esta_definido_sin_variedad(pares: list[tuple[str, str]]) -> None:
    assert kappa_de_cohen(pares) is None


def test_medir_acuerdo_por_clase_cuenta_coincidencias_sobre_el_total_de_cajas() -> None:
    a = etiquetado((CASCO, [0, 0, 10, 10]), (CASCO, [50, 50, 10, 10]), (CHALECO, [100, 0, 20, 30]))
    b = etiquetado(
        (CASCO, [0, 0, 10, 10]), (CHALECO, [50, 50, 10, 10]), (CHALECO, [100, 0, 20, 30])
    )

    informe = medir_acuerdo(a, b)

    casco, chaleco = informe.por_clase["casco"], informe.por_clase["chaleco"]
    assert (casco.cajas_a, casco.cajas_b, casco.coincidencias) == (2, 1, 1)
    assert casco.acuerdo == pytest.approx(2 / 3)
    assert chaleco.acuerdo == pytest.approx(2 / 3)
    assert casco.iou_medio == pytest.approx(1.0)


def test_medir_acuerdo_calcula_kappa_con_fondo_para_las_cajas_sin_pareja() -> None:
    a = etiquetado((CASCO, [0, 0, 10, 10]), (CASCO, [50, 50, 10, 10]))
    b = etiquetado((CASCO, [0, 0, 10, 10]), (CHALECO, [100, 100, 10, 10]), (CASCO, [200, 0, 9, 9]))

    informe = medir_acuerdo(a, b)

    # Pares: (casco, casco), (casco, fondo), (fondo, chaleco), (fondo, casco).
    # po = 1/4; pe = (2·2 + 2·1) / 16 = 3/8; kappa = (1/4 - 3/8) / (1 - 3/8) = -0,2.
    assert informe.kappa == pytest.approx(-0.2)


def test_medir_acuerdo_ignora_las_regiones_ignorar() -> None:
    a = etiquetado((CASCO, [0, 0, 4, 4]), (CASCO, [0, 0, 10, 10]), ignoradas=1)
    b = etiquetado((CASCO, [0, 0, 10, 10]))

    assert medir_acuerdo(a, b).por_clase["casco"].acuerdo == 1.0


def test_medir_acuerdo_de_una_clase_sin_cajas_no_tiene_valor() -> None:
    informe = medir_acuerdo(
        etiquetado((CASCO, [0, 0, 10, 10])), etiquetado((CASCO, [0, 0, 10, 10]))
    )

    assert informe.por_clase["persona"].acuerdo is None
    assert informe.por_clase["persona"].iou_medio is None


def test_medir_acuerdo_exige_las_mismas_imagenes_en_los_dos_etiquetados() -> None:
    b = etiquetado()
    b["images"] = [{"id": 7, "file_name": "cam-02_20261021_083005_0001.jpg"}]

    with pytest.raises(AcuerdoInvalidoError, match="mismas imágenes"):
        medir_acuerdo(etiquetado(), b)


def test_medir_acuerdo_exige_las_mismas_categorias() -> None:
    b = {**etiquetado(), "categories": categorias(("persona", "casco"))}

    with pytest.raises(AcuerdoInvalidoError, match="mismas categorías"):
        medir_acuerdo(etiquetado(), b)


def test_clases_bajo_el_umbral_falla_cerrada_si_no_hay_umbral_aprobado() -> None:
    informe = medir_acuerdo(
        etiquetado((CASCO, [0, 0, 10, 10])), etiquetado((CASCO, [0, 0, 10, 10]))
    )

    with pytest.raises(UmbralDeAcuerdoPendienteError, match="PENDIENTE"):
        clases_bajo_el_umbral(informe, None)


@pytest.mark.parametrize(
    ("umbral", "bajo"),
    [(0.5, ["persona", "cabeza"]), (0.51, ["persona", "cabeza", "casco"])],
)
def test_clases_bajo_el_umbral_incluye_las_que_no_llegan_y_las_que_no_tienen_cajas(
    umbral: float, bajo: list[str]
) -> None:
    a = etiquetado((CASCO, [0, 0, 10, 10]), (CASCO, [50, 50, 10, 10]), (CHALECO, [100, 0, 20, 30]))
    b = etiquetado((CASCO, [0, 0, 10, 10]), (CASCO, [200, 200, 9, 9]), (CHALECO, [100, 0, 20, 30]))

    assert clases_bajo_el_umbral(medir_acuerdo(a, b), umbral) == bajo
