"""Línea de comandos del manifiesto del dataset (docs/runbooks/etiquetado.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ml.manifiesto_dataset import huella_del_manifiesto, main
from tests.test_manifiesto_dataset import _dataset
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS

CAMBIADO, INVALIDO = 1, 2
FUENTE = "Piloto planta 1=propia-con-autorizacion"
LADO_MINIMO = 10.0


def _crear(carpeta: Path, *extra: str) -> list[str]:
    return [
        "crear",
        *("--carpeta", str(carpeta), "--version", "v0.1", "--taxonomia", "v1"),
        *("--lado-minimo", str(LADO_MINIMO), "--fuente", FUENTE),
        *("--camara-test", "cam-03", "--dia-valid", "2026-10-02"),
        *("--salida", str(carpeta / "manifest.json")),
        *extra,
    ]


def _verificar(carpeta: Path) -> list[str]:
    return ["verificar", "--carpeta", str(carpeta), "--manifiesto", str(carpeta / "manifest.json")]


def test_crear_guarda_el_manifiesto_y_muestra_su_huella(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = _dataset(tmp_path)

    codigo = main(_crear(carpeta))

    manifiesto = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert manifiesto["fuentes"] == [
        {"nombre": "Piloto planta 1", "licencia": "propia-con-autorizacion"}
    ]
    assert manifiesto["regla_de_split"]["camaras_de_test"] == ["cam-03"]
    assert manifiesto["lado_minimo_px"] == LADO_MINIMO
    assert capsys.readouterr().out == (
        f"Dataset v0.1: train 2, valid 1, test 1. Huella: {huella_del_manifiesto(manifiesto)}\n"
    )


def test_crear_informa_la_violacion_y_no_guarda_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = _dataset(tmp_path)

    codigo = main(_crear(carpeta, "--fuente", "SH17=CC-BY-4.0"))

    assert codigo == INVALIDO
    assert capsys.readouterr().err == (
        "El dataset no cumple el contrato de datos:\n"
        "SH17: SH17 no es apto para el producto (CC BY-NC-SA 4.0, SPEC/9 §2.3).\n"
    )
    assert not (carpeta / "manifest.json").exists()


@pytest.mark.parametrize("fuente", ["sin-signo-igual", "=MIT"])
def test_crear_exige_fuentes_con_nombre_igual_licencia(tmp_path: Path, fuente: str) -> None:
    argumentos = _crear(_dataset(tmp_path))
    argumentos[argumentos.index(FUENTE)] = fuente

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


@pytest.mark.parametrize(
    "falta",
    ["--carpeta", "--version", "--taxonomia", "--lado-minimo", "--fuente", "--salida"],
)
def test_crear_exige_cada_parametro(tmp_path: Path, falta: str) -> None:
    argumentos = _crear(tmp_path)
    posicion = argumentos.index(falta)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


def test_verificar_aprueba_un_dataset_intacto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = _dataset(tmp_path)
    main(_crear(carpeta))
    capsys.readouterr()

    codigo = main(_verificar(carpeta))

    assert codigo == 0
    assert capsys.readouterr().out == "El dataset coincide con el manifiesto.\n"


def test_verificar_lista_las_diferencias(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = _dataset(tmp_path)
    main(_crear(carpeta))
    (carpeta / "cam-01_20261001_083005_0001.jpg").write_bytes(b"cambiada")
    (carpeta / "cam-02_20261001_083005_0001.jpg").unlink()

    codigo = main(_verificar(carpeta))

    assert codigo == CAMBIADO
    assert capsys.readouterr().err == (
        "cam-01_20261001_083005_0001.jpg: el sha256 no coincide con el manifiesto.\n"
        "cam-02_20261001_083005_0001.jpg: falta el archivo.\n"
    )


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "ml.manifiesto_dataset", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "Manifiesto versionado del dataset EPP" in resultado.stdout
