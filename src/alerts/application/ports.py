"""Puertos de salida de las notificaciones (SPEC/9 §7.1; skill hexagonal-architecture).

El despachador depende de estas interfaces; la base (bandeja de salida), los canales (email,
webhook) y el reloj del sistema las implementan fuera del dominio.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from src.alerts.domain.aviso import Aviso


class RelojPort(Protocol):
    """Fuente del instante actual; en las pruebas, un reloj falso."""

    def ahora(self) -> datetime:
        """Instante actual, con zona horaria."""
        ...


class BandejaSalidaPort(Protocol):
    """Avisos guardados antes de notificar (outbox): sobreviven a cortes de red y reinicios."""

    def pendientes(self, ahora: datetime) -> Sequence[Aviso]:
        """Avisos PENDIENTES cuyo próximo intento ya llegó, del más antiguo al más nuevo."""
        ...

    def marcar_enviada(self, id_aviso: int) -> None:
        """El canal recibió el aviso: pasa a ENVIADA."""

    def reprogramar(self, id_aviso: int, intentos: int, proximo_intento: datetime) -> None:
        """El intento falló: guarda los intentos fallidos y cuándo reintentar."""

    def marcar_fallida(self, id_aviso: int, intentos: int) -> None:
        """Se agotaron los reintentos: pasa a FALLIDA, visible en la UI (nunca se descarta)."""


class NotificadorPort(Protocol):
    """Canal de aviso al responsable de seguridad."""

    def enviar(self, aviso: Aviso) -> None:
        """Entrega el aviso o lanza NotificacionFallidaError si el canal no lo recibió."""
