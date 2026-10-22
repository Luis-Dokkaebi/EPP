"""Del COCO exportado por CVAT o Label Studio al COCO del contrato de datos (SPEC/9 §3.1, B-03).

Traduce las etiquetas por nombre a los IDs de la taxonomía, marca como región "ignorar" lo que el
etiquetador ignoró (iscrowd o atributo "ignorar") y agrega a cada imagen sus metadatos de captura
(metadatos.jsonl de tools/capturar_dataset.py). Una imagen sin metadatos no tiene autorización
registrada y se rechaza.
"""

from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from ml.contrato_datos import categorias

# True también cubre al entero 1: en Python True == 1 y ambos tienen el mismo hash.
VERDADEROS = frozenset({True, "true", "True", "1"})


class ConversionInvalidaError(ValueError):
    """El etiquetado exportado no se puede llevar al contrato de datos."""


def convertir(
    exportado: Mapping[str, Any], metadatos: Iterable[Mapping[str, Any]], taxonomia: Sequence[str]
) -> dict[str, Any]:
    ids_de_clase = _ids_de_clase(exportado, taxonomia)
    por_nombre = {registro["file_name"]: registro for registro in metadatos}
    exportadas = sorted(exportado["images"], key=lambda imagen: _nombre(imagen["file_name"]))
    nuevo_id = {imagen["id"]: indice for indice, imagen in enumerate(exportadas, start=1)}
    imagenes = [_imagen(imagen, por_nombre, nuevo_id[imagen["id"]]) for imagen in exportadas]
    cajas = sorted(
        exportado["annotations"], key=lambda caja: (nuevo_id[caja["image_id"]], caja["id"])
    )
    anotaciones = [
        _anotacion(caja, indice, nuevo_id[caja["image_id"]], ids_de_clase)
        for indice, caja in enumerate(cajas, start=1)
    ]
    return {"images": imagenes, "annotations": anotaciones, "categories": categorias(taxonomia)}


def _ids_de_clase(exportado: Mapping[str, Any], taxonomia: Sequence[str]) -> dict[int, int]:
    """ID exportado -> ID de la taxonomía; una etiqueta ajena solo falla si alguna caja la usa."""
    nombres = {categoria["id"]: categoria["name"] for categoria in exportado["categories"]}
    usadas = {caja["category_id"] for caja in exportado["annotations"]}
    ajenas = sorted(nombres[usada] for usada in usadas if nombres[usada] not in taxonomia)
    if ajenas:
        raise ConversionInvalidaError(
            f'Etiqueta "{ajenas[0]}" fuera de la taxonomía ({", ".join(taxonomia)}): '
            "renómbrala en la herramienta de etiquetado (docs/ml/guia_etiquetado.md §1)."
        )
    return {
        identificador: taxonomia.index(nombre) + 1
        for identificador, nombre in nombres.items()
        if nombre in taxonomia
    }


def _nombre(ruta: str) -> str:
    return PurePosixPath(ruta.replace("\\", "/")).name


def _imagen(
    exportada: Mapping[str, Any], metadatos: Mapping[str, Mapping[str, Any]], nuevo_id: int
) -> dict[str, Any]:
    nombre = _nombre(exportada["file_name"])
    captura = metadatos.get(nombre)
    if captura is None:
        raise ConversionInvalidaError(
            f"{nombre} no tiene metadatos de captura: solo entran imágenes capturadas con "
            "tools/capturar_dataset.py y su autorización."
        )
    for campo in ("width", "height"):
        if exportada[campo] != captura[campo]:
            raise ConversionInvalidaError(
                f'{nombre}: "{campo}" ({exportada[campo]}) no coincide con la captura '
                f"({captura[campo]})."
            )
    return {**captura, "id": nuevo_id}


def _anotacion(
    caja: Mapping[str, Any], nuevo_id: int, imagen: int, ids_de_clase: Mapping[int, int]
) -> dict[str, Any]:
    ignorada = caja.get("iscrowd") == 1 or caja.get("attributes", {}).get("ignorar") in VERDADEROS
    return {
        "id": nuevo_id,
        "image_id": imagen,
        "category_id": ids_de_clase[caja["category_id"]],
        "bbox": list(caja["bbox"]),
        "area": caja["area"],
        "iscrowd": 1 if ignorada else 0,
    }
