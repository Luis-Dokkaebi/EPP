"""Selector de fecha propio y mínimo: reemplaza a tkcalendar (GPLv3), SPEC/9 §1.11.

La validación vive en funciones puras, probables sin Tk; el widget solo muestra el texto.
"""

import re
import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Any

FORMATO_FECHA = "%Y-%m-%d"
_AAAA_MM_DD = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
ANCHO_EN_CARACTERES = 12


class FechaInvalidaError(ValueError):
    """El texto no es una fecha AAAA-MM-DD existente."""


class RangoDeFechasInvalidoError(ValueError):
    """La fecha inicial del reporte es posterior a la final."""


def leer_fecha(texto: str) -> date:
    try:
        if not _AAAA_MM_DD.fullmatch(texto):
            raise ValueError(texto)
        return datetime.strptime(texto, FORMATO_FECHA).date()
    except ValueError as causa:
        raise FechaInvalidaError(
            f"Fecha inválida: «{texto}». Usa el formato AAAA-MM-DD."
        ) from causa


def consultar_reporte(
    desde: str,
    hasta: str,
    empleado: str,
    consulta: Callable[[str, str, str], Sequence[Any]],
) -> Sequence[Any]:
    """Valida el rango antes de consultar: un rango inválido no llega a la base de datos."""
    inicio, fin = leer_fecha(desde), leer_fecha(hasta)
    if inicio > fin:
        raise RangoDeFechasInvalidoError(
            f"La fecha «Desde» ({desde}) es posterior a «Hasta» ({hasta})."
        )
    return consulta(desde, hasta, empleado)


class SelectorDeFecha(tk.Entry):
    """Campo de texto con la fecha en AAAA-MM-DD; `get()` devuelve el texto tal cual."""

    def __init__(self, master: tk.Misc, inicial: date) -> None:
        super().__init__(master, width=ANCHO_EN_CARACTERES)
        self.set_date(inicial)

    def set_date(self, fecha: date) -> None:
        self.delete(0, tk.END)
        self.insert(tk.END, fecha.strftime(FORMATO_FECHA))
