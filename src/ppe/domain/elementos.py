"""Elementos de EPP, anclas corporales y estados de verificación (SPEC/9 §2.2 y §4.1).

Taxonomía v1 (decisión D3): casco y chaleco. Guantes, gafas y barbijo ya existen para la
2.ª iteración; la asociación es genérica por tipo de ancla y no necesita lógica extra.
"""

from enum import Enum


class TipoAncla(Enum):
    """Parte del cuerpo donde se verifica un elemento (ADR-002: anclas, no clases "sin-X").

    El valor es el nombre de la clase en la taxonomía del detector (§2.2).
    """

    CABEZA = "cabeza"
    MANOS = "manos"
    # El torso no se detecta: es la región central de la caja de la persona.
    TORSO = "torso"


class ElementoEPP(Enum):
    """Elemento de protección personal; el valor es su nombre en la configuración de zonas."""

    CASCO = "casco"
    CHALECO = "chaleco"
    GUANTES = "guantes"
    GAFAS = "gafas"
    BARBIJO = "barbijo"

    @property
    def ancla(self) -> TipoAncla:
        return _ANCLA_POR_ELEMENTO[self]


_ANCLA_POR_ELEMENTO = {
    ElementoEPP.CASCO: TipoAncla.CABEZA,
    ElementoEPP.GAFAS: TipoAncla.CABEZA,
    ElementoEPP.BARBIJO: TipoAncla.CABEZA,
    ElementoEPP.GUANTES: TipoAncla.MANOS,
    ElementoEPP.CHALECO: TipoAncla.TORSO,
}


class EstadoElemento(Enum):
    """Resultado de verificar un elemento en una persona; el valor es el texto para el usuario."""

    PRESENTE = "presente"
    AUSENTE = "ausente"
    # El ancla no se ve: no se puede afirmar ni negar el elemento, y no se alerta (AC-011).
    NO_VERIFICABLE = "no verificable"
