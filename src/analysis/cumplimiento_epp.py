"""Resumen de cumplimiento de EPP para el reporte (SPEC/9 §8.4).

Por turno, empleado, zona y elemento: cantidad de infracciones, duración total y porcentaje del
tiempo en cumplimiento. La duración se cuenta hasta el corte del período: una infracción todavía
abierta, o que lo cruza, suma solo hasta ahí.

El porcentaje es 100 * (1 - tiempo en infracción / tiempo en la zona), acotado a [0, 100]. El
tiempo en la zona por persona llega como dato; si falta o es cero, el porcentaje es None ("sin
datos"): no se inventa.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import NamedTuple

SIN_TURNO = "sin turno"
SIN_IDENTIFICAR = "persona no identificada"
CIEN = 100


class InfraccionRegistrada(NamedTuple):
    """Infracción leída de la base; `fin` es None mientras sigue abierta."""

    persona: str | None
    zona: str
    elemento: str
    inicio: datetime
    fin: datetime | None


class FilaCumplimiento(NamedTuple):
    turno: str
    persona: str
    zona: str
    elemento: str
    cantidad: int
    duracion_total: timedelta
    porcentaje_cumplimiento: float | None


def resumir(
    infracciones: Iterable[InfraccionRegistrada],
    turnos: Mapping[str, str],
    exposicion: Mapping[tuple[str, str], timedelta],
    corte: datetime,
) -> list[FilaCumplimiento]:
    """Filas del reporte, ordenadas por turno, persona, zona y elemento."""
    grupos: defaultdict[tuple[str, str, str, str], list[timedelta]] = defaultdict(list)
    for infraccion in infracciones:
        persona = SIN_IDENTIFICAR if infraccion.persona is None else infraccion.persona
        turno = turnos.get(persona, SIN_TURNO)
        clave = (turno, persona, infraccion.zona, infraccion.elemento)
        grupos[clave].append(_duracion(infraccion, corte))
    return [
        _fila(clave, duraciones, exposicion.get(clave[1:3]))
        for clave, duraciones in sorted(grupos.items())
    ]


def _duracion(infraccion: InfraccionRegistrada, corte: datetime) -> timedelta:
    fin = corte if infraccion.fin is None else min(infraccion.fin, corte)
    return max(fin - infraccion.inicio, timedelta(0))


def _fila(
    clave: tuple[str, str, str, str], duraciones: list[timedelta], expuesto: timedelta | None
) -> FilaCumplimiento:
    total = sum(duraciones, timedelta(0))
    return FilaCumplimiento(*clave, len(duraciones), total, _porcentaje(total, expuesto))


def _porcentaje(en_infraccion: timedelta, expuesto: timedelta | None) -> float | None:
    if not expuesto:
        return None
    cumplido = max(1 - en_infraccion / expuesto, 0)
    return round(cumplido * CIEN, 1)
