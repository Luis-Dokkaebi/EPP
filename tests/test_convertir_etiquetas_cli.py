"""Línea de comandos de la conversión de etiquetas (docs/runbooks/etiquetado.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ml.contrato_datos import TAXONOMIA_V1, TAXONOMIA_V2, TAXONOMIAS
from ml.convertir_etiquetas import main
from ml.manifiesto_dataset import ARCHIVO_DE_ANOTACIONES
from tests.test_convertir_etiquetas import METADATOS, _anotacion, _exportado
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS

INVALIDO = 2


def _argumentos(carpeta: Path, exportado: dict[str, object], metadatos: str) -> list[str]:
    ruta_exportado = carpeta / "cvat.json"
    ruta_exportado.write_text(json.dumps(exportado), encoding="utf-8")
    ruta_metadatos = carpeta / "metadatos.jsonl"
    ruta_metadatos.write_text(metadatos, encoding="utf-8")
    return [
        *("--exportado", str(ruta_exportado), "--metadatos", str(ruta_metadatos)),
        *("--taxonomia", "v1", "--salida", str(carpeta / "dataset" / ARCHIVO_DE_ANOTACIONES)),
    ]


def test_taxonomias_por_version() -> None:
    assert TAXONOMIAS == {"v1": TAXONOMIA_V1, "v2": TAXONOMIA_V2}


def test_main_escribe_el_coco_del_contrato(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(tmp_path, _exportado(_anotacion()), json.dumps(METADATOS) + "\n\n")

    codigo = main(argumentos)

    salida = tmp_path / "dataset" / ARCHIVO_DE_ANOTACIONES
    convertido = json.loads(salida.read_text(encoding="utf-8"))
    assert codigo == 0
    assert [caja["category_id"] for caja in convertido["annotations"]] == [3]
    assert capsys.readouterr().out == f"1 imágenes y 1 cajas convertidas en {salida}\n"


def test_main_informa_el_error_y_no_escribe_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main(_argumentos(tmp_path, _exportado(), ""))

    assert codigo == INVALIDO
    assert capsys.readouterr().err.startswith("cam-01_20261021_083005_0001.jpg no tiene metadatos")
    assert not (tmp_path / "dataset").exists()


@pytest.mark.parametrize("falta", ["--exportado", "--metadatos", "--taxonomia", "--salida"])
def test_main_exige_cada_parametro(tmp_path: Path, falta: str) -> None:
    argumentos = _argumentos(tmp_path, _exportado(), "")
    posicion = argumentos.index(falta)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "ml.convertir_etiquetas", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "COCO exportado por CVAT o Label Studio" in resultado.stdout
