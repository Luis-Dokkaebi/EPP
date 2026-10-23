"""Adaptador de RF-DETR (Apache-2.0) a EntrenadorPort (SPEC/9 §3.1, B-04).

`rfdetr` solo existe en el entorno de ml/requirements-ml.txt: se importa al entrenar, a través de
un importador inyectable, así las pruebas usan un doble y nadie descarga pesos. RF-DETR espera el
dataset en formato COCO con las carpetas train/, valid/ y test/, cada una con sus imágenes y un
`_annotations.coco.json`; `preparar_dataset` lo arma a partir del dataset versionado.
"""

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ml.contrato_datos import SPLITS
from ml.manifiesto_dataset import ARCHIVO_DE_ANOTACIONES
from ml.train import (
    ARCHIVO_DE_REGISTRO,
    ConfigEntrenamiento,
    EntrenadorPort,
    EntrenamientoInvalidoError,
    ResultadoDelEntrenador,
    entrenar,
)

RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[1]
CODIGO_INVALIDO = 2

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


def sha_del_codigo(raiz: Path, ejecutar: Callable[..., Any] = subprocess.run) -> str:
    """SHA del commit actual; falla si hay cambios sin commitear (el SHA no los describiría)."""
    base = ["git", "-C", str(raiz)]
    opciones = {"capture_output": True, "text": True, "check": True}
    if ejecutar([*base, "status", "--porcelain", "--untracked-files=no"], **opciones).stdout:
        raise EntrenamientoInvalidoError(
            "Hay cambios sin commitear: el SHA no describiría el código que entrena. Commitea o "
            "descarta los cambios y vuelve a correr."
        )
    return str(ejecutar([*base, "rev-parse", "HEAD"], **opciones).stdout.strip())


def _analizar(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, type=Path, help="dataset versionado")
    parser.add_argument("--manifiesto", required=True, type=Path, help="su manifest.json")
    parser.add_argument("--tamano", required=True, help="nano, small, medium o large (Apache-2.0)")
    parser.add_argument("--resolucion", required=True, type=int, help="múltiplo de 32")
    parser.add_argument("--epocas", required=True, type=int)
    parser.add_argument("--lote", required=True, type=int)
    parser.add_argument("--tasa", required=True, type=float, help="tasa de aprendizaje")
    parser.add_argument("--semilla", required=True, type=int)
    parser.add_argument(
        "--salidas", required=True, type=Path, help="carpeta de artefactos, fuera de git"
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    crear_entrenador: Callable[[], EntrenadorPort] = EntrenadorRfDetr,
    sha: Callable[[], str] | None = None,
) -> int:
    argumentos = _analizar(argv)
    try:
        config = ConfigEntrenamiento(
            dataset=argumentos.dataset,
            manifiesto=argumentos.manifiesto,
            tamano=argumentos.tamano,
            resolucion=argumentos.resolucion,
            epocas=argumentos.epocas,
            lote=argumentos.lote,
            tasa_de_aprendizaje=argumentos.tasa,
            semilla=argumentos.semilla,
        )
        sha_codigo = sha() if sha else sha_del_codigo(RAIZ_DEL_REPOSITORIO)
        registro = entrenar(config, crear_entrenador(), sha_codigo, argumentos.salidas)
    except EntrenamientoInvalidoError as error:
        sys.stderr.write(f"{error}\n")
        return CODIGO_INVALIDO
    destino = argumentos.salidas / registro["artefacto"]
    sys.stdout.write(f"Artefacto {registro['artefacto']}: {destino / ARCHIVO_DE_REGISTRO}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
