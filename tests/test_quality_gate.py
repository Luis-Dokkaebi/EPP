"""Humo de scripts/quality_gate.sh y .ps1 con herramientas falsas en el PATH (SPEC/9 §0.3)."""

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
HERRAMIENTAS = (
    "ruff", "mypy", "python", "bandit", "pip-audit", "diff-cover", "mutmut", "detect-secrets-hook",
)  # fmt: skip
CODIGO_OPCION_INVALIDA_BASH = 2
MODULOS_CRITICOS = 4

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Lanzador:
    comando: tuple[str, ...]
    opciones_rapidas: tuple[str, ...]
    sin_instalar: str


def _pwsh() -> str:
    ejecutable = shutil.which("pwsh") or shutil.which("powershell")
    assert ejecutable, "Instala PowerShell 7 (pwsh) para probar scripts/quality_gate.ps1"
    return ejecutable


def _lanzador_bash() -> Lanzador:
    bash = shutil.which("bash")
    assert bash, "Se necesita bash para probar scripts/quality_gate.sh"
    return Lanzador(
        comando=(bash, str(RAIZ / "scripts" / "quality_gate.sh")),
        opciones_rapidas=("--sin-instalar", "--sin-mutacion"),
        sin_instalar="--sin-instalar",
    )


def _lanzador_powershell() -> Lanzador:
    return Lanzador(
        comando=(_pwsh(), "-NoProfile", "-File", str(RAIZ / "scripts" / "quality_gate.ps1")),
        opciones_rapidas=("-SinInstalar", "-SinMutacion"),
        sin_instalar="-SinInstalar",
    )


@pytest.fixture(params=["bash", "powershell"])
def lanzador(request: pytest.FixtureRequest) -> Lanzador:
    fabricas = {"bash": _lanzador_bash, "powershell": _lanzador_powershell}
    return fabricas[request.param]()


def _crear_herramienta(carpeta: Path, nombre: str, codigo: int) -> None:
    posix = carpeta / nombre
    posix.write_text(
        f'#!/bin/sh\necho "{nombre} $*" | tee -a "$HOME/registro.txt"\nexit {codigo}\n',
        encoding="utf-8",
    )
    posix.chmod(posix.stat().st_mode | stat.S_IXUSR)
    (carpeta / f"{nombre}.cmd").write_text(
        f'@echo {nombre} %* >> "%HOME%\\registro.txt"\r\n@exit /b {codigo}\r\n'
    )


def _entorno(tmp_path: Path, fallan: frozenset[str] = frozenset()) -> dict[str, str]:
    carpeta = tmp_path / "bin"
    carpeta.mkdir()
    for nombre in HERRAMIENTAS:
        _crear_herramienta(carpeta, nombre, 1 if nombre in fallan else 0)
    sistema = os.pathsep.join(str(Path(ruta).parent) for ruta in (_pwsh(), shutil.which("bash")))
    return {
        **{clave: valor for clave, valor in os.environ.items() if clave.upper() == "SYSTEMROOT"},
        "PATH": os.pathsep.join([str(carpeta), sistema, "/usr/bin", "/bin"]),
        "GATE_REPORTES": str(tmp_path / "reportes"),
        "DISPLAY": ":0",
        "HOME": str(tmp_path),
    }


def _correr(
    lanzador: Lanzador, entorno: dict[str, str], *opciones: str
) -> subprocess.CompletedProcess[str]:
    return _correr_con_opciones(lanzador, entorno, *lanzador.opciones_rapidas, *opciones)


def _correr_con_opciones(
    lanzador: Lanzador, entorno: dict[str, str], *opciones: str
) -> subprocess.CompletedProcess[str]:
    # S603: ejecuta los scripts propios del repositorio; los argumentos no vienen de fuera.
    return subprocess.run(
        [*lanzador.comando, *opciones],  # noqa: S603
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_quality_gate_todas_las_herramientas_en_verde_devuelve_cero(
    lanzador: Lanzador, tmp_path: Path
) -> None:
    resultado = _correr(lanzador, _entorno(tmp_path))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert (tmp_path / "reportes" / "9b-waivers.txt").is_file()


def test_quality_gate_falla_en_formato_y_no_ejecuta_los_pasos_siguientes(
    lanzador: Lanzador, tmp_path: Path
) -> None:
    resultado = _correr(lanzador, _entorno(tmp_path, fallan=frozenset({"ruff"})))

    assert resultado.returncode != 0
    assert "FALLA en el paso '1-formato'" in resultado.stderr
    assert not (tmp_path / "reportes" / "2-lint.txt").exists()


def test_quality_gate_falla_si_un_paso_posterior_falla(lanzador: Lanzador, tmp_path: Path) -> None:
    resultado = _correr(lanzador, _entorno(tmp_path, fallan=frozenset({"bandit"})))

    assert resultado.returncode != 0
    assert "FALLA en el paso '6a-bandit'" in resultado.stderr


def test_quality_gate_registra_los_pasos_omitidos_como_omitidos(
    lanzador: Lanzador, tmp_path: Path
) -> None:
    _correr(lanzador, _entorno(tmp_path))

    reporte = (tmp_path / "reportes" / "7-mutacion.txt").read_text(encoding="utf-8")
    assert "omitido" in reporte


def test_quality_gate_bash_opcion_desconocida_devuelve_dos(tmp_path: Path) -> None:
    resultado = _correr(_lanzador_bash(), _entorno(tmp_path), "--inventada")

    assert resultado.returncode == CODIGO_OPCION_INVALIDA_BASH


def test_quality_gate_powershell_opcion_desconocida_falla(tmp_path: Path) -> None:
    resultado = _correr(_lanzador_powershell(), _entorno(tmp_path), "-Inventada")

    assert resultado.returncode != 0


def _invocaciones(tmp_path: Path, texto: str) -> int:
    registro = (tmp_path / "registro.txt").read_text(encoding="utf-8").splitlines()
    return sum(texto in linea for linea in registro)


def test_quality_gate_mide_la_mutacion_de_cada_modulo_critico_por_separado(
    lanzador: Lanzador, tmp_path: Path
) -> None:
    _correr_con_opciones(lanzador, _entorno(tmp_path), lanzador.sin_instalar)

    assert _invocaciones(tmp_path, "python scripts/check_mutacion.py") == MODULOS_CRITICOS


def test_quality_gate_falla_si_mutmut_termina_con_error(lanzador: Lanzador, tmp_path: Path) -> None:
    entorno = _entorno(tmp_path, fallan=frozenset({"mutmut"}))

    resultado = _correr_con_opciones(lanzador, entorno, lanzador.sin_instalar)

    assert resultado.returncode != 0
    assert "FALLA en el paso '7-mutacion'" in resultado.stderr


def test_quality_gate_revisa_tamano_de_archivos_y_secretos(
    lanzador: Lanzador, tmp_path: Path
) -> None:
    _correr(lanzador, _entorno(tmp_path))

    assert _invocaciones(tmp_path, "python scripts/check_tamano.py") == 1
    assert _invocaciones(tmp_path, "detect-secrets-hook --baseline .secrets.baseline") == 1


def test_quality_gate_falla_si_aparece_un_secreto_nuevo(lanzador: Lanzador, tmp_path: Path) -> None:
    entorno = _entorno(tmp_path, fallan=frozenset({"detect-secrets-hook"}))

    resultado = _correr(lanzador, entorno)

    assert resultado.returncode != 0
    assert "FALLA en el paso '6c-secretos'" in resultado.stderr
