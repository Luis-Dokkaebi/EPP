"""Aviso al responsable de seguridad, tal como sale de la bandeja de salida (SPEC/9 §7.1)."""

from datetime import datetime
from typing import NamedTuple


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
