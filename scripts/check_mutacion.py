"""Puntaje de mutación por archivo a partir de la caché de mutmut 2.x (CLAUDE.md §7).

Uso: python scripts/check_mutacion.py [.mutmut-cache] [umbral_porcentaje]
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ESTADOS_MUERTOS = ("ok_killed", "ok_suspicious")
ESTADOS_SOBREVIVIENTES = ("bad_survived", "bad_timeout")
ESTADO_SIN_PROBAR = "untested"
UMBRAL_POR_DEFECTO = 85.0
PORCENTAJE_TOTAL = 100.0

CONSULTA = """
SELECT SourceFile.filename, Mutant.status, COUNT(*)
FROM Mutant
JOIN Line ON Mutant.line = Line.id
JOIN SourceFile ON Line.sourcefile = SourceFile.id
GROUP BY SourceFile.filename, Mutant.status
ORDER BY SourceFile.filename
"""


@dataclass(frozen=True)
class ResultadoMutacion:
    archivo: str
    muertos: int
    sobrevivientes: int
    sin_probar: int

    @property
    def puntaje(self) -> float:
        evaluados = self.muertos + self.sobrevivientes
        return PORCENTAJE_TOTAL if evaluados == 0 else PORCENTAJE_TOTAL * self.muertos / evaluados


def leer_resultados(cache: Path) -> list[ResultadoMutacion]:
    """Agrupa los estados de los mutantes por archivo fuente."""
    conteos: dict[str, dict[str, int]] = {}
    with sqlite3.connect(cache) as conexion:
        for archivo, estado, cantidad in conexion.execute(CONSULTA):
            conteos.setdefault(archivo, {})[estado] = cantidad
    return [
        ResultadoMutacion(
            archivo=archivo,
            muertos=sum(estados.get(e, 0) for e in ESTADOS_MUERTOS),
            sobrevivientes=sum(estados.get(e, 0) for e in ESTADOS_SOBREVIVIENTES),
            sin_probar=estados.get(ESTADO_SIN_PROBAR, 0),
        )
        for archivo, estados in conteos.items()
    ]


def _errores(resultado: ResultadoMutacion, umbral: float) -> list[str]:
    errores = []
    if resultado.sin_probar:
        errores.append(f"{resultado.archivo}: {resultado.sin_probar} mutantes sin probar")
    if resultado.puntaje < umbral:
        errores.append(
            f"{resultado.archivo}: {resultado.puntaje:.1f} % < {umbral:.1f} %. Mata los "
            "sobrevivientes con pruebas nuevas (`mutmut results` / `mutmut show <id>`); "
            "los equivalentes van en docs/quality/mutantes_equivalentes.md."
        )
    return errores


def main(argv: list[str]) -> int:
    cache = Path(argv[0] if argv else ".mutmut-cache")
    umbral = float(argv[1]) if len(argv) > 1 else UMBRAL_POR_DEFECTO
    errores = []
    for resultado in leer_resultados(cache):
        sys.stdout.write(f"{resultado.archivo}: {resultado.puntaje:.1f} % ({resultado})\n")
        errores += _errores(resultado, umbral)
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
