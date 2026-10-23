"""Canal de aviso por webhook (SPEC/9 §7.2, §7.3; D1: email y webhook).

POST con un cuerpo JSON firmado con HMAC-SHA256 (encabezado `X-EPP-Firma`) y la clave de
idempotencia del aviso (`Idempotency-Key`): un reintento repite exactamente el mismo pedido y el
receptor puede descartar el duplicado. Solo https, salvo hacia la propia máquina (un relé local);
no sigue redirecciones. Cualquier falla de red o respuesta que no sea 2xx es una
NotificacionFallidaError, que el despachador reintenta. Los mensajes de error no repiten la URL,
que puede llevar un token.
"""

import base64
import hashlib
import hmac
import json
import ssl
import urllib.error
import urllib.request
from datetime import timedelta
from typing import NamedTuple

from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import NotificacionFallidaError
from src.alerts.domain.mensaje import DatosDeLaPersona, describir_persona, redactar
from src.alerts.evidencias import LectorEvidencias

PROPIA_MAQUINA = frozenset({"127.0.0.1", "::1", "localhost"})


class ConfiguracionWebhook(NamedTuple):
    """Destino del webhook. El secreto sale de una variable de entorno, nunca del código."""

    url: str
    secreto: bytes
    timeout: timedelta
    contexto_tls: ssl.SSLContext


class CanalWebhook:
    """Implementa NotificadorPort con un POST firmado."""

    def __init__(
        self,
        configuracion: ConfiguracionWebhook,
        datos: DatosDeLaPersona,
        evidencias: LectorEvidencias,
    ) -> None:
        self._configuracion = configuracion
        self._datos = datos
        self._evidencias = evidencias
        self._abrir = _abridor_sin_redirecciones(configuracion.contexto_tls).open

    def enviar(self, aviso: Aviso) -> None:
        cuerpo = self._cuerpo(aviso)
        firma = hmac.new(self._configuracion.secreto, cuerpo, hashlib.sha256).hexdigest()
        pedido = urllib.request.Request(  # noqa: S310 - el esquema se valida al construir
            self._configuracion.url,
            data=cuerpo,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Idempotency-Key": f"epp-aviso-{aviso.id_aviso}",
                "X-EPP-Firma": f"sha256={firma}",
            },
        )
        try:
            with self._abrir(pedido, timeout=self._configuracion.timeout.total_seconds()):
                return
        except urllib.error.HTTPError as error:
            raise NotificacionFallidaError(f"El webhook respondió {error.code}") from error
        except OSError as error:
            raise NotificacionFallidaError(f"No se pudo contactar el webhook: {error}") from error

    def _cuerpo(self, aviso: Aviso) -> bytes:
        mensaje = redactar(aviso, self._datos)
        imagen = self._evidencias.leer(aviso.evidencia)
        contenido = {
            "aviso": aviso.id_aviso,
            "persona": describir_persona(aviso.persona, self._datos),
            "elemento": aviso.elemento,
            "zona": aviso.zona,
            "desde": aviso.inicio.isoformat(),
            "asunto": mensaje.asunto,
            "texto": mensaje.cuerpo,
            "imagen_jpeg_base64": None if imagen is None else base64.b64encode(imagen).decode(),
        }
        return json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode()


def _abridor_sin_redirecciones(contexto_tls: ssl.SSLContext) -> urllib.request.OpenerDirector:
    """Como build_opener, pero sin manejador de redirecciones: un 3xx queda como HTTPError y el
    aviso nunca se reenvía a otro destino."""
    abridor = urllib.request.OpenerDirector()
    for manejador in (
        urllib.request.ProxyHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(context=contexto_tls),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        abridor.add_handler(manejador)
    return abridor
