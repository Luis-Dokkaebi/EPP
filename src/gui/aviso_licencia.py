"""Aviso de días restantes de la licencia de prueba (SPEC/10 F-03.5).

Solo decide el texto y la urgencia; la ventana principal lo pinta (rojo los últimos tres días).
"""

from typing import NamedTuple, Protocol

DIAS_DE_URGENCIA = 3


class LicenciaConVigencia(Protocol):
    def es_prueba(self) -> bool: ...

    def dias_restantes(self) -> int | None: ...


class AvisoDeLicencia(NamedTuple):
    texto: str
    urgente: bool


def _texto(dias: int) -> str:
    if dias == 0:
        return "Prueba: vence hoy"
    if dias == 1:
        return "Prueba: queda 1 día"
    return f"Prueba: quedan {dias} días"


def aviso_de_prueba(licencia: LicenciaConVigencia) -> AvisoDeLicencia | None:
    """El aviso para una licencia de prueba vigente; None para cualquier otra."""
    dias = licencia.dias_restantes()
    if dias is None or not licencia.es_prueba():
        return None
    return AvisoDeLicencia(_texto(dias), urgente=dias <= DIAS_DE_URGENCIA)
