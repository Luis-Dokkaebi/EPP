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
# Rutas que el gate muta por omisión (MODULOS_CRITICOS de los scripts); solo deben existir.
ARCHIVOS_CRITICOS = (
    "src/security/drm.py",
    "src/storage/database_manager.py",
    "src/analysis/efficiency_calculator.py",
    "src/zones/zone_checker.py",
    "src/ppe/domain/asociacion.py",
)
MODULOS_CRITICOS = len(ARCHIVOS_CRITICOS)

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


def _lanzador_bash(raiz: Path) -> Lanzador:
    bash = shutil.which("bash")
    assert bash, "Se necesita bash para probar scripts/quality_gate.sh"
    return Lanzador(
        comando=(bash, str(raiz / "scripts" / "quality_gate.sh")),
        opciones_rapidas=("--sin-instalar", "--sin-mutacion"),
        sin_instalar="--sin-instalar",
    )


def _lanzador_powershell(raiz: Path) -> Lanzador:
    return Lanzador(
        comando=(_pwsh(), "-NoProfile", "-File", str(raiz / "scripts" / "quality_gate.ps1")),
        opciones_rapidas=("-SinInstalar", "-SinMutacion"),
        sin_instalar="-SinInstalar",
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Copia mínima del repositorio para correr el gate.

    El gate trabaja en la raíz donde vive el script y borra su `.mutmut-cache`: corrido sobre el
    repositorio real, borraba la caché de un mutmut en curso (CLAUDE.md §4: nada fuera de tmp_path).
    """
    raiz = tmp_path / "repo"
    (raiz / "scripts").mkdir(parents=True)
    for script in ("quality_gate.sh", "quality_gate.ps1"):
        shutil.copy2(RAIZ / "scripts" / script, raiz / "scripts" / script)
    for gemelo in ("CLAUDE.md", "Agents.md"):
        shutil.copy2(RAIZ / gemelo, raiz / gemelo)
    for archivo in ARCHIVOS_CRITICOS:
        (raiz / archivo).parent.mkdir(parents=True, exist_ok=True)
        (raiz / archivo).write_text("VALOR = 1\n", encoding="utf-8")
    git = shutil.which("git")
    assert git, "Se necesita git: el gate lista los archivos versionados"
    # S603: git del sistema con argumentos fijos sobre un directorio temporal.
    subprocess.run([git, "init", "-q", str(raiz)], check=True)  # noqa: S603
    _versionar(raiz)
    return raiz


def _versionar(raiz: Path) -> None:
    """Agrega al índice todo lo que hay en la copia: el gate revisa los archivos versionados."""
    git = shutil.which("git")
    assert git, "Se necesita git: el gate lista los archivos versionados"
    # S603: git del sistema con argumentos fijos sobre un directorio temporal.
    subprocess.run([git, "-C", str(raiz), "add", "-A"], check=True)  # noqa: S603


@pytest.fixture(params=["bash", "powershell"])
def lanzador(request: pytest.FixtureRequest, repo: Path) -> Lanzador:
    fabricas = {"bash": _lanzador_bash, "powershell": _lanzador_powershell}
    return fabricas[request.param](repo)


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


# Windows necesita estas variables para ejecutar los .cmd falsos (cmd.exe y PATHEXT).
VARIABLES_DE_WINDOWS = frozenset({"SYSTEMROOT", "COMSPEC", "PATHEXT"})


def _entorno(
    tmp_path: Path,
    fallan: frozenset[str] = frozenset(),
    ausentes: frozenset[str] = frozenset(),
) -> dict[str, str]:
    carpeta = tmp_path / "bin"
    carpeta.mkdir()
    for nombre in sorted(set(HERRAMIENTAS) - ausentes):
        _crear_herramienta(carpeta, nombre, 1 if nombre in fallan else 0)
    # Solo la carpeta de bash (sus utilidades): la de pwsh puede ser un venv con las herramientas
    # reales, que ocultarían a las falsas.
    sistema = [str(Path(shutil.which("bash") or "/bin/bash").parent)]
    windows = {
        clave: valor for clave, valor in os.environ.items() if clave.upper() in VARIABLES_DE_WINDOWS
    }
    system32 = [
        str(Path(valor, "System32"))
        for clave, valor in windows.items()
        if clave.upper() == "SYSTEMROOT"
    ]
    return {
        **windows,
        "PATH": os.pathsep.join([str(carpeta), *sistema, *system32, "/usr/bin", "/bin"]),
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


def test_quality_gate_bash_opcion_desconocida_devuelve_dos(repo: Path, tmp_path: Path) -> None:
    resultado = _correr(_lanzador_bash(repo), _entorno(tmp_path), "--inventada")

    assert resultado.returncode == CODIGO_OPCION_INVALIDA_BASH


def test_quality_gate_powershell_opcion_desconocida_falla(repo: Path, tmp_path: Path) -> None:
    resultado = _correr(_lanzador_powershell(repo), _entorno(tmp_path), "-Inventada")

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
    assert _invocaciones(tmp_path, "detect-secrets-hook --baseline .secrets.baseline") >= 1


LIMITE_DE_CMD = 8191  # caracteres por línea de comandos de cmd.exe


ARCHIVOS_DE_RELLENO = 300  # con sus nombres largos suman más que LIMITE_DE_CMD


def test_quality_gate_revisa_cada_archivo_versionado_en_lotes_que_caben_en_cmd(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    for numero in range(ARCHIVOS_DE_RELLENO):
        (repo / f"documento_con_un_nombre_bastante_largo_numero_{numero:03d}.md").touch()
    _versionar(repo)
    # S603/S607: git del sistema con argumentos fijos.
    versionados = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files"],  # noqa: S603, S607
        capture_output=True, text=True, check=True, cwd=repo,
    ).stdout.splitlines()  # fmt: skip
    assert len(" ".join(versionados)) > LIMITE_DE_CMD

    _correr(lanzador, _entorno(tmp_path))

    registro = (tmp_path / "registro.txt").read_text(encoding="utf-8").splitlines()
    lotes = [linea for linea in registro if linea.startswith("detect-secrets-hook --baseline")]
    assert max(len(lote) for lote in lotes) < LIMITE_DE_CMD
    assert [archivo for archivo in versionados if not any(archivo in lote for lote in lotes)] == []


def test_quality_gate_falla_si_aparece_un_secreto_nuevo(lanzador: Lanzador, tmp_path: Path) -> None:
    entorno = _entorno(tmp_path, fallan=frozenset({"detect-secrets-hook"}))

    resultado = _correr(lanzador, entorno)

    assert resultado.returncode != 0
    assert "FALLA en el paso '6c-secretos'" in resultado.stderr


def test_quality_gate_falla_si_falta_una_herramienta(lanzador: Lanzador, tmp_path: Path) -> None:
    resultado = _correr(lanzador, _entorno(tmp_path, ausentes=frozenset({"bandit"})))

    assert resultado.returncode != 0
    assert "FALLA en el paso '6a-bandit'" in resultado.stderr


def test_quality_gate_reinicia_la_cache_de_mutmut_de_su_raiz_en_cada_objetivo(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    cache = repo / ".mutmut-cache"
    cache.write_text("corrida anterior", encoding="utf-8")

    _correr_con_opciones(lanzador, _entorno(tmp_path), lanzador.sin_instalar)

    assert not cache.exists()


def test_quality_gate_falla_si_los_gemelos_difieren(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    (repo / "Agents.md").write_text("versión divergente\n", encoding="utf-8")

    resultado = _correr(lanzador, _entorno(tmp_path))

    assert resultado.returncode != 0
    assert "FALLA en el paso '9a-gemelos'" in resultado.stderr


def _mutmut_de(tmp_path: Path, archivo: str) -> str:
    registro = (tmp_path / "registro.txt").read_text(encoding="utf-8").splitlines()
    (linea,) = (x for x in registro if f"--paths-to-mutate {archivo} " in x)
    return linea


def test_quality_gate_muta_cada_archivo_de_un_directorio_critico_por_separado(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    (repo / "src" / "security" / "crash_logger.py").write_text("VALOR = 2\n", encoding="utf-8")
    _versionar(repo)

    _correr_con_opciones(lanzador, _entorno(tmp_path), lanzador.sin_instalar)

    assert _mutmut_de(tmp_path, "src/security/crash_logger.py")
    assert _mutmut_de(tmp_path, "src/security/drm.py")
    assert _invocaciones(tmp_path, "--paths-to-mutate src/security ") == 0


def test_quality_gate_no_muta_los_archivos_vacios_de_un_directorio_critico(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    (repo / "src" / "security" / "__init__.py").touch()
    _versionar(repo)

    _correr_con_opciones(lanzador, _entorno(tmp_path), lanzador.sin_instalar)

    assert _invocaciones(tmp_path, "--paths-to-mutate src/security/__init__.py") == 0
    assert _mutmut_de(tmp_path, "src/security/drm.py")


def test_quality_gate_muta_con_las_pruebas_que_importan_el_archivo(
    lanzador: Lanzador, repo: Path, tmp_path: Path
) -> None:
    (repo / "tests").mkdir()
    (repo / "tests" / "test_boveda.py").write_text(
        "from src.security.drm import DRMValidator\n", encoding="utf-8"
    )
    (repo / "tests" / "test_drm_respaldo.py").touch()
    (repo / "tests" / "test_ajena.py").write_text("import src.security.drm_viejo\n")
    _versionar(repo)

    _correr_con_opciones(lanzador, _entorno(tmp_path), lanzador.sin_instalar)

    linea = _mutmut_de(tmp_path, "src/security/drm.py")
    assert "tests/test_boveda.py" in linea
    assert "tests/test_drm_respaldo.py" in linea
    assert "tests/test_ajena.py" not in linea
