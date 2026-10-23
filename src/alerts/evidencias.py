"""Lectura de la imagen que acompaña al aviso (SPEC/9 §4.6, AC-015; CLAUDE.md §9).

Solo se leen imágenes de la carpeta de evidencias del tenant. Un aviso de seguridad no se retiene
por su adjunto: si la imagen ya no existe (la retención pudo purgarla) se avisa sin imagen, y si
la referencia apunta fuera de la carpeta se registra como error y tampoco se adjunta.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LectorEvidencias:
    """Lee imágenes de evidencia, sin salir de la carpeta del tenant."""

    def __init__(self, carpeta: Path) -> None:
        self._carpeta = carpeta.resolve()

    def leer(self, referencia: str | None) -> bytes | None:
        """Bytes de la imagen, o None si el aviso no tiene una que se pueda adjuntar."""
        if referencia is None:
            return None
        ruta = Path(referencia).resolve()
        if not ruta.is_relative_to(self._carpeta):
            logger.error("Imagen fuera de la carpeta de evidencias, no se adjunta: %s", referencia)
            return None
        try:
            return ruta.read_bytes()
        except FileNotFoundError:
            logger.warning("La imagen del aviso ya no existe: %s", referencia)
            return None
