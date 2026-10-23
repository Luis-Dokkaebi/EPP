"""Texto del aviso al responsable de seguridad (SPEC/9 §4.6, §7.3).

El nombre del empleado solo aparece si el negocio lo permite (D5, pendiente): quien despliega lo
fija con `DatosDeLaPersona` y no hay valor por omisión. Una persona sin reconocer siempre figura
como "persona no identificada".
"""

from enum import Enum
from typing import NamedTuple

from src.alerts.domain.aviso import Aviso

SIN_IDENTIFICAR = "persona no identificada"
NOMBRE_OMITIDO = "persona identificada (nombre omitido)"


class DatosDeLaPersona(Enum):
    """Si el aviso puede nombrar al empleado reconocido; el valor es el texto de configuración."""

    NOMBRE = "incluir"
    ANONIMO = "omitir"


class Mensaje(NamedTuple):
    asunto: str
    cuerpo: str


def describir_persona(persona: str | None, datos: DatosDeLaPersona) -> str:
    if persona is None:
        return SIN_IDENTIFICAR
    if datos is DatosDeLaPersona.ANONIMO:
        return NOMBRE_OMITIDO
    return persona


def redactar(aviso: Aviso, datos: DatosDeLaPersona) -> Mensaje:
    persona = describir_persona(aviso.persona, datos)
    lineas = (
        f"Persona: {persona}",
        f"Elemento faltante: {aviso.elemento}",
        f"Zona: {aviso.zona}",
        f"Desde: {aviso.inicio.isoformat()}",
        f"Aviso N.º {aviso.id_aviso}",
    )
    return Mensaje(
        asunto=f"EPP: {persona} sin {aviso.elemento} en {aviso.zona}", cuerpo="\n".join(lineas)
    )
