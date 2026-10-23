"""Guardar el polígono de una zona sin perder su EPP exigido (SPEC/9 §8.3, §6.3; TASK-5.3).

El nombre es una entrada del usuario: solo admite letras (también con acentos y ñ), números,
'_', '-' y espacios simples entre palabras, así nunca lleva separadores de ruta ni comillas. El
archivo se escribe en v2 con escribir_zonas (respalda un v1 y no pisa uno corrupto). Si la zona
ya existía, conserva su EPP exigido y su lugar; si no, se agrega al final sin EPP.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import escribir_zonas, leer_zonas

NOMBRE_VALIDO = re.compile(r"[\w-]+(?: [\w-]+)*")


class NombreDeZonaInvalidoError(ValueError):
    """El nombre de la zona tiene caracteres no permitidos o está vacío."""


def guardar_poligono(ruta: Path, nombre: str, puntos: Sequence[tuple[float, float]]) -> None:
    """Crea la zona `nombre` o reemplaza su polígono, conservando su EPP exigido."""
    if NOMBRE_VALIDO.fullmatch(nombre) is None:
        raise NombreDeZonaInvalidoError(
            f"El nombre de zona solo admite letras, números, espacios, '_' y '-': {nombre!r}"
        )
    poligono = tuple((float(x), float(y)) for x, y in puntos)
    zonas = list(leer_zonas(ruta))
    previa = next((zona for zona in zonas if zona.nombre == nombre), None)
    exigidos = frozenset() if previa is None else previa.exigidos
    nueva = ReglaZona(nombre, poligono, exigidos)
    if previa is None:
        zonas.append(nueva)
    else:
        zonas[zonas.index(previa)] = nueva
    escribir_zonas(ruta, zonas)
