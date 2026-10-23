"""Puntaje de mutación por archivo a partir de la caché de mutmut 2.x (CLAUDE.md §7).

Los sobrevivientes equivalentes documentados en docs/quality/mutantes_equivalentes.md (una
mutación por cada `...` de la columna "Mutación") no cuentan como huecos de prueba (§7).

Uso: python scripts/check_mutacion.py [.mutmut-cache] [umbral_porcentaje] [equivalentes.md]
"""

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ESTADOS_MUERTOS = ("ok_killed", "ok_suspicious")
ESTADOS_SOBREVIVIENTES = ("bad_survived", "bad_timeout")
ESTADO_SIN_PROBAR = "untested"
UMBRAL_POR_DEFECTO = 85.0
EQUIVALENTES_POR_DEFECTO = "docs/quality/mutantes_equivalentes.md"
SEPARADOR_DE_CELDAS = re.compile(r"(?<!\\)\|")
MUTACION_ENTRE_COMILLAS = re.compile(r"`[^`]+`")
COLUMNA_ARCHIVO = 1
COLUMNA_MUTACION = 3
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
    equivalentes: int = 0

    @property
    def puntaje(self) -> float:
        """Porcentaje de muertos sin contar los sobrevivientes equivalentes documentados."""
        sobrevivientes_reales = max(0, self.sobrevivientes - self.equivalentes)
        evaluados = self.muertos + sobrevivientes_reales
        return PORCENTAJE_TOTAL if evaluados == 0 else PORCENTAJE_TOTAL * self.muertos / evaluados


def equivalentes_documentados(texto: str) -> dict[str, int]:
    """Mutaciones equivalentes por archivo según la tabla de docs/quality (una por `...`)."""
    conteo: dict[str, int] = {}
    for linea in texto.splitlines():
        celdas = SEPARADOR_DE_CELDAS.split(linea)
        if len(celdas) > COLUMNA_MUTACION and celdas[COLUMNA_ARCHIVO].strip().startswith("`"):
            archivo = celdas[COLUMNA_ARCHIVO].strip().strip("`")
            mutaciones = len(MUTACION_ENTRE_COMILLAS.findall(celdas[COLUMNA_MUTACION]))
            conteo[archivo] = conteo.get(archivo, 0) + mutaciones
    return conteo


def leer_resultados(
    cache: Path, equivalentes: dict[str, int] | None = None
) -> list[ResultadoMutacion]:
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
            equivalentes=(equivalentes or {}).get(archivo, 0),
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", nargs="?", type=Path, default=Path(".mutmut-cache"))
    parser.add_argument("umbral", nargs="?", type=float, default=UMBRAL_POR_DEFECTO)
    parser.add_argument("tabla", nargs="?", type=Path, default=Path(EQUIVALENTES_POR_DEFECTO))
    argumentos = parser.parse_args(argv)
    cache, umbral, tabla = argumentos.cache, argumentos.umbral, argumentos.tabla
    # Sin tabla no se descuenta nada: el puntaje solo puede quedar más exigente.
    equivalentes = equivalentes_documentados(
        tabla.read_text(encoding="utf-8") if tabla.is_file() else ""
    )
    errores = []
    for resultado in leer_resultados(cache, equivalentes):
        sys.stdout.write(f"{resultado.archivo}: {resultado.puntaje:.1f} % ({resultado})\n")
        errores += _errores(resultado, umbral)
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
