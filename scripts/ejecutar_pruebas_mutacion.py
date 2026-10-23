"""Runner de pruebas para mutmut 2.x (CLAUDE.md §7).

mutmut 2.4 solo considera "muerto" un mutante cuando el comando de pruebas sale con código 1.
Un mutante que rompe la importación hace que pytest salga con 2 y quedaría como sobreviviente
falso. Este runner traduce cualquier falla a 1.

Uso: mutmut run --runner "python scripts/ejecutar_pruebas_mutacion.py -x -q tests/test_x.py"
"""

import sys

import pytest

CODIGO_EXITO = 0
CODIGO_FALLA_PARA_MUTMUT = 1


def codigo_para_mutmut(codigo_pytest: int) -> int:
    """0 si pytest pasó; 1 ante cualquier otro resultado."""
    return CODIGO_EXITO if codigo_pytest == CODIGO_EXITO else CODIGO_FALLA_PARA_MUTMUT


def main(argv: list[str]) -> int:
    return codigo_para_mutmut(int(pytest.main(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
