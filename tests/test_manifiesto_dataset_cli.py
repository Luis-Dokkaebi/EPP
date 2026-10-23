"""Línea de comandos del manifiesto del dataset (docs/runbooks/etiquetado.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ml.manifiesto_dataset import huella_del_manifiesto, main
from tests.test_manifiesto_dataset import _dataset
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS, textos_ausentes

CAMBIADO, INVALIDO = 1, 2
FUENTE = "Planta Ñandú=propia-con-autorizacion"
LADO_MINIMO = 10.0
AYUDA = ["valida el dataset y escribe su manifiesto", "compara la carpeta con el manifiesto"]
AYUDA_DE_CREAR = [
    "vMAYOR.MENOR",
    "decisión D6, en píxeles",
    "AAAA-MM-DD",
    "ml/datasets/<v>/manifest.json",
]


def _ruta(carpeta: Path) -> Path:
    return carpeta / "datasets" / "v0.1" / "manifest.json"


def _crear(carpeta: Path, *extra: str) -> list[str]:
    return [
        "crear",
        *("--carpeta", str(carpeta), "--version", "v0.1", "--taxonomia", "v1"),
        *("--lado-minimo", str(LADO_MINIMO), "--fuente", FUENTE),
        *("--camara-test", "cam-03", "--dia-valid", "2026-10-02"),
        *("--salida", str(_ruta(carpeta))),
        *extra,
    ]


def _verificar(carpeta: Path) -> list[str]:
    return ["verificar", "--carpeta", str(carpeta), "--manifiesto", str(_ruta(carpeta))]


def test_crear_guarda_el_manifiesto_y_muestra_su_huella(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = _dataset(tmp_path)

    codigo = main(_crear(carpeta))

    texto = _ruta(carpeta).read_text(encoding="utf-8")
    manifiesto = json.loads(texto)
    assert codigo == 0
    assert texto.startswith('{\n  "version"')
    assert "Planta Ñandú" in texto
    assert manifiesto["fuentes"] == [
        {"nombre": "Planta Ñandú", "licencia": "propia-con-autorizacion"}
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
    assert not (_ruta(carpeta)).exists()


@pytest.mark.parametrize("fuente", ["sin-signo-igual", "=MIT"])
def test_crear_exige_fuentes_con_nombre_igual_licencia(
    tmp_path: Path, fuente: str, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _crear(_dataset(tmp_path))
    argumentos[argumentos.index(FUENTE)] = fuente

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO
    assert f'"{fuente}": usa <nombre>=<licencia>.' in capsys.readouterr().err


@pytest.mark.parametrize(
    "argumentos",
    [[], ["verificar", "--carpeta", "x"], ["verificar", "--manifiesto", "x"]],
    ids=["sin-accion", "sin-manifiesto", "sin-carpeta"],
)
def test_main_exige_la_accion_y_los_parametros_de_verificar(argumentos: list[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


@pytest.mark.parametrize(
    ("argumentos", "textos"),
    [(["--help"], AYUDA), (["crear", "--help"], AYUDA_DE_CREAR)],
)
def test_main_explica_acciones_y_parametros_en_la_ayuda(
    argumentos: list[str], textos: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(argumentos)

    assert textos_ausentes(capsys.readouterr().out, textos) == []


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
