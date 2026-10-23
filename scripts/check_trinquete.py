"""Trinquete de complejidad (SPEC/9 §0.3, CLAUDE.md §3 y §10 paso 5).

Compara la salida de radon con la deuda heredada aprobada en docs/quality/metricas.json:
falla si aparece un bloque complejo nuevo y también si un waiver ya no hace falta.

Uso: python scripts/check_trinquete.py [raiz_src] [metricas.json]
"""

import json
import sys
from pathlib import Path

from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_rank, mi_visit

RANGOS_PROHIBIDOS_CC = frozenset("CDEF")
RANGOS_PROHIBIDOS_MI = frozenset("BC")
RAIZ_POR_DEFECTO = "src"
METRICAS_POR_DEFECTO = "docs/quality/metricas.json"


def _fuentes(raiz: Path) -> list[Path]:
    return sorted(raiz.rglob("*.py"))


def bloques_complejos(raiz: Path) -> list[str]:
    """Devuelve `ruta:nombre` de cada función o clase con rango C o peor."""
    return [
        f"{archivo.as_posix()}:{bloque.fullname}"
        for archivo in _fuentes(raiz)
        for bloque in cc_visit(archivo.read_text(encoding="utf-8"))
        if cc_rank(bloque.complexity) in RANGOS_PROHIBIDOS_CC
    ]


def archivos_poco_mantenibles(raiz: Path) -> list[str]:
    """Devuelve la ruta de cada archivo con índice de mantenibilidad B o peor."""
    return [
        archivo.as_posix()
        for archivo in _fuentes(raiz)
        if mi_rank(mi_visit(archivo.read_text(encoding="utf-8"), multi=True))
        in RANGOS_PROHIBIDOS_MI
    ]


def evaluar_trinquete(encontrados: list[str], permitidos: list[str]) -> list[str]:
    """Mensajes de error: deuda nueva o waivers que sobran."""
    nuevos = sorted(set(encontrados) - set(permitidos))
    sobrantes = sorted(set(permitidos) - set(encontrados))
    return [
        f"{bloque} supera la complejidad permitida (rango C o peor): divídela en funciones "
        "más chicas; el código nuevo no admite waivers (CLAUDE.md §3)."
        for bloque in nuevos
    ] + [
        f"{bloque} ya cumple: quítalo de docs/quality/metricas.json "
        "(el trinquete solo baja la deuda)."
        for bloque in sobrantes
    ]


def main(argv: list[str]) -> int:
    raiz = Path(argv[0] if argv else RAIZ_POR_DEFECTO)
    metricas = json.loads(Path(argv[1] if len(argv) > 1 else METRICAS_POR_DEFECTO).read_text())
    errores = evaluar_trinquete(bloques_complejos(raiz), metricas["radon_cc_waiver"])
    errores += evaluar_trinquete(archivos_poco_mantenibles(raiz), metricas["radon_mi_waiver"])
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
