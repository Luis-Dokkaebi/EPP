"""Excepciones tipadas del dominio de EPP (CLAUDE.md §3: errores como excepciones de dominio)."""


class DominioEPPError(Exception):
    """Base de todos los errores del dominio de EPP."""


class CajaInvalidaError(DominioEPPError):
    """La caja tiene coordenadas no finitas o esquinas invertidas."""
