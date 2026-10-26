"""Aviso al responsable de seguridad, tal como sale de la bandeja de salida (SPEC/9 §7.1)."""

from datetime import datetime
from enum import Enum
from typing import NamedTuple


class EstadoNotificacion(Enum):
    """Estado del aviso en la bandeja de salida; el valor es el que se guarda en la base."""

    PENDIENTE = "PENDIENTE"
    ENVIADA = "ENVIADA"
    # Se agotaron los reintentos: queda visible en la UI, nunca se descarta (P5).
    FALLIDA = "FALLIDA"
    # Detectada durante el piloto en modo sombra: no se avisa al salir de él (decisión del
    # 24/10/2026). Sigue visible en la UI y en los reportes.
    DESCARTADA = "DESCARTADA"


class Aviso(NamedTuple):
    """Una infracción pendiente de notificar.

    `id_aviso` es el id de la infracción y la clave de idempotencia: un reintento del mismo aviso
    nunca debe duplicarlo en un canal que lo soporte. `persona` es None si nadie fue reconocido.
    `intentos` cuenta los intentos fallidos previos.
    """

    id_aviso: int
    persona: str | None
    elemento: str
    zona: str
    inicio: datetime
    evidencia: str | None
    intentos: int
