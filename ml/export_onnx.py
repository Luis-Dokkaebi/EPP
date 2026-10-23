"""Exportación del modelo EPP a ONNX y su entrada en models/manifest.json (SPEC/9 §3.6, §3.7).

`rfdetr` se importa solo al exportar, con un importador inyectable (las pruebas usan un doble).
El ONNX sale con opset 17 y la resolución del entrenamiento; antes de declararlo en el manifiesto
hay que probar la paridad (ml/paridad.py) y completar la ficha del modelo
(docs/ml/ficha_modelo_plantilla.md). Procedimiento: docs/runbooks/exportacion_modelo.md.
"""

import argparse
import importlib
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ml.entrenador_rfdetr import CLASES_POR_TAMANO
from ml.manifiesto_dataset import sha256_de

OPSET = 17
ARCHIVO_EN_MODELS = re.compile(r"models/(?:[a-z0-9_-]+/)+[a-z0-9_.-]+\.onnx")
CARACTERES_DE_HUELLA = 12
CODIGO_INVALIDO = 2


class ExportacionInvalidaError(ValueError):
    """La exportación o su entrada de manifiesto no cumplen el contrato."""


class ExportadorRfDetr:
    def __init__(self, importar: Callable[[str], Any] = importlib.import_module) -> None:
        self.importar = importar

    def exportar(self, pesos: Path, tamano: str, resolucion: int, carpeta: Path) -> Path:
        rfdetr = self.importar("rfdetr")
        modelo = getattr(rfdetr, CLASES_POR_TAMANO[tamano])(pretrain_weights=str(pesos))
        ruta = Path(
            modelo.export(
                output_dir=str(carpeta),
                opset_version=OPSET,
                shape=(resolucion, resolucion),
                format="onnx",
            )
        )
        if not ruta.is_file():
            raise ExportacionInvalidaError(f"RF-DETR no dejó el ONNX en {ruta}.")
        return ruta


def entrada_de_manifiesto(
    onnx: Path,
    registro: Mapping[str, Any],
    manifiesto_dataset: Mapping[str, Any],
    version: str,
    archivo: str,
) -> dict[str, Any]:
    """Entrada para models/manifest.json; las clases usan los IDs de la taxonomía del dataset."""
    if ARCHIVO_EN_MODELS.fullmatch(archivo) is None:
        raise ExportacionInvalidaError(f'"{archivo}" inválido: usa models/<carpeta>/<nombre>.onnx.')
    resolucion = registro["config"]["resolucion"]
    return {
        "nombre": "epp",
        "version": version,
        "archivo": archivo,
        "sha256": sha256_de(onnx),
        "motor": "onnxruntime",
        "licencia_pesos": "Apache-2.0",
        "licencia_codigo_entrenamiento": "Apache-2.0",
        "datasets": [
            {"nombre": fuente["nombre"], "licencia": fuente["licencia"]}
            for fuente in manifiesto_dataset["fuentes"]
        ],
        "clases": {
            str(indice): clase
            for indice, clase in enumerate(manifiesto_dataset["taxonomia"], start=1)
        },
        "tamano_entrada": [resolucion, resolucion],
        "origen": (
            f"RF-DETR {registro['config']['tamano']} ajustado con el dataset "
            f"{registro['dataset_version']} (huella "
            f"{registro['dataset_huella'][:CARACTERES_DE_HUELLA]}), artefacto "
            f"{registro['artefacto']}, código {registro['sha_codigo'][:CARACTERES_DE_HUELLA]}."
        ),
    }


def main(
    argv: Sequence[str] | None = None,
    importar: Callable[[str], Any] = importlib.import_module,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registro", required=True, type=Path, help="registro.json del artefacto")
    parser.add_argument(
        "--manifiesto-dataset", required=True, type=Path, help="manifest.json del dataset"
    )
    parser.add_argument("--version", required=True, help="versión del modelo, p. ej. 0.1.0")
    parser.add_argument("--archivo", required=True, help="models/<carpeta>/<nombre>.onnx")
    argumentos = parser.parse_args(argv)
    registro = json.loads(argumentos.registro.read_text(encoding="utf-8"))
    dataset = json.loads(argumentos.manifiesto_dataset.read_text(encoding="utf-8"))
    carpeta = argumentos.registro.parent
    try:
        onnx = ExportadorRfDetr(importar).exportar(
            carpeta / registro["pesos"],
            registro["config"]["tamano"],
            registro["config"]["resolucion"],
            carpeta,
        )
        entrada = entrada_de_manifiesto(
            onnx, registro, dataset, argumentos.version, argumentos.archivo
        )
    except ExportacionInvalidaError as error:
        sys.stderr.write(f"{error}\n")
        return CODIGO_INVALIDO
    sys.stdout.write(json.dumps(entrada, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
