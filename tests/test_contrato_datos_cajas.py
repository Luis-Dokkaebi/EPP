"""Contrato de datos: cajas, licencias de las fuentes y split sin fuga (SPEC/9 §2.3 y §2.4)."""

from typing import Any

import pytest

from ml.contrato_datos import (
    TAXONOMIA_V1,
    TAXONOMIA_V2,
    ContratoDeDatosError,
    ImagenDeSplit,
    categorias,
    validar_anotaciones,
    validar_licencia_de_fuente,
    validar_split,
)
from tests.coco_sintetico import ARCHIVO, LADO_MINIMO, caja, coco


def _violaciones(dataset: dict[str, Any]) -> list[str]:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_anotaciones(dataset, TAXONOMIA_V1, LADO_MINIMO)
    return error.value.violaciones


@pytest.mark.parametrize(
    "bbox",
    [[0, 0, 640, 480], [630, 470, 10, 10], [0, 0, 10, 10]],
    ids=["imagen-entera", "esquina-inferior", "esquina-superior"],
)
def test_validar_anotaciones_acepta_cajas_que_tocan_el_borde(bbox: list[float]) -> None:
    validar_anotaciones(coco(None, caja(bbox=bbox)), TAXONOMIA_V1, LADO_MINIMO)


@pytest.mark.parametrize(
    "bbox",
    [[-1, 0, 20, 20], [0, -1, 20, 20], [621, 0, 20, 20], [0, 461, 20, 20]],
    ids=["x-negativa", "y-negativa", "se-sale-a-la-derecha", "se-sale-abajo"],
)
def test_validar_anotaciones_rechaza_cajas_fuera_de_la_imagen(bbox: list[float]) -> None:
    assert _violaciones(coco(None, caja(bbox=bbox))) == [
        f"{ARCHIVO}: la caja 1 se sale de la imagen de 640x480."
    ]


@pytest.mark.parametrize(
    "bbox",
    [[0, 0, 0, 20], [0, 0, 20, 0], [0, 0, -5, 20], [0, 0, 20], "0,0,1,1", None],
    ids=["ancho-cero", "alto-cero", "ancho-negativo", "tres-valores", "texto", "ausente"],
)
def test_validar_anotaciones_rechaza_cajas_degeneradas(bbox: object) -> None:
    assert _violaciones(coco(None, caja(bbox=bbox))) == [
        f"{ARCHIVO}: la caja 1 no es [x, y, ancho, alto] con ancho y alto positivos."
    ]


@pytest.mark.parametrize("bbox", [[0, 0, 9.99, 40], [0, 0, 40, 0.5]], ids=["ancho", "alto"])
def test_validar_anotaciones_exige_ignorar_las_cajas_chicas(bbox: list[float]) -> None:
    assert _violaciones(coco(None, caja(bbox=bbox))) == [
        f"{ARCHIVO}: la caja 1 mide menos de {LADO_MINIMO} px de lado: márcala como región "
        "ignorar (iscrowd = 1)."
    ]


@pytest.mark.parametrize("lado", [LADO_MINIMO, 40.0])
def test_validar_anotaciones_acepta_cajas_desde_el_lado_minimo(lado: float) -> None:
    validar_anotaciones(coco(None, caja(bbox=[0, 0, 40, lado])), TAXONOMIA_V1, LADO_MINIMO)


@pytest.mark.parametrize("bbox", [[0, 0, 2, 2], [0, 0, 0.5, 40]], ids=["cuadrada", "fina"])
def test_validar_anotaciones_acepta_una_caja_chica_marcada_como_ignorar(bbox: list[float]) -> None:
    validar_anotaciones(coco(None, caja(bbox=bbox, iscrowd=1)), TAXONOMIA_V1, LADO_MINIMO)


def test_validar_anotaciones_acepta_la_categoria_uno_y_lados_menores_a_un_pixel() -> None:
    dataset = coco(None, caja(category_id=1, bbox=[0, 0, 0.5, 0.5]))

    validar_anotaciones(dataset, TAXONOMIA_V1, lado_minimo_px=0.5)


def test_validar_anotaciones_rechaza_cajas_con_valores_no_finitos() -> None:
    assert _violaciones(coco(None, caja(bbox=[float("nan"), 0, 10, 10]))) == [
        f"{ARCHIVO}: la caja 1 no es [x, y, ancho, alto] con ancho y alto positivos."
    ]


@pytest.mark.parametrize("lado_minimo", [0.0, -1.0, float("nan")])
def test_validar_anotaciones_exige_un_lado_minimo_positivo(lado_minimo: float) -> None:
    with pytest.raises(ValueError) as error:
        validar_anotaciones(coco(), TAXONOMIA_V1, lado_minimo)

    assert str(error.value) == f"El lado mínimo debe ser positivo; llegó {lado_minimo}."


@pytest.mark.parametrize("categoria", [0, 5, 99, "3"])
def test_validar_anotaciones_rechaza_categorias_desconocidas(categoria: object) -> None:
    assert _violaciones(coco(None, caja(category_id=categoria))) == [
        f"{ARCHIVO}: la caja 1 tiene la categoría {categoria}, que no está en la taxonomía."
    ]


def test_validar_anotaciones_rechaza_cajas_de_imagenes_inexistentes() -> None:
    assert _violaciones(coco(None, caja(image_id=2))) == [
        "La caja 1 apunta a la imagen 2, que no existe."
    ]


def test_validar_anotaciones_con_la_taxonomia_v2_acepta_sus_clases_nuevas() -> None:
    dataset = {**coco(None, caja(category_id=8)), "categories": categorias(TAXONOMIA_V2)}

    validar_anotaciones(dataset, TAXONOMIA_V2, LADO_MINIMO)


@pytest.mark.parametrize("licencia", ["propia-con-autorizacion", "CC-BY-4.0", "CC0-1.0", "MIT"])
def test_validar_licencia_de_fuente_acepta_las_licencias_comerciales(licencia: str) -> None:
    validar_licencia_de_fuente("Piloto planta 1", licencia)


@pytest.mark.parametrize(
    "licencia", ["CC-BY-NC-SA-4.0", "CC-BY-NC-4.0", "AGPL-3.0", "GPL-2.0", "SSPL-1.0", "PML-1.0"]
)
def test_validar_licencia_de_fuente_rechaza_las_licencias_prohibidas(licencia: str) -> None:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_licencia_de_fuente("Dataset X", licencia)

    assert error.value.violaciones == [
        f"Dataset X: la licencia {licencia} está prohibida para pesos que se distribuyen."
    ]


@pytest.mark.parametrize("licencia", ["", "LGPL-3.0", "Desconocida", "cc-by-4.0"])
def test_validar_licencia_de_fuente_pide_revision_humana_para_el_resto(licencia: str) -> None:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_licencia_de_fuente("Dataset X", licencia)

    assert error.value.violaciones == [
        f'Dataset X: la licencia "{licencia}" necesita revisión humana antes de usarse.'
    ]


@pytest.mark.parametrize("nombre", ["SH17", "sh17 (Pexels)", "Mi copia de SH17"])
def test_validar_licencia_de_fuente_rechaza_sh17_aunque_declare_otra_licencia(
    nombre: str,
) -> None:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_licencia_de_fuente(nombre, "CC-BY-4.0")

    assert error.value.violaciones == [
        f"{nombre}: SH17 no es apto para el producto (CC BY-NC-SA 4.0, SPEC/9 §2.3)."
    ]


SPLIT_VALIDO = [
    ImagenDeSplit("cam-01", "2026-10-01", "train"),
    ImagenDeSplit("cam-01", "2026-10-01", "train"),
    ImagenDeSplit("cam-01", "2026-10-02", "valid"),
    ImagenDeSplit("cam-02", "2026-10-01", "train"),
    ImagenDeSplit("cam-03", "2026-10-01", "test"),
]


def _violaciones_de_split(imagenes: list[ImagenDeSplit]) -> list[str]:
    with pytest.raises(ContratoDeDatosError) as error:
        validar_split(imagenes)
    return error.value.violaciones


def test_validar_split_acepta_cortes_por_camara_y_dia() -> None:
    validar_split(SPLIT_VALIDO)


def test_validar_split_rechaza_una_camara_y_dia_repartidos_en_dos_splits() -> None:
    imagenes = [*SPLIT_VALIDO, ImagenDeSplit("cam-01", "2026-10-01", "valid")]

    assert _violaciones_de_split(imagenes) == [
        "cam-01 del 2026-10-01 está en más de un split (train, valid): fuga de información."
    ]


def test_validar_split_exige_una_camara_reservada_solo_para_test() -> None:
    imagenes = [*SPLIT_VALIDO, ImagenDeSplit("cam-03", "2026-10-02", "valid")]

    assert _violaciones_de_split(imagenes) == [
        "Ninguna cámara está reservada solo para test (SPEC/9 §2.4)."
    ]


@pytest.mark.parametrize("vacio", ["train", "valid"])
def test_validar_split_exige_train_y_valid_con_imagenes(vacio: str) -> None:
    imagenes = [imagen for imagen in SPLIT_VALIDO if imagen.split != vacio]

    assert _violaciones_de_split(imagenes) == [f'El split "{vacio}" no tiene imágenes.']


def test_validar_split_rechaza_nombres_de_split_desconocidos() -> None:
    imagenes = [*SPLIT_VALIDO, ImagenDeSplit("cam-04", "2026-10-03", "val")]

    assert _violaciones_de_split(imagenes) == [
        'cam-04 del 2026-10-03: split desconocido "val" (válidos: train, valid, test).'
    ]


def test_validar_split_sin_imagenes_informa_cada_regla_incumplida() -> None:
    assert _violaciones_de_split([]) == [
        "Ninguna cámara está reservada solo para test (SPEC/9 §2.4).",
        'El split "train" no tiene imágenes.',
        'El split "valid" no tiene imágenes.',
        'El split "test" no tiene imágenes.',
    ]
