"""Adaptador de RF-DETR (Apache-2.0) a EntrenadorPort (SPEC/9 §3.1, B-04).

`rfdetr` solo existe en el entorno de ml/requirements-ml.txt: se importa al entrenar, a través de
un importador inyectable, así las pruebas usan un doble y nadie descarga pesos. RF-DETR espera el
dataset en formato COCO con las carpetas train/, valid/ y test/, cada una con sus imágenes y un
`_annotations.coco.json`; `preparar_dataset` lo arma a partir del dataset versionado.
"""

import importlib
import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ml.contrato_datos import SPLITS
from ml.manifiesto_dataset import ARCHIVO_DE_ANOTACIONES
from ml.train import ConfigEntrenamiento, EntrenamientoInvalidoError, ResultadoDelEntrenador

CLASES_POR_TAMANO = {
    "nano": "RFDETRNano",
    "small": "RFDETRSmall",
    "medium": "RFDETRMedium",
    "large": "RFDETRLarge",
}
ANOTACIONES_RFDETR = "_annotations.coco.json"
ARCHIVO_DE_PESOS = "checkpoint_best_total.pth"  # nombre que deja rfdetr 1.11.2 al entrenar


def preparar_dataset(dataset: Path, manifiesto: Mapping[str, Any], destino: Path) -> None:
    """Copia cada imagen a la carpeta de su split y reparte las cajas con ella."""
    coco = json.loads((dataset / ARCHIVO_DE_ANOTACIONES).read_text(encoding="utf-8"))
    split_de = {imagen["file_name"]: imagen["split"] for imagen in manifiesto["imagenes"]}
    for split in SPLITS:
        imagenes = [imagen for imagen in coco["images"] if split_de[imagen["file_name"]] == split]
        ids = {imagen["id"] for imagen in imagenes}
        carpeta = destino / split
        carpeta.mkdir(parents=True)
        for imagen in imagenes:
            shutil.copy2(dataset / imagen["file_name"], carpeta / imagen["file_name"])
        contenido = {
            "images": imagenes,
            "annotations": [caja for caja in coco["annotations"] if caja["image_id"] in ids],
            "categories": coco["categories"],
        }
        (carpeta / ANOTACIONES_RFDETR).write_text(json.dumps(contenido), encoding="utf-8")


class EntrenadorRfDetr:
    def __init__(self, importar: Callable[[str], Any] = importlib.import_module) -> None:
        self.importar = importar

    def entrenar(self, config: ConfigEntrenamiento, carpeta: Path) -> ResultadoDelEntrenador:
        """Entrena en `carpeta`; las métricas por caja quedan en los registros de RF-DETR."""
        manifiesto = json.loads(config.manifiesto.read_text(encoding="utf-8"))
        datos = carpeta / "dataset"
        preparar_dataset(config.dataset, manifiesto, datos)
        rfdetr = self.importar("rfdetr")
        modelo = getattr(rfdetr, CLASES_POR_TAMANO[config.tamano])()
        modelo.train(
            dataset_dir=str(datos),
            output_dir=str(carpeta),
            epochs=config.epocas,
            batch_size=config.lote,
            lr=config.tasa_de_aprendizaje,
            resolution=config.resolucion,
            seed=config.semilla,
        )
        pesos = carpeta / ARCHIVO_DE_PESOS
        if not pesos.is_file():
            raise EntrenamientoInvalidoError(f"RF-DETR terminó sin dejar {pesos}.")
        return ResultadoDelEntrenador(pesos=pesos, metricas={})
