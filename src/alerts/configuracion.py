"""Canales de aviso configurados por variables de entorno (SPEC/9 §7.3; D1, D5).

Los secretos (secreto del webhook, contraseña SMTP) llegan por el entorno o el almacén de
credenciales que lo cargue, nunca por archivos del repositorio, y ningún mensaje de error los
repite. Un canal se activa si está su variable principal (la URL del webhook o el servidor SMTP)
y entonces exige todas las demás. Si el aviso nombra al empleado lo decide el negocio (D5): sin
esa variable, la configuración falla.
"""

import ssl
from collections.abc import Mapping
from datetime import timedelta

from src.alerts.application.ports import NotificadorPort
from src.alerts.canal_email import CanalEmail, ConfiguracionEmail, Credenciales
from src.alerts.canal_webhook import CanalWebhook, ConfiguracionWebhook
from src.alerts.canales import CanalesDeAviso
from src.alerts.domain.errores import ConfiguracionAlertasError
from src.alerts.domain.mensaje import DatosDeLaPersona
from src.alerts.evidencias import LectorEvidencias

NOMBRE_EMPLEADO = "EPP_ALERTAS_NOMBRE_EMPLEADO"
WEBHOOK_URL = "EPP_ALERTAS_WEBHOOK_URL"
SMTP_SERVIDOR = "EPP_ALERTAS_SMTP_SERVIDOR"
SMTP_USUARIO = "EPP_ALERTAS_SMTP_USUARIO"
# Es el nombre de la variable de entorno, no una contraseña.
SMTP_CONTRASENA = "EPP_ALERTAS_SMTP_CONTRASENA"  # pragma: allowlist secret


def datos_de_la_persona(entorno: Mapping[str, str]) -> DatosDeLaPersona:
    valor = _opcional(entorno, NOMBRE_EMPLEADO)
    if valor is None:
        raise ConfiguracionAlertasError(
            f"Falta {NOMBRE_EMPLEADO}: si el aviso nombra al empleado lo decide el negocio (D5) "
            "y no tiene valor por omisión"
        )
    try:
        return DatosDeLaPersona(valor)
    except ValueError as error:
        raise ConfiguracionAlertasError(
            f"{NOMBRE_EMPLEADO} debe ser 'incluir' u 'omitir': {valor}"
        ) from error


def configuracion_webhook(
    entorno: Mapping[str, str], contexto_tls: ssl.SSLContext
) -> ConfiguracionWebhook | None:
    url = _opcional(entorno, WEBHOOK_URL)
    if url is None:
        return None
    return ConfiguracionWebhook(
        url=url,
        secreto=_requerida(entorno, "EPP_ALERTAS_WEBHOOK_SECRETO").encode(),
        timeout=_segundos(entorno, "EPP_ALERTAS_WEBHOOK_TIMEOUT_S"),
        contexto_tls=contexto_tls,
    )


def configuracion_email(
    entorno: Mapping[str, str], contexto_tls: ssl.SSLContext
) -> ConfiguracionEmail | None:
    servidor = _opcional(entorno, SMTP_SERVIDOR)
    if servidor is None:
        return None
    destinatarios = _requerida(entorno, "EPP_ALERTAS_SMTP_DESTINATARIOS").split(",")
    return ConfiguracionEmail(
        servidor=servidor,
        puerto=_entero(entorno, "EPP_ALERTAS_SMTP_PUERTO"),
        remitente=_requerida(entorno, "EPP_ALERTAS_SMTP_REMITENTE"),
        destinatarios=tuple(filter(None, (destino.strip() for destino in destinatarios))),
        credenciales=_credenciales(entorno),
        timeout=_segundos(entorno, "EPP_ALERTAS_SMTP_TIMEOUT_S"),
        contexto_tls=contexto_tls,
    )


def canales_desde_entorno(
    entorno: Mapping[str, str], evidencias: LectorEvidencias, contexto_tls: ssl.SSLContext
) -> CanalesDeAviso:
    """Arma los canales configurados; sin ninguno, o sin la decisión D5, falla."""
    datos = datos_de_la_persona(entorno)
    canales: dict[str, NotificadorPort] = {}
    email = configuracion_email(entorno, contexto_tls)
    if email is not None:
        canales["email"] = CanalEmail(email, datos, evidencias)
    webhook = configuracion_webhook(entorno, contexto_tls)
    if webhook is not None:
        canales["webhook"] = CanalWebhook(webhook, datos, evidencias)
    return CanalesDeAviso(canales)


def _credenciales(entorno: Mapping[str, str]) -> Credenciales | None:
    usuario = _opcional(entorno, SMTP_USUARIO)
    contrasena = _opcional(entorno, SMTP_CONTRASENA)
    if usuario is None and contrasena is None:
        return None
    if usuario is None or contrasena is None:
        raise ConfiguracionAlertasError(f"{SMTP_USUARIO} y {SMTP_CONTRASENA} van juntas")
    return Credenciales(usuario, contrasena)


def _opcional(entorno: Mapping[str, str], nombre: str) -> str | None:
    """El valor sin espacios a los costados; una variable vacía cuenta como ausente."""
    return entorno.get(nombre, "").strip() or None


def _requerida(entorno: Mapping[str, str], nombre: str) -> str:
    valor = _opcional(entorno, nombre)
    if valor is None:
        raise ConfiguracionAlertasError(f"Falta la variable de entorno {nombre}")
    return valor


def _entero(entorno: Mapping[str, str], nombre: str) -> int:
    valor = _requerida(entorno, nombre)
    try:
        return int(valor)
    except ValueError as error:
        raise ConfiguracionAlertasError(f"{nombre} debe ser un número: {valor}") from error


def _segundos(entorno: Mapping[str, str], nombre: str) -> timedelta:
    valor = _requerida(entorno, nombre)
    try:
        return timedelta(seconds=float(valor))
    except ValueError as error:
        raise ConfiguracionAlertasError(f"{nombre} debe ser un número: {valor}") from error
