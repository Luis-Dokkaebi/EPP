"""Cómo se nombra la cámara activa en la interfaz.

Una cámara IP se configura con una URL que lleva usuario y contraseña: en pantalla solo se
muestra el equipo. El texto se recorta para que no ensanche la barra lateral.
"""

from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

LARGO_MAXIMO = 34
RECORTE = "…"


def describir_camara(camara: int | str) -> str:
    """ "índice N" para una cámara local, el equipo para una IP o el nombre de un archivo."""
    if isinstance(camara, int):
        return f"índice {camara}"
    equipo = urlsplit(camara).hostname if "://" in camara else None
    if equipo:
        return _recortar(f"cámara IP {equipo}")
    nombre = PurePosixPath(PureWindowsPath(camara).name).name
    return _recortar(f"archivo {nombre}")


def _recortar(texto: str) -> str:
    if len(texto) <= LARGO_MAXIMO:
        return texto
    return texto[: LARGO_MAXIMO - len(RECORTE)] + RECORTE
