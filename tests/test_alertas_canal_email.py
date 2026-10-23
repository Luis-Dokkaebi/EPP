"""Canal de aviso por email contra un SMTP local falso (SPEC/9 §7.2, §7.3, §7.5; D1).

Sin red real. El canal exige STARTTLS siempre: si el servidor no lo ofrece o su certificado no
es confiable, no envía nada en claro y la entrega falla (el despachador la reintenta).
"""

import email
import email.policy
import ssl
from collections.abc import Iterator
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path

import pytest

from src.alerts.canal_email import CanalEmail, ConfiguracionEmail, Credenciales
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import ConfiguracionAlertasError, NotificacionFallidaError
from src.alerts.domain.mensaje import DatosDeLaPersona
from src.alerts.evidencias import LectorEvidencias
from tests.dobles_alertas import aviso
from tests.servidores_falsos import (
    CertificadoLocal,
    CorreoRecibido,
    ServidorSMTPFalso,
    certificado_autofirmado,
    contexto_cliente,
    contexto_servidor,
)

JPEG = b"\xff\xd8\xff\xe0 imagen \xff\xd9"
CREDENCIALES = Credenciales(usuario="avisos", contrasena="clave-de-prueba")
FALLA = r"^No se pudo enviar el correo: "


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    carpeta = tmp_path / "snapshots"
    (carpeta / "epp").mkdir(parents=True)
    (carpeta / "epp" / "7.jpg").write_bytes(JPEG)
    return carpeta


@pytest.fixture
def certificado(tmp_path: Path) -> CertificadoLocal:
    return certificado_autofirmado(tmp_path)


@pytest.fixture
def servidor(certificado: CertificadoLocal) -> Iterator[ServidorSMTPFalso]:
    with ServidorSMTPFalso(contexto_servidor(certificado)) as servidor:
        yield servidor


def _configuracion(puerto: int, tls: ssl.SSLContext) -> ConfiguracionEmail:
    return ConfiguracionEmail(
        servidor="127.0.0.1",
        puerto=puerto,
        remitente="epp@empresa.example",
        destinatarios=("seguridad@empresa.example", "jefe@empresa.example"),
        credenciales=CREDENCIALES,
        timeout=timedelta(seconds=2),
        contexto_tls=tls,
    )


def _canal(
    carpeta: Path,
    configuracion: ConfiguracionEmail,
    datos: DatosDeLaPersona = DatosDeLaPersona.NOMBRE,
) -> CanalEmail:
    return CanalEmail(configuracion, datos, LectorEvidencias(carpeta))


def _confiable(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> CanalEmail:
    return _canal(carpeta, _configuracion(servidor.puerto, contexto_cliente(certificado)))


def _aviso_con_imagen(carpeta: Path) -> Aviso:
    return aviso(7, persona="Ana")._replace(evidencia=str(carpeta / "epp" / "7.jpg"))


def _correo(recibido: CorreoRecibido) -> EmailMessage:
    correo = email.message_from_bytes(recibido.datos, policy=email.policy.default)
    assert isinstance(correo, EmailMessage)
    return correo


def test_email_entrega_el_aviso_por_tls_con_la_imagen_adjunta(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    canal = _confiable(carpeta, servidor, certificado)

    canal.enviar(_aviso_con_imagen(carpeta))

    (recibido,) = servidor.recibidos
    correo = _correo(recibido)
    (adjunto,) = correo.iter_attachments()
    assert recibido.con_tls is True
    assert recibido.credenciales == ("avisos", "clave-de-prueba")
    assert recibido.remitente == "epp@empresa.example"
    assert recibido.destinatarios == ["seguridad@empresa.example", "jefe@empresa.example"]
    assert correo["Subject"] == "EPP: Ana sin casco en Boca de pozo"
    assert correo["To"] == "seguridad@empresa.example, jefe@empresa.example"
    assert correo.get_body().get_content().splitlines() == [
        "Persona: Ana",
        "Elemento faltante: casco",
        "Zona: Boca de pozo",
        "Desde: 2026-10-22T08:00:00+00:00",
        "Aviso N.º 7",
    ]
    assert adjunto.get_content_type() == "image/jpeg"
    assert adjunto.get_filename() == "aviso-7.jpg"
    assert adjunto.get_content() == JPEG


def test_email_un_reintento_conserva_el_mismo_identificador_de_mensaje(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    canal = _confiable(carpeta, servidor, certificado)

    canal.enviar(aviso(7))
    canal.enviar(aviso(7, intentos=1))

    identificadores = [_correo(recibido)["Message-ID"] for recibido in servidor.recibidos]
    assert identificadores == ["<epp-aviso-7@empresa.example>"] * 2


def test_email_sin_imagen_disponible_avisa_sin_adjunto(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    canal = _confiable(carpeta, servidor, certificado)

    canal.enviar(aviso(7)._replace(evidencia=None))

    assert list(_correo(servidor.recibidos[0]).iter_attachments()) == []


def test_email_sin_credenciales_no_se_autentica(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    configuracion = _configuracion(servidor.puerto, contexto_cliente(certificado))
    canal = _canal(carpeta, configuracion._replace(credenciales=None))

    canal.enviar(aviso(7))

    assert servidor.recibidos[0].credenciales is None


def test_email_anonimo_no_incluye_el_nombre(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    configuracion = _configuracion(servidor.puerto, contexto_cliente(certificado))
    canal = _canal(carpeta, configuracion, DatosDeLaPersona.ANONIMO)

    canal.enviar(_aviso_con_imagen(carpeta))

    assert b"Ana" not in servidor.recibidos[0].datos


def test_email_nunca_envia_en_claro_si_el_servidor_no_ofrece_tls(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    servidor.ofrece_starttls = False
    canal = _confiable(carpeta, servidor, certificado)

    with pytest.raises(NotificacionFallidaError, match=FALLA):
        canal.enviar(aviso(7))

    assert servidor.recibidos == []


def test_email_con_un_certificado_no_confiable_no_envia(
    carpeta: Path, servidor: ServidorSMTPFalso
) -> None:
    canal = _canal(carpeta, _configuracion(servidor.puerto, ssl.create_default_context()))

    with pytest.raises(NotificacionFallidaError, match=FALLA):
        canal.enviar(aviso(7))

    assert servidor.recibidos == []


def test_email_rechazado_por_el_servidor_es_una_falla_de_entrega(
    carpeta: Path, servidor: ServidorSMTPFalso, certificado: CertificadoLocal
) -> None:
    servidor.rechazo = "451 intente luego"
    canal = _confiable(carpeta, servidor, certificado)

    with pytest.raises(NotificacionFallidaError, match=FALLA + r".*intente luego"):
        canal.enviar(aviso(7))


def test_email_con_el_servidor_caido_es_una_falla_de_entrega(
    carpeta: Path, certificado: CertificadoLocal
) -> None:
    with ServidorSMTPFalso(contexto_servidor(certificado)) as apagado:
        puerto = apagado.puerto
    canal = _canal(carpeta, _configuracion(puerto, contexto_cliente(certificado)))

    with pytest.raises(NotificacionFallidaError, match=FALLA):
        canal.enviar(aviso(7))


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"destinatarios": ()}, r"^El email necesita al menos un destinatario$"),
        ({"puerto": 0}, r"^puerto debe estar entre 1 y 65535: 0$"),
        ({"puerto": 65536}, r"^puerto debe estar entre 1 y 65535: 65536$"),
        ({"timeout": timedelta(0)}, r"^timeout debe ser positivo: 0:00:00$"),
    ],
    ids=["sin-destinatarios", "puerto-cero", "puerto-alto", "timeout-cero"],
)
def test_email_rechaza_configuracion_invalida(
    carpeta: Path, cambios: dict[str, object], mensaje: str
) -> None:
    configuracion = _configuracion(25, ssl.create_default_context())._replace(**cambios)

    with pytest.raises(ConfiguracionAlertasError, match=mensaje):
        _canal(carpeta, configuracion)


@pytest.mark.parametrize("puerto", [1, 65535], ids=["minimo", "maximo"])
def test_email_acepta_los_puertos_limite(carpeta: Path, puerto: int) -> None:
    configuracion = _configuracion(puerto, ssl.create_default_context())

    assert isinstance(_canal(carpeta, configuracion), CanalEmail)
