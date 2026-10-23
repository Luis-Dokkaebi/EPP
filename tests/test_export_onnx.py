"""Exportación del modelo EPP a ONNX y su entrada de manifiesto (SPEC/9 §3.6 y §3.7).

rfdetr se reemplaza por un doble: ninguna prueba exporta un modelo real ni descarga pesos.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ml.export_onnx import (
    OPSET,
    ExportacionInvalidaError,
    ExportadorRfDetr,
    entrada_de_manifiesto,
    main,
)
from tests.test_train import SHA_CODIGO
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS, textos_ausentes

INVALIDO = 2
REGISTRO = {
    "artefacto": "epp-0123456789ab-ffffffffffff",
    "sha_codigo": SHA_CODIGO,
    "config": {"tamano": "small", "resolucion": 512},
    "dataset_version": "v0.1",
    "dataset_huella": "d" * 64,
    "pesos": "checkpoint_best_total.pth",
}
MANIFIESTO_DEL_DATASET = {
    "taxonomia": ["persona", "cabeza", "casco", "chaleco"],
    "fuentes": [{"nombre": "Planta Ñandú", "licencia": "propia-con-autorizacion"}],
}


class ModeloFalso:
    """Doble de rfdetr.RFDETRSmall: guarda cómo se creó y escribe un ONNX falso al exportar."""

    def __init__(self, **argumentos: Any) -> None:
        self.creado_con = argumentos
        self.exportado_con: dict[str, Any] = {}

    def export(self, **argumentos: Any) -> Path:
        self.exportado_con = argumentos
        ruta = Path(argumentos["output_dir"]) / "inference_model.onnx"
        ruta.write_bytes(b"onnx falso")
        return ruta


class ModeloQueNoEscribe(ModeloFalso):
    def export(self, **argumentos: Any) -> Path:
        self.exportado_con = argumentos
        return Path(argumentos["output_dir"]) / "inference_model.onnx"


class PaqueteFalso:
    def __init__(self, modelo: type[ModeloFalso] = ModeloFalso) -> None:
        self.modelos: list[ModeloFalso] = []
        self._modelo = modelo

    def importar(self, nombre: str) -> SimpleNamespace:
        assert nombre == "rfdetr"
        return SimpleNamespace(RFDETRSmall=self._crear, RFDETRNano=self._crear)

    def _crear(self, **argumentos: Any) -> ModeloFalso:
        self.modelos.append(self._modelo(**argumentos))
        return self.modelos[-1]


def test_exportar_carga_los_pesos_entrenados_y_exporta_onnx_opset_17(tmp_path: Path) -> None:
    paquete = PaqueteFalso()
    pesos = tmp_path / "checkpoint_best_total.pth"

    ruta = ExportadorRfDetr(paquete.importar).exportar(pesos, "small", 512, tmp_path)

    [modelo] = paquete.modelos
    assert modelo.creado_con == {"pretrain_weights": str(pesos)}
    assert modelo.exportado_con == {
        "output_dir": str(tmp_path),
        "opset_version": OPSET,
        "shape": (512, 512),
        "format": "onnx",
    }
    assert (ruta, OPSET) == (tmp_path / "inference_model.onnx", 17)


def test_exportar_falla_si_no_queda_el_onnx(tmp_path: Path) -> None:
    paquete = PaqueteFalso(ModeloQueNoEscribe)

    with pytest.raises(ExportacionInvalidaError) as error:
        ExportadorRfDetr(paquete.importar).exportar(tmp_path / "p.pth", "nano", 384, tmp_path)

    assert str(error.value) == (f"RF-DETR no dejó el ONNX en {tmp_path / 'inference_model.onnx'}.")


def test_exportar_usa_el_paquete_real_por_omision() -> None:
    import importlib

    assert ExportadorRfDetr().importar is importlib.import_module


def test_entrada_de_manifiesto_declara_hash_licencias_datasets_y_clases(tmp_path: Path) -> None:
    onnx = tmp_path / "inference_model.onnx"
    onnx.write_bytes(b"onnx falso")

    entrada = entrada_de_manifiesto(
        onnx, REGISTRO, MANIFIESTO_DEL_DATASET, "0.1.0", "models/epp/epp-0.1.0.onnx"
    )

    assert entrada == {
        "nombre": "epp",
        "version": "0.1.0",
        "archivo": "models/epp/epp-0.1.0.onnx",
        "sha256": hashlib.sha256(b"onnx falso").hexdigest(),
        "motor": "onnxruntime",
        "licencia_pesos": "Apache-2.0",
        "licencia_codigo_entrenamiento": "Apache-2.0",
        "datasets": [{"nombre": "Planta Ñandú", "licencia": "propia-con-autorizacion"}],
        "clases": {"1": "persona", "2": "cabeza", "3": "casco", "4": "chaleco"},
        "tamano_entrada": [512, 512],
        "origen": (
            "RF-DETR small ajustado con el dataset v0.1 (huella dddddddddddd), artefacto "
            "epp-0123456789ab-ffffffffffff, código 0123456789ab."
        ),
    }


@pytest.mark.parametrize(
    "archivo", ["epp.onnx", "models/epp.pt", "/abs/models/epp.onnx", "models/../epp.onnx"]
)
def test_entrada_de_manifiesto_exige_un_onnx_dentro_de_models(tmp_path: Path, archivo: str) -> None:
    with pytest.raises(ExportacionInvalidaError) as error:
        entrada_de_manifiesto(tmp_path, REGISTRO, MANIFIESTO_DEL_DATASET, "0.1.0", archivo)

    assert str(error.value) == f'"{archivo}" inválido: usa models/<carpeta>/<nombre>.onnx.'


def _archivos(carpeta: Path) -> list[str]:
    registro = carpeta / "registro.json"
    registro.write_text(json.dumps(REGISTRO), encoding="utf-8")
    (carpeta / "checkpoint_best_total.pth").write_bytes(b"pesos")
    dataset = carpeta / "manifest.json"
    dataset.write_text(json.dumps(MANIFIESTO_DEL_DATASET), encoding="utf-8")
    return [
        *("--registro", str(registro), "--manifiesto-dataset", str(dataset)),
        *("--version", "0.1.0", "--archivo", "models/epp/epp-0.1.0.onnx"),
    ]


def test_main_exporta_e_imprime_la_entrada_para_el_manifiesto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paquete = PaqueteFalso()

    codigo = main(_archivos(tmp_path), importar=paquete.importar)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert paquete.modelos[0].creado_con == {
        "pretrain_weights": str(tmp_path / "checkpoint_best_total.pth")
    }
    assert json.loads(salida)["sha256"] == hashlib.sha256(b"onnx falso").hexdigest()
    assert salida.startswith('{\n  "nombre": "epp",')
    assert "Planta Ñandú" in salida


def test_main_informa_un_archivo_destino_invalido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _archivos(tmp_path)
    argumentos[-1] = "epp.onnx"

    codigo = main(argumentos, importar=PaqueteFalso().importar)

    assert codigo == INVALIDO
    assert capsys.readouterr().err == '"epp.onnx" inválido: usa models/<carpeta>/<nombre>.onnx.\n'


@pytest.mark.parametrize("falta", ["--registro", "--manifiesto-dataset", "--version", "--archivo"])
def test_main_exige_cada_parametro(tmp_path: Path, falta: str) -> None:
    argumentos = _archivos(tmp_path)
    posicion = argumentos.index(falta)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


def test_main_explica_los_parametros(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    textos = (
        "registro.json del artefacto",
        "manifest.json del dataset",
        "models/<carpeta>/<nombre>.onnx",
        "versión del modelo, p. ej. 0.1.0",
    )
    assert textos_ausentes(capsys.readouterr().out, textos) == []


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "ml.export_onnx", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "Exportación del modelo EPP a ONNX" in resultado.stdout
