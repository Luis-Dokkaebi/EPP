"""Hooks `formato` y `cierre` de .claude/hooks/guardian.py (SPEC/9 §0.6)."""

import io
import json
import os
import stat
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


def _ejecutar(
    argumentos: list[str], carga: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(carga)))
    resultado: int = guardian.main(argumentos)
    return resultado


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
