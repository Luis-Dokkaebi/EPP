"""Cómo se muestra el cumplimiento de cada persona en el video (SPEC/9 §8.1).

- INFRACCION (rojo): falta un elemento exigido; la ausencia ya viene confirmada por la ventana
  temporal, así que el rojo coincide con la infracción.
- NO_VERIFICABLE (gris): no falta nada, pero algo exigido no se puede verificar.
- CUMPLE (verde): todo lo exigido está presente, o no se exige nada.

Cada elemento exigido lleva su etiqueta, en el orden de ElementoEPP. Sin dibujo: el adaptador de
video decide colores y trazo.
"""

from enum import Enum
from typing import NamedTuple

from src.ppe.application.evaluar_cumplimiento import EstadoCumplimiento
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento


class SituacionVisual(Enum):
    """Situación de la persona en el video; el valor es el texto para el usuario."""

    CUMPLE = "cumple"
    INFRACCION = "infracción"
    NO_VERIFICABLE = "no verificable"


class VistaPersona(NamedTuple):
    situacion: SituacionVisual
    etiquetas: tuple[str, ...]


def vista_de(estado: EstadoCumplimiento) -> VistaPersona:
    exigidos = [elemento for elemento in ElementoEPP if elemento in estado.exigidos]
    estados = [estado.estados[elemento] for elemento in exigidos]
    etiquetas = tuple(map(_etiqueta, exigidos, estados))
    if EstadoElemento.AUSENTE in estados:
        return VistaPersona(SituacionVisual.INFRACCION, etiquetas)
    if EstadoElemento.NO_VERIFICABLE in estados:
        return VistaPersona(SituacionVisual.NO_VERIFICABLE, etiquetas)
    return VistaPersona(SituacionVisual.CUMPLE, etiquetas)


def _etiqueta(elemento: ElementoEPP, estado: EstadoElemento) -> str:
    nombre = elemento.value
    if estado is EstadoElemento.AUSENTE:
        return f"Sin {nombre}"
    if estado is EstadoElemento.NO_VERIFICABLE:
        return f"{nombre.capitalize()} ?"
    return nombre.capitalize()
