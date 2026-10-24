"""Deja en la carpeta de reportes del gate qué prueba está corriendo (issue #37).

Un crash nativo (por ejemplo, un panic de Tcl en Windows, código 0x80000003) mata a pytest sin
traza: el archivo sobrevive y viaja en el artefacto de la CI con el nombre de la prueba.
"""

from collections.abc import Mapping
from pathlib import Path

ARCHIVO = "prueba-en-curso.txt"


def anotar(nodeid: str, entorno: Mapping[str, str]) -> None:
    carpeta = entorno.get("GATE_REPORTES")
    if not carpeta:
        return
    destino = Path(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / ARCHIVO).write_text(f"{nodeid}\n", encoding="utf-8")
