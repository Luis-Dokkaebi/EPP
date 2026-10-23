"""Hooks de Claude Code del repositorio (SPEC/9 §0.6): .claude/hooks/guardian.py."""

import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

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


def _cargar_guardian() -> ModuleType:
    especificacion = importlib.util.spec_from_file_location("guardian", SCRIPT)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


guardian = _cargar_guardian()


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


def _ejecutable(ruta: Path, contenido: str) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    ruta.chmod(ruta.stat().st_mode | stat.S_IXUSR)
    return ruta


def test_herramienta_prefiere_el_venv_del_proyecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    propia = _ejecutable(tmp_path / ".venv" / "bin" / "ruff", "#!/bin/sh\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    assert guardian.herramienta("ruff") == str(propia)


def test_herramienta_sin_variable_de_proyecto_usa_el_directorio_actual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ejecutable(tmp_path / ".venv" / "bin" / "ruff", "#!/bin/sh\n")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    assert guardian.herramienta("ruff") == os.path.join(".venv", "bin", "ruff")


def test_herramienta_sin_venv_usa_la_del_interprete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    assert guardian.herramienta("ruff") == str(Path(sys.executable).parent / "ruff")


def test_herramienta_por_ultimo_busca_en_el_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    en_path = _ejecutable(tmp_path / "bin" / "herramienta-falsa", "#!/bin/sh\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("PATH", str(en_path.parent))

    assert guardian.herramienta("herramienta-falsa") == str(en_path)


def _formatear(ruta: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ruta.parent))
    return _ejecutar(["formato"], {"tool_input": {"file_path": str(ruta)}}, monkeypatch)


def test_main_formato_ignora_archivos_fuera_del_proyecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archivo = tmp_path / "fuera" / "modulo.py"
    archivo.parent.mkdir()
    archivo.write_text("x = ( 1 )\n", encoding="utf-8")
    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proyecto))
    carga = {"tool_input": {"file_path": str(archivo)}}

    assert _ejecutar(["formato"], carga, monkeypatch) == 0
    assert archivo.read_text(encoding="utf-8") == "x = ( 1 )\n"


@pytest.mark.integration
def test_main_formato_formatea_el_archivo_python_editado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = ( 1 )\n", encoding="utf-8")

    codigo = _formatear(archivo, monkeypatch)

    assert codigo == 0
    assert archivo.read_text(encoding="utf-8") == "x = 1\n"


@pytest.mark.integration
def test_main_formato_respeta_las_exclusiones_del_proyecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\nextend-exclude = ["heredado.py"]\n', encoding="utf-8"
    )
    archivo = tmp_path / "heredado.py"
    archivo.write_text("l = ( 1 )\n", encoding="utf-8")

    codigo = _formatear(archivo, monkeypatch)

    assert codigo == 0
    assert archivo.read_text(encoding="utf-8") == "l = ( 1 )\n"


@pytest.mark.integration
def test_main_formato_con_hallazgo_sin_arreglo_automatico_lo_muestra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "modulo.py"
    archivo.write_text("l = 1\n", encoding="utf-8")

    codigo = _formatear(archivo, monkeypatch)

    assert codigo == CODIGO_BLOQUEO
    assert capsys.readouterr().err.startswith(
        f"ruff encontró problemas que no puede arreglar solo:\n{archivo}:1:1: E741"
    )


def test_main_formato_ignora_archivos_que_no_son_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archivo = tmp_path / "notas.md"
    archivo.write_text("x = ( 1 )\n", encoding="utf-8")

    assert _formatear(archivo, monkeypatch) == 0
    assert archivo.read_text(encoding="utf-8") == "x = ( 1 )\n"


def test_main_formato_ignora_un_python_borrado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _formatear(tmp_path / "borrado.py", monkeypatch) == 0


def test_main_formato_sin_ruff_instalado_avisa_con_codigo_uno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))

    codigo = _formatear(archivo, monkeypatch)

    assert codigo == 1
    assert capsys.readouterr().err == (
        "ruff no está instalado: corre .claude/hooks/session-start.sh.\n"
    )


def _crear_proyecto(raiz: Path, gemelo: str, prueba: str) -> None:
    (raiz / "CLAUDE.md").write_text("reglas\n", encoding="utf-8")
    (raiz / "Agents.md").write_text(gemelo, encoding="utf-8")
    (raiz / "test_rapida.py").write_text(
        f"import pytest\n\n\n@pytest.mark.unit\ndef test_x():\n    {prueba}\n", encoding="utf-8"
    )


def _cerrar(raiz: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(raiz))
    return _ejecutar(["cierre"], {"stop_hook_active": False}, monkeypatch)


def _motivo_de_cierre(capsys: pytest.CaptureFixture[str]) -> str:
    salida = json.loads(capsys.readouterr().out)
    assert salida["decision"] == "block"
    motivo: str = salida["reason"]
    return motivo


@pytest.mark.integration
def test_main_cierre_con_gemelos_distintos_bloquea(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "otras reglas\n", "assert True")

    codigo = _cerrar(tmp_path, monkeypatch)

    assert codigo == 0
    assert _motivo_de_cierre(capsys) == MOTIVO_GEMELOS


@pytest.mark.integration
def test_main_cierre_compara_el_contenido_y_no_solo_tamano_y_fecha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "REGLAS\n", "assert True")
    marca = os.stat(tmp_path / "CLAUDE.md").st_mtime_ns
    os.utime(tmp_path / "Agents.md", ns=(marca, marca))

    _cerrar(tmp_path, monkeypatch)

    assert _motivo_de_cierre(capsys) == MOTIVO_GEMELOS


@pytest.mark.integration
def test_main_cierre_con_dos_problemas_los_lista_en_lineas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "otras reglas\n", "assert False")

    _cerrar(tmp_path, monkeypatch)

    lineas = _motivo_de_cierre(capsys).split("\n")
    assert lineas[0] == MOTIVO_GEMELOS
    assert lineas[1] == "Las pruebas unitarias rápidas fallan (Ley Cero):"


@pytest.mark.integration
def test_main_cierre_usa_el_python_del_venv_del_proyecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "reglas\n", "assert True")
    _ejecutable(tmp_path / ".venv" / "bin" / "python", "#!/bin/sh\necho pytest-falso\nexit 1\n")

    _cerrar(tmp_path, monkeypatch)

    assert _motivo_de_cierre(capsys) == (
        "Las pruebas unitarias rápidas fallan (Ley Cero):\npytest-falso\n"
    )


@pytest.mark.integration
def test_main_cierre_recorta_la_salida_de_las_pruebas_a_los_ultimos_caracteres(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "reglas\n", "assert True")
    _ejecutable(
        tmp_path / ".venv" / "bin" / "python", "#!/bin/sh\nprintf 'a%.0s' $(seq 2500)\nexit 1\n"
    )

    _cerrar(tmp_path, monkeypatch)

    assert _motivo_de_cierre(capsys) == (
        "Las pruebas unitarias rápidas fallan (Ley Cero):\n" + "a" * 2000
    )


@pytest.mark.integration
@pytest.mark.parametrize("prueba", ["assert True", None], ids=["verde", "sin-pruebas-unitarias"])
def test_main_cierre_sin_problemas_no_bloquea(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    prueba: str | None,
) -> None:
    _crear_proyecto(tmp_path, "reglas\n", prueba or "pass")
    (tmp_path / "test_rapida.py").unlink(missing_ok=prueba is None)

    codigo = _cerrar(tmp_path, monkeypatch)

    assert codigo == 0
    assert capsys.readouterr().out == ""


def test_main_cierre_ya_activo_no_vuelve_a_bloquear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_proyecto(tmp_path, "otras reglas\n", "assert False")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    codigo = _ejecutar(["cierre"], {"stop_hook_active": True}, monkeypatch)

    assert codigo == 0
    assert capsys.readouterr().out == ""


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
