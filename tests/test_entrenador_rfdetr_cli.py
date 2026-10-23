"""Línea de comandos del entrenamiento con RF-DETR (docs/runbooks/entrenamiento.md)."""

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from ml import entrenador_rfdetr
from ml.entrenador_rfdetr import ARCHIVO_DE_PESOS, RAIZ_DEL_REPOSITORIO, main, sha_del_codigo
from ml.train import EntrenamientoInvalidoError
from tests.test_train import SHA_CODIGO, EntrenadorFalso, _dataset_versionado
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS, textos_ausentes

INVALIDO = 2
TASA = 1e-4
AYUDA = (
    "nano, small, medium o large (Apache-2.0)",
    "múltiplo de 32",
    "carpeta de artefactos, fuera de git",
    "dataset versionado",
    "su manifest.json",
    "tasa de aprendizaje",
)


class GitFalso:
    """Doble de subprocess.run para git: responde según el subcomando."""

    def __init__(self, cambios: str = "", sha: str = SHA_CODIGO) -> None:
        self.comandos: list[list[str]] = []
        self._respuestas = {"status": cambios, "rev-parse": f"{sha}\n"}

    def __call__(self, comando: Sequence[str], **opciones: Any) -> subprocess.CompletedProcess[str]:
        self.comandos.append(list(comando))
        assert opciones == {"capture_output": True, "text": True, "check": True}
        return subprocess.CompletedProcess(comando, 0, self._respuestas[comando[3]], "")


def _argumentos(carpeta: Path) -> list[str]:
    return [
        *("--dataset", str(carpeta), "--manifiesto", str(carpeta / "manifest.json")),
        *("--tamano", "small", "--resolucion", "512", "--epocas", "2", "--lote", "4"),
        *("--tasa", str(TASA), "--semilla", "7", "--salidas", str(carpeta / "artefactos")),
    ]


def test_sha_del_codigo_lee_el_commit_actual_de_un_arbol_limpio(tmp_path: Path) -> None:
    git = GitFalso()

    assert sha_del_codigo(tmp_path, git) == SHA_CODIGO
    assert git.comandos == [
        ["git", "-C", str(tmp_path), "status", "--porcelain", "--untracked-files=no"],
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
    ]


def test_sha_del_codigo_se_niega_con_cambios_sin_commitear(tmp_path: Path) -> None:
    with pytest.raises(EntrenamientoInvalidoError) as error:
        sha_del_codigo(tmp_path, GitFalso(cambios=" M ml/train.py\n"))

    assert str(error.value) == (
        "Hay cambios sin commitear: el SHA no describiría el código que entrena. Commitea o "
        "descarta los cambios y vuelve a correr."
    )


def test_main_entrena_y_muestra_el_registro(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _dataset_versionado(tmp_path)

    codigo = main(_argumentos(tmp_path), crear_entrenador=EntrenadorFalso, sha=lambda: SHA_CODIGO)

    [artefacto] = (tmp_path / "artefactos").iterdir()
    registro = json.loads((artefacto / "registro.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert registro["config"]["tasa_de_aprendizaje"] == TASA
    assert capsys.readouterr().out == f"Artefacto {artefacto.name}: {artefacto / 'registro.json'}\n"


def test_main_informa_una_configuracion_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(tmp_path)
    argumentos[argumentos.index("small")] = "xl"

    codigo = main(argumentos, crear_entrenador=EntrenadorFalso, sha=lambda: SHA_CODIGO)

    assert codigo == INVALIDO
    assert capsys.readouterr().err.startswith('Tamaño "xl" no permitido')


@pytest.mark.parametrize(
    "falta",
    [
        "--dataset",
        "--manifiesto",
        "--tamano",
        "--resolucion",
        "--epocas",
        "--lote",
        "--tasa",
        "--semilla",
        "--salidas",
    ],
)
def test_main_exige_cada_parametro(tmp_path: Path, falta: str) -> None:
    argumentos = _argumentos(tmp_path)
    posicion = argumentos.index(falta)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == INVALIDO


def test_main_explica_los_parametros_en_la_ayuda(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert textos_ausentes(capsys.readouterr().out, AYUDA) == []


def test_main_toma_el_sha_de_la_raiz_del_repositorio() -> None:
    assert RAIZ_DEL_REPOSITORIO == RAIZ


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "ml.entrenador_rfdetr", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "Adaptador de RF-DETR (Apache-2.0)" in resultado.stdout


def test_los_pesos_se_buscan_con_el_nombre_que_deja_rfdetr() -> None:
    assert ARCHIVO_DE_PESOS == "checkpoint_best_total.pth"


def test_main_sin_sha_inyectado_lo_lee_del_repositorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dataset_versionado(tmp_path)
    raices: list[Path] = []
    monkeypatch.setattr(
        entrenador_rfdetr, "sha_del_codigo", lambda raiz: raices.append(raiz) or SHA_CODIGO
    )

    codigo = main(_argumentos(tmp_path), crear_entrenador=EntrenadorFalso)

    assert (codigo, raices) == (0, [RAIZ])
