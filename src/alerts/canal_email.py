"""Canal de aviso por email (SPEC/9 §7.2, §7.3; D1: email y webhook).

`smtplib` de la biblioteca estándar, sin dependencias nuevas. Siempre con STARTTLS: si el
servidor no lo ofrece o su certificado no es confiable, no se envía nada en claro y la entrega
falla. La imagen del evento va adjunta. El Message-ID depende solo del id del aviso, así un
reintento lleva el mismo identificador y el cliente de correo puede reconocer el duplicado. La
contraseña sale de una variable de entorno, nunca del código ni de la base (§9).
"""

import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from typing import NamedTuple

from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import NotificacionFallidaError
from src.alerts.domain.mensaje import DatosDeLaPersona, redactar
from src.alerts.evidencias import LectorEvidencias


class Credenciales(NamedTuple):
    usuario: str
    contrasena: str


class ConfiguracionEmail(NamedTuple):
    """Servidor SMTP y destinatarios; sin credenciales, el canal no se autentica."""

    servidor: str
    puerto: int
    remitente: str
    destinatarios: tuple[str, ...]
    credenciales: Credenciales | None
    timeout: timedelta
    contexto_tls: ssl.SSLContext


class CanalEmail:
    """Implementa NotificadorPort enviando un correo por SMTP con STARTTLS."""

    def __init__(
        self,
        configuracion: ConfiguracionEmail,
        datos: DatosDeLaPersona,
        evidencias: LectorEvidencias,
    ) -> None:
        self._configuracion = configuracion
        self._datos = datos
        self._evidencias = evidencias

    def enviar(self, aviso: Aviso) -> None:
        correo = self._correo(aviso)
        configuracion = self._configuracion
        try:
            with smtplib.SMTP(
                configuracion.servidor,
                configuracion.puerto,
                timeout=configuracion.timeout.total_seconds(),
            ) as smtp:
                smtp.starttls(context=configuracion.contexto_tls)
                if configuracion.credenciales is not None:
                    smtp.login(*configuracion.credenciales)
                smtp.send_message(correo)
        except (smtplib.SMTPException, OSError) as error:
            raise NotificacionFallidaError(f"No se pudo enviar el correo: {error}") from error

    def _correo(self, aviso: Aviso) -> EmailMessage:
        mensaje = redactar(aviso, self._datos)
        remitente = self._configuracion.remitente
        correo = EmailMessage()
        correo["Subject"] = mensaje.asunto
        correo["From"] = remitente
        correo["To"] = ", ".join(self._configuracion.destinatarios)
        correo["Message-ID"] = f"<epp-aviso-{aviso.id_aviso}@{remitente.rpartition('@')[2]}>"
        correo.set_content(mensaje.cuerpo)
        imagen = self._evidencias.leer(aviso.evidencia)
        if imagen is not None:
            correo.add_attachment(
                imagen, maintype="image", subtype="jpeg", filename=f"aviso-{aviso.id_aviso}.jpg"
            )
        return correo
