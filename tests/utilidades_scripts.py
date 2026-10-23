"""Ayudas compartidas para probar los scripts del harness como programas."""

import importlib.util
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[1]
SEGUNDOS_MAXIMOS = 60


def ejecutar_script(
    nombre: str, *argumentos: str, carpeta: Path = RAIZ
) -> subprocess.CompletedProcess[str]:
    """Corre scripts/<nombre> con el mismo intérprete de la suite, desde `carpeta`."""
    # S603: ejecuta un script propio del repositorio; los argumentos no vienen de fuera.
    return subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / nombre), *argumentos],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=carpeta,
    )


def ejecutar_modulo(modulo: str, *argumentos: str) -> subprocess.CompletedProcess[str]:
    """Corre `python -m <modulo>` desde la raíz del repositorio (p. ej. tools.replay)."""
    # S603: ejecuta un módulo propio del repositorio; los argumentos no vienen de fuera.
    return subprocess.run(
        [sys.executable, "-m", modulo, *argumentos],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )


def cargar_hook(nombre: str) -> ModuleType:
    """Importa .claude/hooks/<nombre>.py, que no es un paquete importable."""
    ruta = RAIZ / ".claude" / "hooks" / f"{nombre}.py"
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    if especificacion is None or especificacion.loader is None:
        raise ImportError(f"No se puede cargar {ruta}")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def textos_ausentes(salida: str, textos: Iterable[str]) -> list[str]:
    """Textos que no aparecen como frase entera (entre espacios) en la salida, sin importar los
    saltos de línea: "XXtextoXX" no cuenta como "texto"."""
    normalizada = f" {' '.join(salida.split())} "
    return [texto for texto in textos if f" {texto} " not in normalizada]
