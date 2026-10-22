"""CI de GitHub Actions (SPEC/9 §0.8): matriz Windows + Linux, licencias y mutación."""

from typing import Any

import yaml

from tests.utilidades_scripts import RAIZ

FLUJO = RAIZ / ".github" / "workflows" / "quality-gate.yml"
# PyYAML sigue YAML 1.1, donde la clave `on` se lee como el booleano True.
CLAVE_EVENTOS = True


def _flujo() -> dict[Any, Any]:
    flujo: dict[Any, Any] = yaml.safe_load(FLUJO.read_text(encoding="utf-8"))
    return flujo


def _job(nombre: str) -> dict[str, Any]:
    job: dict[str, Any] = _flujo()["jobs"][nombre]
    return job


def _comandos(job: dict[str, Any]) -> str:
    return "\n".join(paso.get("run", "") for paso in job["steps"])


def _acciones(job: dict[str, Any]) -> list[str]:
    return [paso["uses"].split("@")[0] for paso in job["steps"] if "uses" in paso]


def test_ci_corre_en_pull_requests_en_main_y_cada_noche() -> None:
    eventos = _flujo()[CLAVE_EVENTOS]

    assert {"pull_request", "push", "schedule"} <= set(eventos)
    assert eventos["push"]["branches"] == ["main"]


def test_ci_solo_lee_el_repositorio() -> None:
    assert _flujo()["permissions"] == {"contents": "read"}


def test_ci_gate_corre_en_windows_y_linux_con_python_311() -> None:
    gate = _job("gate")

    assert gate["strategy"]["matrix"]["os"] == ["windows-latest", "ubuntu-latest"]
    assert '"3.11"' in FLUJO.read_text(encoding="utf-8")


def test_ci_gate_corre_el_script_de_cada_sistema_sin_mutacion() -> None:
    comandos = _comandos(_job("gate"))

    assert "scripts/quality_gate.sh --sin-instalar --sin-mutacion" in comandos
    assert "scripts/quality_gate.ps1 -SinInstalar -SinMutacion" in comandos


def test_ci_mutacion_muta_lo_cambiado_en_pr_y_los_criticos_de_noche() -> None:
    comandos = _comandos(_job("mutacion"))

    assert "scripts/quality_gate.sh --sin-instalar --changed" in comandos
    assert "scripts/quality_gate.sh --sin-instalar\n" in comandos + "\n"


def test_ci_licencias_evalua_un_entorno_limpio_solo_con_requirements() -> None:
    comandos = _comandos(_job("licencias"))

    assert "-m venv" in comandos
    assert "-r requirements.txt" in comandos
    assert "requirements-dev.txt" not in comandos
    assert "scripts/check_licenses.py --paquetes" in comandos


def test_ci_licencias_no_pierde_el_codigo_de_salida_en_la_tuberia() -> None:
    # Sin `shell: bash` explícito, Actions no activa pipefail y `| tee` ocultaría el fallo.
    paso = next(
        paso for paso in _job("licencias")["steps"] if paso.get("name") == "Gate de licencias"
    )

    assert paso["shell"] == "bash"


def test_ci_licencias_genera_los_avisos_de_terceros_del_runtime_antes_del_gate() -> None:
    """El gate falla por diseño (W-011): los avisos se generan antes para no perderlos."""
    nombres = [paso.get("name") for paso in _job("licencias")["steps"]]
    paso = _job("licencias")["steps"][nombres.index("Avisos de terceros del runtime")]

    assert nombres.index("Avisos de terceros del runtime") < nombres.index("Gate de licencias")
    assert "--python .venv-licencias/bin/python" in paso["run"]
    assert "--with-license-file --with-notice-file --no-license-path" in paso["run"]
    assert "scripts/generar_avisos_terceros.py" in paso["run"]
    assert "--salida reports/licencias/THIRD_PARTY_NOTICES.txt" in paso["run"]


def test_ci_publica_los_reportes_aunque_el_job_falle() -> None:
    for nombre in ("gate", "licencias", "mutacion"):
        subidas = [
            paso
            for paso in _job(nombre)["steps"]
            if paso.get("uses", "").startswith("actions/upload-artifact@")
        ]
        assert [paso["if"] for paso in subidas] == ["always()"], nombre


def test_ci_trae_la_historia_completa_para_comparar_con_la_base() -> None:
    for nombre in ("gate", "mutacion"):
        checkout = next(
            paso
            for paso in _job(nombre)["steps"]
            if paso.get("uses", "").startswith("actions/checkout@")
        )
        assert checkout["with"]["fetch-depth"] == 0, nombre


def test_ci_usa_solo_acciones_oficiales_de_github() -> None:
    acciones = {accion for job in _flujo()["jobs"].values() for accion in _acciones(job)}

    assert acciones == {
        "actions/checkout",
        "actions/setup-python",
        "actions/upload-artifact",
    }
