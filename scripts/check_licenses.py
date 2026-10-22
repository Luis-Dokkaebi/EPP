"""Gate de licencias del runtime (SPEC/9 §0.5, AC-001).

Clasifica la licencia de cada paquete instalado (salida JSON de pip-licenses) en permitida,
prohibida o pendiente de revisión humana. Una licencia prohibida o pendiente solo pasa si
docs/legal/licencias_revisadas.json registra una decisión aprobada por un humano para esa
misma licencia declarada.

Uso: python scripts/check_licenses.py [--paquetes salida.json] [--revisadas revisadas.json]
     Sin --paquetes, corre pip-licenses sobre el entorno actual (debe ser el de runtime).
"""

import argparse
import json
import re
import subprocess
import sys
from enum import IntEnum
from pathlib import Path

REVISADAS_POR_DEFECTO = "docs/legal/licencias_revisadas.json"
SEPARADOR_ALTERNATIVAS = re.compile(r"\s+OR\s+", re.IGNORECASE)
SEPARADOR_CONJUNTO = re.compile(r"\s+AND\s+|;", re.IGNORECASE)


class Veredicto(IntEnum):
    """Ordenado por gravedad: el peor de un conjunto AND decide."""

    PERMITIDA = 0
    REVISION = 1
    PROHIBIDA = 2


# El orden importa: LGPL se revisa antes que GPL porque su nombre contiene "General Public".
# Lo que no coincide con ninguna regla (MPL, licencias desconocidas o vacías) va a revisión.
REGLAS = (
    (re.compile(r"affero|agpl", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"lgpl|lesser general|library general", re.IGNORECASE), Veredicto.REVISION),
    (re.compile(r"\bgpl|general public license", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"sspl|server side public", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"\bnc\b|non-?commercial", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"\bpml\b|commercial|proprietary", re.IGNORECASE), Veredicto.PROHIBIDA),
    (
        re.compile(
            r"\bmit\b|\bbsd\b|bsd-|apache|\bisc\b|\bpsf|python software foundation|\bbsl\b|"
            r"boost|hpnd|historical permission|\bcc0\b|unlicense|zlib",
            re.IGNORECASE,
        ),
        Veredicto.PERMITIDA,
    ),
)


def _clasificar_termino(termino: str) -> Veredicto:
    for patron, veredicto in REGLAS:
        if patron.search(termino):
            return veredicto
    return Veredicto.REVISION


def _clasificar_conjunto(conjunto: str) -> Veredicto:
    return max(_clasificar_termino(termino) for termino in SEPARADOR_CONJUNTO.split(conjunto))


def clasificar_licencia(licencia: str) -> Veredicto:
    """Las alternativas OR eligen la mejor; los términos AND o `;` exigen todos."""
    return min(_clasificar_conjunto(opcion) for opcion in SEPARADOR_ALTERNATIVAS.split(licencia))


def _aprobada(paquete: dict[str, str], revisadas: dict[str, dict[str, str | None]]) -> bool:
    revision = revisadas.get(paquete["Name"].lower(), {})
    return bool(revision.get("aprobado_por")) and (
        revision.get("licencia_declarada") == paquete["License"]
    )


def _error(paquete: dict[str, str], veredicto: Veredicto) -> str:
    identificacion = f"{paquete['Name']} {paquete['Version']}"
    if veredicto is Veredicto.PROHIBIDA:
        return (
            f"{identificacion}: licencia prohibida en el runtime ({paquete['License']}). "
            "Reemplázalo por una alternativa Apache/MIT o registra la aprobación legal en "
            "docs/legal/."
        )
    return (
        f"{identificacion}: licencia que exige revisión humana ({paquete['License']}). "
        "Registra la decisión aprobada en docs/legal/licencias_revisadas.json."
    )


def evaluar_paquetes(
    paquetes: list[dict[str, str]], revisadas: dict[str, dict[str, str | None]]
) -> list[str]:
    """Un mensaje por paquete no permitido y sin revisión aprobada vigente."""
    return [
        _error(paquete, veredicto)
        for paquete in paquetes
        if (veredicto := clasificar_licencia(paquete["License"])) is not Veredicto.PERMITIDA
        and not _aprobada(paquete, revisadas)
    ]


def paquetes_instalados() -> list[dict[str, str]]:
    # S603: ejecuta pip-licenses del mismo intérprete; los argumentos son fijos.
    salida = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--from=mixed", "--format=json"],  # noqa: S603
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paquetes: list[dict[str, str]] = json.loads(salida)
    return paquetes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paquetes", type=Path)
    parser.add_argument("--revisadas", type=Path, default=Path(REVISADAS_POR_DEFECTO))
    argumentos = parser.parse_args(argv)
    paquetes = (
        json.loads(argumentos.paquetes.read_text(encoding="utf-8"))
        if argumentos.paquetes
        else paquetes_instalados()
    )
    revisadas = json.loads(argumentos.revisadas.read_text(encoding="utf-8"))
    errores = evaluar_paquetes(paquetes, {nombre.lower(): r for nombre, r in revisadas.items()})
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
