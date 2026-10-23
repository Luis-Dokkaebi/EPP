"""Excepciones tipadas de las notificaciones (CLAUDE.md §3: errores como excepciones de dominio)."""


class AlertasError(Exception):
    """Base de todos los errores de las notificaciones."""


class ConfiguracionAlertasError(AlertasError):
    """Un parámetro de reintentos, del circuito o de un canal está fuera de su rango válido."""


class NotificacionFallidaError(AlertasError):
    """El canal no entregó el aviso; el despachador lo reintentará según la política."""
