"""Hooks de Claude Code del repositorio (SPEC/9 §0.6): .claude/hooks/guardian.py."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.utilidades_scripts import cargar_hook

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / ".claude" / "hooks" / "guardian.py"
CODIGO_BLOQUEO = 2
MOTIVO_COMMIT = "`git commit --no-verify` está prohibido (CLAUDE.md §12 y §14.9): corrige el hook."
MOTIVO_PUSH = (
    "`git push --force` está prohibido (CLAUDE.md §12): usa --force-with-lease y decláralo."
)
MOTIVO_GEMELOS = "CLAUDE.md y Agents.md difieren: copia uno sobre el otro (§14.13)."
OPCIONES_PIP_CON_VALOR = [
    "-r", "--requirement", "-c", "--constraint", "-e", "--editable", "-i", "--index-url",
    "--extra-index-url", "-f", "--find-links", "-t", "--target", "--python", "-p",
    "--index-strategy", "--prefix", "--root",
]  # fmt: skip


guardian = cargar_hook("guardian")


@pytest.mark.parametrize(
    "comando",
    [
        'git commit --no-verify -m "x"',
        "git commit -n -m x",
        "git commit -m x -n",
        "git commit -F - --no-verify",
        "git add . && git commit -anm x",
        "ls; git commit -n",
        "true || git commit -n",
        "echo x | git commit -n",
        "sleep 1 & git commit -n",
        "true\ngit commit -n",
        'git commit -n -m "sin cerrar',
        "true;git commit -n",
        "true&&git commit -n",
        "true||git commit -n",
        "echo x|git commit -n",
        "true&git commit -n",
        "git commit -ma -n",
        "git commit -a -n",
    ],
)
def test_motivo_de_bloqueo_bash_commit_sin_verificar_es_bloqueado(comando: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) == MOTIVO_COMMIT


@pytest.mark.parametrize(
    "comando",
    [
        'git commit -m "feat: --no-verify en el mensaje no cuenta"',
        "git commit -m -n",
        "git commit -mn",
        "git commit -am 'mensaje'",
        "git commit --message -n",
        "git commit -F -n",
        "git commit --file -n",
        "git commit -C -n",
        "git commit -c -n",
        "git commit -t -n",
        "git commit --template -n",
        "git commit --author -n",
        "git commit --date -n",
        "git commit --amend -m x",
        "git commit -am -n",
        "git commit -a -m x",
        "git commit",
    ],
)
def test_motivo_de_bloqueo_bash_commit_permitido_devuelve_none(comando: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) is None


@pytest.mark.parametrize("comando", ["git push --force origin rama", "git push -f"])
def test_motivo_de_bloqueo_bash_push_forzado_es_bloqueado(comando: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) == MOTIVO_PUSH


@pytest.mark.parametrize(
    "comando", ["git push --force-with-lease origin rama", "git push -u origin rama"]
)
def test_motivo_de_bloqueo_bash_push_normal_devuelve_none(comando: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) is None


@pytest.mark.parametrize(
    ("comando", "paquetes"),
    [
        ("pip install requests", "requests"),
        ("pip3 install requests six", "requests, six"),
        ("python -m pip install numpy pandas==2.2.0", "numpy"),
        ("uv pip install --index-strategy unsafe-best-match torch", "torch"),
        ('pip install "./ruta con espacios/pkg.whl" otro', "otro"),
    ],
)
def test_motivo_de_bloqueo_bash_pip_sin_version_nombra_los_paquetes(
    comando: str, paquetes: str
) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) == (
        f"pip install sin versión fijada ({paquetes}) está prohibido (CLAUDE.md §14.11): "
        "usa paquete==versión y corre pip-audit."
    )


@pytest.mark.parametrize("opcion", OPCIONES_PIP_CON_VALOR)
def test_motivo_de_bloqueo_bash_pip_opcion_con_valor_no_es_un_paquete(opcion: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(f"pip install {opcion} valor numpy==1.26.4") is None


@pytest.mark.parametrize(
    "comando",
    [
        "pip install numpy==1.26.4",
        "pip install ./dlib-19.24.1-cp311-cp311-win_amd64.whl",
        "pip install /tmp/paquete",
        "pip install ./paquete",
        "pip install .",
        "pip install dist/paquete-1.0.tar.gz",
        "pip install dlib.whl",
        "pip install --upgrade numpy==1.26.4",
        'pip install "./ruta con espacios/pkg.whl"',
        "pip install",
        "pip install -r requirements.txt  # comentario de shell, no un paquete",
        "ls -la",
    ],
)
def test_motivo_de_bloqueo_bash_pip_fijado_o_local_devuelve_none(comando: str) -> None:
    assert guardian.motivo_de_bloqueo_bash(comando) is None


@pytest.mark.parametrize(
    "ruta",
    [
        "gui_app.spec",
        "/repo/compilar_exe.bat",
        "obfuscate.py",
        "setup_oficina.iss",
        "models/yolov8/yolov8n.pt",
        "models/epp.onnx",
        "Reporte_Asistencia.xlsx",
        "dlib-19.24.1-cp311-cp311-win_amd64.whl",
    ],
)
def test_motivo_de_bloqueo_archivo_protegido_explica_la_autorizacion(ruta: str) -> None:
    assert guardian.motivo_de_bloqueo_archivo(ruta) == (
        f"{Path(ruta).name} es un archivo de build o binario protegido (CLAUDE.md §14.12 y §16). "
        "Necesita la autorización humana D8; con ella, exporta "
        "EPP_AUTORIZA_ARCHIVOS_PROTEGIDOS=1."
    )


def test_motivo_de_bloqueo_archivo_comun_devuelve_none() -> None:
    assert guardian.motivo_de_bloqueo_archivo("src/ppe/domain/reglas.py") is None


def _ejecutar(
    argumentos: list[str], carga: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(carga)))
    resultado: int = guardian.main(argumentos)
    return resultado


def test_main_bash_prohibido_bloquea_con_codigo_dos_y_explica(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    carga = {"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}}

    codigo = _ejecutar(["bash"], carga, monkeypatch)

    assert codigo == CODIGO_BLOQUEO
    assert capsys.readouterr().err == f"{MOTIVO_COMMIT}\n"


def test_main_bash_permitido_devuelve_cero(monkeypatch: pytest.MonkeyPatch) -> None:
    carga = {"tool_name": "Bash", "tool_input": {"command": "git status"}}

    assert _ejecutar(["bash"], carga, monkeypatch) == 0


def test_main_archivo_protegido_bloquea_sin_autorizacion(monkeypatch: pytest.MonkeyPatch) -> None:
    carga = {"tool_name": "Edit", "tool_input": {"file_path": "/repo/gui_app.spec"}}
    monkeypatch.delenv("EPP_AUTORIZA_ARCHIVOS_PROTEGIDOS", raising=False)

    assert _ejecutar(["archivos"], carga, monkeypatch) == CODIGO_BLOQUEO


def test_main_archivo_protegido_con_variable_de_autorizacion_pasa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    carga = {"tool_name": "Write", "tool_input": {"file_path": "/repo/gui_app.spec"}}
    monkeypatch.setenv("EPP_AUTORIZA_ARCHIVOS_PROTEGIDOS", "1")

    assert _ejecutar(["archivos"], carga, monkeypatch) == 0


def test_main_evento_sin_los_datos_de_la_herramienta_falla_ruidosamente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(KeyError):
        _ejecutar(["bash"], {"tool_name": "Bash", "tool_input": {}}, monkeypatch)


def test_main_subcomando_desconocido_falla_ruidosamente(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        _ejecutar(["inventado"], {}, monkeypatch)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("comando", "codigo_esperado"),
    [("git push -f", CODIGO_BLOQUEO), ("git status", 0)],
    ids=["bloqueado", "permitido"],
)
def test_script_ejecutado_como_hook_devuelve_el_codigo_de_main(
    comando: str, codigo_esperado: int
) -> None:
    carga = json.dumps({"tool_name": "Bash", "tool_input": {"command": comando}})

    # S603: ejecuta el hook propio del repositorio con un evento fijo.
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), "bash"],  # noqa: S603
        input=carga,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert resultado.returncode == codigo_esperado, resultado.stderr
