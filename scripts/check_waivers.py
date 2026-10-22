"""Caducidad de los waivers (CLAUDE.md §15.4).

Lee la tabla de docs/quality/waivers.md y falla si algún waiver pasó su fecha límite.

Uso: python scripts/check_waivers.py [waivers.md] [AAAA-MM-DD]
"""

import sys
from datetime import date
from pathlib import Path

ARCHIVO_POR_DEFECTO = "docs/quality/waivers.md"
COLUMNA_ID = 0
COLUMNA_FECHA = 5
COLUMNA_ISSUE = 6


def _filas_de_waivers(texto: str) -> list[list[str]]:
    filas = (linea.strip().strip("|").split("|") for linea in texto.splitlines())
    return [[celda.strip() for celda in fila] for fila in filas if fila[0].strip().startswith("W-")]


def _fecha_limite(fila: list[str]) -> date:
    try:
        return date.fromisoformat(fila[COLUMNA_FECHA])
    except ValueError as error:
        raise ValueError(
            f"{fila[COLUMNA_ID]}: fecha límite inválida {fila[COLUMNA_FECHA]!r}"
        ) from error


def waivers_vencidos(texto: str, hoy: date) -> list[str]:
    """Devuelve una descripción por cada waiver cuya fecha límite ya pasó."""
    return [
        f"{fila[COLUMNA_ID]} ({fila[COLUMNA_ISSUE]}) venció el {fila[COLUMNA_FECHA]}"
        for fila in _filas_de_waivers(texto)
        if _fecha_limite(fila) < hoy
    ]


def main(argv: list[str]) -> int:
    archivo = Path(argv[0] if argv else ARCHIVO_POR_DEFECTO)
    hoy = date.fromisoformat(argv[1]) if len(argv) > 1 else date.today()
    vencidos = waivers_vencidos(archivo.read_text(encoding="utf-8"), hoy)
    for vencido in vencidos:
        sys.stdout.write(
            f"{vencido}: renueva el waiver con aprobación humana o paga la deuda (§15.4).\n"
        )
    return 1 if vencidos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
