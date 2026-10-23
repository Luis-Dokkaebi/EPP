"""Configuración de pre-commit (SPEC/9 §0.7): los chequeos rápidos corren antes de cada commit."""

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.utilidades_scripts import RAIZ

CONFIGURACION = RAIZ / ".pre-commit-config.yaml"
GANCHOS_DE_COMMIT = {
    "ruff-format",
    "ruff-check",
    "arquitectura",
    "gemelos",
    "tamano",
    "detect-secrets",
}


def _ganchos() -> dict[str, dict[str, Any]]:
    configuracion = yaml.safe_load(CONFIGURACION.read_text(encoding="utf-8"))
    return {gancho["id"]: gancho for repo in configuracion["repos"] for gancho in repo["hooks"]}


def test_pre_commit_incluye_los_chequeos_del_plan() -> None:
    ganchos = _ganchos()

    assert GANCHOS_DE_COMMIT | {"licencias"} == set(ganchos)


def test_pre_commit_corre_los_chequeos_rapidos_en_cada_commit() -> None:
    ganchos = _ganchos()

    assert all("stages" not in ganchos[nombre] for nombre in GANCHOS_DE_COMMIT)


def test_pre_commit_deja_el_gate_de_licencias_en_la_etapa_manual() -> None:
    # Bloqueado por AC-001 (ultralytics AGPL, D8): en cada commit impediría todo trabajo.
    assert _ganchos()["licencias"]["stages"] == ["manual"]


def test_pre_commit_detect_secrets_usa_la_linea_base_versionada() -> None:
    gancho = _ganchos()["detect-secrets"]

    assert gancho["args"] == ["--baseline", ".secrets.baseline"]
    assert (RAIZ / ".secrets.baseline").is_file()


@pytest.mark.parametrize(
    "script",
    ["scripts/check_architecture.py", "scripts/check_tamano.py", "scripts/check_licenses.py"],
)
def test_pre_commit_los_scripts_que_invoca_existen(script: str) -> None:
    entradas = " ".join(gancho["entry"] for gancho in _ganchos().values())

    assert script in entradas
    assert (RAIZ / script).is_file()


@pytest.mark.integration
def test_pre_commit_valida_la_configuracion(tmp_path: Path) -> None:
    pre_commit = shutil.which("pre-commit")
    assert pre_commit, "Instala pre-commit (requirements-dev.txt)"

    # S603: binario del entorno de desarrollo con argumentos fijos.
    resultado = subprocess.run(
        [pre_commit, "validate-config", str(CONFIGURACION)],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        env={"PRE_COMMIT_HOME": str(tmp_path), "PATH": str(Path(pre_commit).parent)},
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
