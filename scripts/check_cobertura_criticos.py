"""100 % de líneas y ramas en los módulos críticos (CLAUDE.md §6), con trinquete (W-012).

Uso: python scripts/check_cobertura_criticos.py cobertura.json
     `cobertura.json` es la salida de `python -m coverage json`. Los archivos heredados que
     todavía no llegan al 100 % solo pasan si figuran en `cobertura_critica_waiver` de
     docs/quality/metricas.json; los que ya llegan deben salir de esa lista.
"""

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MODULOS_CRITICOS = ("src/security/", "src/storage/", "src/analysis/", "src/ppe/")
METRICAS = Path("docs/quality/metricas.json")


def _faltantes(resumen: Mapping[str, Any]) -> tuple[int, int]:
    return resumen["summary"]["missing_lines"], resumen["summary"]["missing_branches"]


def _sin_cubrir(archivos: Mapping[str, Mapping[str, Any]], permitidos: list[str]) -> list[str]:
    errores = []
    for ruta, resumen in archivos.items():
        lineas, ramas = _faltantes(resumen)
        if ruta.startswith(MODULOS_CRITICOS) and (lineas or ramas) and ruta not in permitidos:
            errores.append(
                f"{ruta}: {lineas} líneas y {ramas} ramas sin cubrir; los módulos críticos "
                "exigen 100 % (CLAUDE.md §6)."
            )
    return errores


def _waivers_sobrantes(
    archivos: Mapping[str, Mapping[str, Any]], permitidos: list[str]
) -> list[str]:
    errores = []
    for ruta in permitidos:
        if ruta not in archivos:
            errores.append(
                f"{ruta} figura en cobertura_critica_waiver y no aparece en la cobertura: quítalo."
            )
        elif _faltantes(archivos[ruta]) == (0, 0):
            errores.append(
                f"{ruta} ya cubre el 100 %: quítalo de cobertura_critica_waiver (trinquete P4)."
            )
    return errores


def incumplimientos(archivos: Mapping[str, Mapping[str, Any]], permitidos: list[str]) -> list[str]:
    """Un mensaje por archivo crítico sin el 100 % y por waiver que ya sobra."""
    # coverage json escribe las rutas con el separador del sistema: en Windows llevan "\".
    normalizados = {ruta.replace("\\", "/"): resumen for ruta, resumen in archivos.items()}
    return _sin_cubrir(normalizados, permitidos) + _waivers_sobrantes(normalizados, permitidos)


def main(argv: list[str]) -> int:
    archivos = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["files"]
    permitidos = json.loads(METRICAS.read_text(encoding="utf-8"))["cobertura_critica_waiver"]
    errores = incumplimientos(archivos, permitidos)
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
