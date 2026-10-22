"""Anotaciones COCO sintéticas que cumplen el contrato de datos (docs/ml/contrato_datos.md)."""

from typing import Any

from ml.contrato_datos import TAXONOMIA_V1, categorias

ARCHIVO = "cam-01_20261021_083005_0001.jpg"


def imagen(**cambios: Any) -> dict[str, Any]:
    """Imagen de 640x480 con los metadatos de captura coherentes con su nombre."""
    base = {
        "id": 1,
        "file_name": ARCHIVO,
        "width": 640,
        "height": 480,
        "camara": "cam-01",
        "fecha": "2026-10-21",
        "hora": "08:30:05",
        "turno": "manana",
        "autorizacion": "AUT-2026-001",
    }
    return {**base, **cambios}


def caja(**cambios: Any) -> dict[str, Any]:
    """Caja de casco (categoría 3 de la taxonomía v1) de 30x40 px en la imagen 1."""
    base = {"id": 1, "image_id": 1, "category_id": 3, "bbox": [10, 20, 30, 40], "iscrowd": 0}
    return {**base, **cambios}


def coco(una_imagen: dict[str, Any] | None = None, *cajas: dict[str, Any]) -> dict[str, Any]:
    """COCO de una imagen; sin cajas explícitas lleva la caja por omisión."""
    return {
        "images": [una_imagen or imagen()],
        "annotations": list(cajas) or [caja()],
        "categories": categorias(TAXONOMIA_V1),
    }
