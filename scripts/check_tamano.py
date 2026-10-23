"""Longitud de archivo ≤ 500 líneas (CLAUDE.md §3), con trinquete para el código heredado.

Uso: python scripts/check_tamano.py [archivo.py ...]
     Sin archivos revisa todo el Python versionado. Los archivos heredados más largos solo
     pasan si figuran en `longitud_waiver` de docs/quality/metricas.json.
"""

import json
import subprocess
import sys
from pathlib import Path

LINEAS_MAXIMAS = 500
METRICAS = Path("docs/quality/metricas.json")


def _lineas(archivo: Path) -> int:
    return len(archivo.read_text(encoding="utf-8").splitlines())


def archivos_demasiado_largos(archivos: list[Path], permitidos: list[str]) -> list[str]:
    """Un mensaje por archivo que supera el límite y no tiene waiver."""
    return [
        f"{archivo.as_posix()} tiene {_lineas(archivo)} líneas (máximo {LINEAS_MAXIMAS}): "
        "divídelo por responsabilidad (CLAUDE.md §3)."
        for archivo in archivos
        if _lineas(archivo) > LINEAS_MAXIMAS and archivo.as_posix() not in permitidos
    ]


def _python_versionado() -> list[Path]:
    # S603/S607: git con argumentos fijos, sobre el repositorio actual.
    salida = subprocess.run(
        ["git", "ls-files", "*.py"],  # noqa: S603, S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(linea) for linea in salida.splitlines()]


def main(argv: list[str]) -> int:
    archivos = [Path(argumento) for argumento in argv] or _python_versionado()
    permitidos = json.loads(METRICAS.read_text(encoding="utf-8"))["longitud_waiver"]
    errores = archivos_demasiado_largos(archivos, permitidos)
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
