"""Validación de la configuración del dominio de EPP en el borde (CLAUDE.md §9).

Los umbrales de negocio no tienen valores por defecto (D4 pendiente): los fija quien despliega y
un valor fuera de rango falla en voz alta al construir la configuración.
"""

from datetime import timedelta

from src.ppe.domain.errores import ConfiguracionInvalidaError


def exigir_fraccion(nombre: str, valor: float) -> float:
    """Devuelve `valor` si está en (0, 1]; si no, falla nombrando el parámetro."""
    if not 0 < valor <= 1:
        raise ConfiguracionInvalidaError(f"{nombre} debe estar en (0, 1]: {valor}")
    return valor


def exigir_duracion_positiva(nombre: str, valor: timedelta) -> timedelta:
    """Devuelve `valor` si es una duración mayor que cero; si no, falla nombrando el parámetro."""
    if valor <= timedelta(0):
        raise ConfiguracionInvalidaError(f"{nombre} debe ser positivo: {valor}")
    return valor


def exigir_al_menos_uno(nombre: str, valor: int) -> int:
    """Devuelve `valor` si es un entero de al menos 1; si no, falla nombrando el parámetro."""
    if valor < 1:
        raise ConfiguracionInvalidaError(f"{nombre} debe ser al menos 1: {valor}")
    return valor
