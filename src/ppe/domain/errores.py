"""Excepciones tipadas del dominio de EPP (CLAUDE.md §3: errores como excepciones de dominio)."""


class DominioEPPError(Exception):
    """Base de todos los errores del dominio de EPP."""


class CajaInvalidaError(DominioEPPError):
    """La caja tiene coordenadas no finitas o esquinas invertidas."""


class ConfiguracionInvalidaError(DominioEPPError):
    """Un parámetro de configuración del dominio está fuera de su rango válido."""


class ObservacionInvalidaError(DominioEPPError):
    """Lo observado en un frame es incoherente (por ejemplo, un track_id repetido)."""


class RelojRetrocedioError(DominioEPPError):
    """El reloj inyectado devolvió un instante anterior al último observado."""


class ElementoDesconocidoError(ConfiguracionInvalidaError):
    """La configuración nombra un elemento de EPP que no existe."""


class ZonaSinPoligonoError(ConfiguracionInvalidaError):
    """Una zona de la configuración no tiene un polígono válido."""
