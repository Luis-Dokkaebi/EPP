"""Arquitectura verificada por máquina (SPEC/9 §0.4, CLAUDE.md §16).

Corre import-linter con `.importlinter` y traduce cada import prohibido a un mensaje que dice
cómo corregirlo, para que el agente se autocorrija (principio H3 del plan).

Uso: python scripts/check_architecture.py [.importlinter]
"""

import io
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout

from importlinter.cli import lint_imports

CONFIGURACION_POR_DEFECTO = ".importlinter"
PATRON_VIOLACION = re.compile(r"^-\s+(?P<origen>\S+) -> (?P<destino>\S+) \(l\.(?P<linea>\d+)")
PISTA_MOTOR = (
    "depende de DetectorPort (src/inference/ports.py) y deja el motor en src/inference/adapters/."
)
PISTA_GUI = "la GUI depende del dominio, nunca al revés; expón un presentador o publica un evento."
PISTA_GENERICA = (
    "las dependencias apuntan hacia adentro: recibe el dato por parámetro o define un puerto "
    "en la capa de aplicación y deja el detalle en un adaptador."
)
PISTAS = {
    "cv2": (
        "recibe la imagen o el dibujo a través de un puerto (por ejemplo AlmacenEvidenciasPort) "
        "y deja cv2 en la capa de adaptadores."
    ),
    "ultralytics": PISTA_MOTOR,
    "torch": PISTA_MOTOR,
    "onnxruntime": PISTA_MOTOR,
    "rfdetr": PISTA_MOTOR,
    "customtkinter": PISTA_GUI,
    "src.gui": PISTA_GUI,
}


def _pista(destino: str) -> str:
    for prefijo, pista in PISTAS.items():
        if destino == prefijo or destino.startswith(f"{prefijo}."):
            return pista
    return PISTA_GENERICA


def traducir(salida: str) -> list[str]:
    """Convierte la salida de import-linter en mensajes con la corrección sugerida."""
    coincidencias = (PATRON_VIOLACION.match(linea.strip()) for linea in salida.splitlines())
    return [
        f"{m['origen']} importa {m['destino']} (línea {m['linea']}): {_pista(m['destino'])}"
        for m in coincidencias
        if m
    ]


@contextmanager
def _conservando_loggers() -> Iterator[None]:
    """import-linter usa `dictConfig`, que deshabilita los loggers ya creados: se restauran."""
    loggers = [
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    estados = [(logger, logger.disabled) for logger in loggers]
    try:
        yield
    finally:
        for logger, deshabilitado in estados:
            logger.disabled = deshabilitado


def main(argv: list[str]) -> int:
    configuracion = argv[0] if argv else CONFIGURACION_POR_DEFECTO
    salida = io.StringIO()
    with redirect_stdout(salida), _conservando_loggers():
        codigo = lint_imports(config_filename=configuracion, no_cache=True)
    sys.stdout.write(salida.getvalue())
    for mensaje in traducir(salida.getvalue()):
        sys.stdout.write(f"{mensaje}\n")
    return 0 if codigo == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
