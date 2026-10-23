"""Adaptador de RF-DETR detrás de EntrenadorPort, con un doble del paquete (SPEC/9 §3.1).

Ninguna prueba importa rfdetr, entrena ni descarga pesos: el paquete se inyecta como un doble.
"""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ml.entrenador_rfdetr import ARCHIVO_DE_PESOS, EntrenadorRfDetr, preparar_dataset
from ml.manifiesto_dataset import ARCHIVO_DE_ANOTACIONES
from ml.train import EntrenamientoInvalidoError
from tests.test_train import _config, _dataset_versionado

ANOTACIONES_RFDETR = "_annotations.coco.json"


class ModeloFalso:
    """Doble de una clase de rfdetr (RFDETRSmall, ...): guarda los argumentos y deja pesos."""

    def __init__(self) -> None:
        self.argumentos: dict[str, Any] = {}

    def train(self, **argumentos: Any) -> None:
        self.argumentos = argumentos
        (Path(argumentos["output_dir"]) / ARCHIVO_DE_PESOS).write_bytes(b"pesos")


class ModeloSinPesos(ModeloFalso):
    def train(self, **argumentos: Any) -> None:
        self.argumentos = argumentos


class PaqueteFalso:
    """Doble del paquete rfdetr: registra qué se importó y qué modelos se crearon."""

    def __init__(self, clase: str, modelo: type[ModeloFalso] = ModeloFalso) -> None:
        self.importados: list[str] = []
        self.modelos: list[ModeloFalso] = []
        self._clase = clase
        self._modelo = modelo

    def importar(self, nombre: str) -> SimpleNamespace:
        self.importados.append(nombre)
        return SimpleNamespace(**{self._clase: self._crear})

    def _crear(self) -> ModeloFalso:
        self.modelos.append(self._modelo())
        return self.modelos[-1]


def _leer(ruta: Path) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _artefacto(carpeta: Path) -> Path:
    _dataset_versionado(carpeta)
    artefacto = carpeta / "artefacto"
    artefacto.mkdir()
    return artefacto


def test_preparar_dataset_reparte_imagenes_por_split(tmp_path: Path) -> None:
    manifiesto = _dataset_versionado(tmp_path)
    destino = tmp_path / "rfdetr"

    preparar_dataset(tmp_path, manifiesto, destino)

    entrenamiento = _leer(destino / "train" / ANOTACIONES_RFDETR)
    assert [imagen["file_name"] for imagen in entrenamiento["images"]] == [
        "cam-01_20261001_083005_0001.jpg",
        "cam-02_20261001_083005_0001.jpg",
    ]
    assert entrenamiento["categories"][0] == {"id": 1, "name": "persona"}
    assert sorted(ruta.name for ruta in (destino / "test").iterdir()) == [
        ANOTACIONES_RFDETR,
        "cam-03_20261002_083005_0001.jpg",
    ]
    assert (destino / "valid" / "cam-01_20261002_083005_0001.jpg").read_bytes() == b"imagen 2"


def test_preparar_dataset_lleva_cada_caja_al_split_de_su_imagen(tmp_path: Path) -> None:
    manifiesto = _dataset_versionado(tmp_path)
    coco = _leer(tmp_path / ARCHIVO_DE_ANOTACIONES)
    caja = {"id": 1, "image_id": 4, "category_id": 3, "bbox": [1, 1, 20, 20], "iscrowd": 0}
    coco["annotations"] = [caja]
    (tmp_path / ARCHIVO_DE_ANOTACIONES).write_text(json.dumps(coco), encoding="utf-8")

    preparar_dataset(tmp_path, manifiesto, tmp_path / "rfdetr")

    cajas = [
        _leer(tmp_path / "rfdetr" / split / ANOTACIONES_RFDETR)["annotations"]
        for split in ("train", "valid", "test")
    ]
    assert cajas == [[], [], [caja]]


@pytest.mark.parametrize(
    ("tamano", "clase"),
    [
        ("nano", "RFDETRNano"),
        ("small", "RFDETRSmall"),
        ("medium", "RFDETRMedium"),
        ("large", "RFDETRLarge"),
    ],
)
def test_entrenador_usa_la_clase_de_rfdetr_de_cada_tamano(
    tmp_path: Path, tamano: str, clase: str
) -> None:
    paquete = PaqueteFalso(clase)
    artefacto = _artefacto(tmp_path)

    resultado = EntrenadorRfDetr(paquete.importar).entrenar(
        _config(tmp_path, tamano=tamano), artefacto
    )

    assert (paquete.importados, len(paquete.modelos)) == (["rfdetr"], 1)
    assert resultado.pesos == artefacto / ARCHIVO_DE_PESOS
    assert resultado.metricas == {}


def test_entrenador_pasa_los_hiperparametros_y_el_dataset_preparado(tmp_path: Path) -> None:
    paquete = PaqueteFalso("RFDETRSmall")
    artefacto = _artefacto(tmp_path)

    EntrenadorRfDetr(paquete.importar).entrenar(_config(tmp_path), artefacto)

    assert paquete.modelos[0].argumentos == {
        "dataset_dir": str(artefacto / "dataset"),
        "output_dir": str(artefacto),
        "epochs": 2,
        "batch_size": 4,
        "lr": 1e-4,
        "resolution": 512,
        "seed": 7,
    }
    assert (artefacto / "dataset" / "train" / ANOTACIONES_RFDETR).is_file()


def test_entrenador_falla_si_rfdetr_no_deja_los_pesos(tmp_path: Path) -> None:
    paquete = PaqueteFalso("RFDETRSmall", ModeloSinPesos)
    artefacto = _artefacto(tmp_path)

    with pytest.raises(EntrenamientoInvalidoError) as error:
        EntrenadorRfDetr(paquete.importar).entrenar(_config(tmp_path), artefacto)

    assert str(error.value) == f"RF-DETR terminó sin dejar {artefacto / ARCHIVO_DE_PESOS}."


def test_entrenador_importa_el_paquete_real_por_omision_y_solo_al_entrenar() -> None:
    assert EntrenadorRfDetr().importar is importlib.import_module
