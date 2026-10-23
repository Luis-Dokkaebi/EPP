"""Contrato de datos del dataset EPP verificable por código (docs/ml/contrato_datos.md).

Valida un COCO ya normalizado: taxonomía y metadatos de captura de cada imagen.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

TAXONOMIA_V1 = ("persona", "cabeza", "casco", "chaleco")
TAXONOMIA_V2 = (*TAXONOMIA_V1, "manos", "guantes", "gafas", "barbijo")
METADATOS_DE_IMAGEN = ("camara", "fecha", "hora", "turno", "autorizacion")
SECCIONES_COCO = ("images", "annotations", "categories")
NOMBRE_DE_ARCHIVO = re.compile(
    r"(?P<camara>[a-z0-9-]+)_(?P<fecha>\d{8})_(?P<hora>\d{6})_\d{4}\.jpg"
)


class ContratoDeDatosError(ValueError):
    """El dataset incumple el contrato; `violaciones` las lista todas."""

    def __init__(self, violaciones: list[str]) -> None:
        self.violaciones = violaciones
        super().__init__("\n".join(["El dataset no cumple el contrato de datos:", *violaciones]))


def categorias(taxonomia: Sequence[str]) -> list[dict[str, Any]]:
    """Categorías COCO del contrato: ids desde 1 en el orden de la taxonomía."""
    return [{"id": indice, "name": nombre} for indice, nombre in enumerate(taxonomia, start=1)]


def validar_anotaciones(coco: Mapping[str, Any], taxonomia: Sequence[str]) -> None:
    """Lanza ContratoDeDatosError con todas las violaciones encontradas."""
    faltantes = [
        f'Falta la sección "{nombre}" del COCO.' for nombre in SECCIONES_COCO if nombre not in coco
    ]
    if faltantes:
        raise ContratoDeDatosError(faltantes)
    violaciones = _violaciones_de_categorias(coco["categories"], taxonomia)
    for imagen in coco["images"]:
        violaciones += _violaciones_de_imagen(imagen)
    if violaciones:
        raise ContratoDeDatosError(violaciones)


def _violaciones_de_categorias(exportadas: Any, taxonomia: Sequence[str]) -> list[str]:
    if exportadas == categorias(taxonomia):
        return []
    return [
        "Las categorías no son las de la taxonomía (ids desde 1, en orden): "
        f"{', '.join(taxonomia)}."
    ]


def _violaciones_de_imagen(imagen: Mapping[str, Any]) -> list[str]:
    nombre = imagen["file_name"]
    violaciones = [
        f'{nombre}: falta el metadato "{campo}".'
        for campo in METADATOS_DE_IMAGEN
        if not isinstance(imagen.get(campo), str) or not imagen[campo].strip()
    ]
    partes = NOMBRE_DE_ARCHIVO.fullmatch(nombre)
    if partes is None:
        return [
            *violaciones,
            f"{nombre}: el nombre no sigue <camara>_<AAAAMMDD>_<HHMMSS>_<nnnn>.jpg.",
        ]
    try:
        momento = datetime.strptime(partes["fecha"] + partes["hora"], "%Y%m%d%H%M%S")
    except ValueError:
        return [*violaciones, f"{nombre}: la fecha y hora del nombre no existen."]
    esperados = {
        "camara": partes["camara"],
        "fecha": momento.strftime("%Y-%m-%d"),
        "hora": momento.strftime("%H:%M:%S"),
    }
    return violaciones + [
        f'{nombre}: el metadato "{campo}" ({imagen[campo]}) no coincide con el nombre del archivo.'
        for campo, esperado in esperados.items()
        if campo in imagen and imagen[campo] != esperado
    ]
