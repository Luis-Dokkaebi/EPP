"""Configuración de los canales de aviso desde variables de entorno (SPEC/9 §7.3; D1, D5).

Los secretos llegan por variables de entorno, nunca por archivos del repositorio, y los mensajes
de error nunca los repiten. Lo que decide el negocio (si el aviso nombra al empleado, D5) no
tiene valor por omisión.
"""

import ssl
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

import pytest

from src.alerts.canal_email import ConfiguracionEmail, Credenciales
from src.alerts.canal_webhook import ConfiguracionWebhook
from src.alerts.configuracion import (
    canales_desde_entorno,
    configuracion_email,
    configuracion_webhook,
    datos_de_la_persona,
)
from src.alerts.domain.errores import ConfiguracionAlertasError, NotificacionFallidaError
from src.alerts.domain.mensaje import DatosDeLaPersona
from src.alerts.evidencias import LectorEvidencias
from tests.dobles_alertas import aviso
from tests.servidores_falsos import puerto_cerrado as _puerto_cerrado

TLS = ssl.create_default_context()
WEBHOOK = {
    "EPP_ALERTAS_WEBHOOK_URL": "https://avisos.example.com/epp",
    # Valores ficticios de prueba, no credenciales reales.
    "EPP_ALERTAS_WEBHOOK_SECRETO": "secreto-webhook",  # pragma: allowlist secret
    "EPP_ALERTAS_WEBHOOK_TIMEOUT_S": "2.5",
}
EMAIL = {
    "EPP_ALERTAS_SMTP_SERVIDOR": "smtp.empresa.example",
    "EPP_ALERTAS_SMTP_PUERTO": "587",
    "EPP_ALERTAS_SMTP_REMITENTE": "epp@empresa.example",
    "EPP_ALERTAS_SMTP_DESTINATARIOS": " seguridad@empresa.example, ,jefe@empresa.example ",
    "EPP_ALERTAS_SMTP_TIMEOUT_S": "10",
    "EPP_ALERTAS_SMTP_USUARIO": "avisos",
    "EPP_ALERTAS_SMTP_CONTRASENA": "clave-smtp",  # pragma: allowlist secret
}
CREDENCIALES_SMTP = {"EPP_ALERTAS_SMTP_USUARIO", "EPP_ALERTAS_SMTP_CONTRASENA"}
EMAIL_SIN_CREDENCIALES = {
    clave: valor for clave, valor in EMAIL.items() if clave not in CREDENCIALES_SMTP
}
CON_NOMBRE = {"EPP_ALERTAS_NOMBRE_EMPLEADO": "incluir"}
LeerCanal = Callable[[Mapping[str, str], ssl.SSLContext], object]


@pytest.mark.parametrize(
    ("valor", "datos"),
    [("incluir", DatosDeLaPersona.NOMBRE), ("omitir", DatosDeLaPersona.ANONIMO)],
)
def test_datos_de_la_persona_se_leen_del_entorno(valor: str, datos: DatosDeLaPersona) -> None:
    assert datos_de_la_persona({"EPP_ALERTAS_NOMBRE_EMPLEADO": valor}) is datos


@pytest.mark.parametrize(
    "entorno", [{}, {"EPP_ALERTAS_NOMBRE_EMPLEADO": " "}], ids=["falta", "vacia"]
)
def test_sin_configurar_el_aviso_nombra_al_empleado_como_decidio_el_negocio(
    entorno: dict[str, str],
) -> None:
    # D5 (24/10/2026): el aviso nombra al empleado reconocido; "omitir" sigue disponible.
    assert datos_de_la_persona(entorno) is DatosDeLaPersona.NOMBRE


def test_datos_de_la_persona_con_un_valor_desconocido_falla() -> None:
    with pytest.raises(
        ConfiguracionAlertasError,
        match=r"^EPP_ALERTAS_NOMBRE_EMPLEADO debe ser 'incluir' u 'omitir': quizas$",
    ):
        datos_de_la_persona({"EPP_ALERTAS_NOMBRE_EMPLEADO": "quizas"})


def test_configuracion_webhook_completa() -> None:
    configuracion = configuracion_webhook(WEBHOOK, TLS)

    assert configuracion == ConfiguracionWebhook(
        url="https://avisos.example.com/epp",
        secreto=b"secreto-webhook",
        timeout=timedelta(seconds=2.5),
        contexto_tls=TLS,
    )


def test_configuracion_webhook_sin_url_no_activa_el_canal() -> None:
    assert configuracion_webhook({"EPP_ALERTAS_WEBHOOK_SECRETO": "x"}, TLS) is None


def test_configuracion_email_completa_sin_destinatarios_vacios() -> None:
    configuracion = configuracion_email(EMAIL, TLS)

    assert configuracion == ConfiguracionEmail(
        servidor="smtp.empresa.example",
        puerto=587,
        remitente="epp@empresa.example",
        destinatarios=("seguridad@empresa.example", "jefe@empresa.example"),
        credenciales=Credenciales("avisos", "clave-smtp"),
        timeout=timedelta(seconds=10),
        contexto_tls=TLS,
    )


def test_configuracion_email_sin_usuario_ni_contrasena_no_se_autentica() -> None:
    configuracion = configuracion_email(EMAIL_SIN_CREDENCIALES, TLS)

    assert configuracion is not None
    assert configuracion.credenciales is None


def test_configuracion_email_sin_servidor_no_activa_el_canal() -> None:
    assert configuracion_email({"EPP_ALERTAS_SMTP_PUERTO": "587"}, TLS) is None


@pytest.mark.parametrize(
    "falta",
    ["EPP_ALERTAS_SMTP_USUARIO", "EPP_ALERTAS_SMTP_CONTRASENA"],
    ids=["sin-usuario", "sin-contrasena"],
)
def test_configuracion_email_usuario_y_contrasena_van_juntos(falta: str) -> None:
    entorno = {**EMAIL, falta: ""}

    with pytest.raises(
        ConfiguracionAlertasError,
        match=r"^EPP_ALERTAS_SMTP_USUARIO y EPP_ALERTAS_SMTP_CONTRASENA van juntas$",
    ):
        configuracion_email(entorno, TLS)


@pytest.mark.parametrize(
    ("leer", "variables", "falta"),
    [
        (configuracion_webhook, WEBHOOK, "EPP_ALERTAS_WEBHOOK_SECRETO"),
        (configuracion_webhook, WEBHOOK, "EPP_ALERTAS_WEBHOOK_TIMEOUT_S"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_PUERTO"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_REMITENTE"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_DESTINATARIOS"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_TIMEOUT_S"),
    ],
)
def test_configuracion_de_un_canal_activo_exige_todas_sus_variables(
    leer: LeerCanal, variables: dict[str, str], falta: str
) -> None:
    entorno = {**variables, falta: ""}

    with pytest.raises(ConfiguracionAlertasError, match=rf"^Falta la variable de entorno {falta}$"):
        leer(entorno, TLS)


@pytest.mark.parametrize(
    ("leer", "variables", "nombre", "valor"),
    [
        (configuracion_webhook, WEBHOOK, "EPP_ALERTAS_WEBHOOK_TIMEOUT_S", "rapido"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_PUERTO", "587.5"),
        (configuracion_email, EMAIL, "EPP_ALERTAS_SMTP_TIMEOUT_S", "diez"),
    ],
)
def test_configuracion_con_un_numero_invalido_falla_nombrando_la_variable(
    leer: LeerCanal, variables: dict[str, str], nombre: str, valor: str
) -> None:
    entorno = {**variables, nombre: valor}

    with pytest.raises(ConfiguracionAlertasError, match=rf"^{nombre} debe ser un número: {valor}$"):
        leer(entorno, TLS)


@pytest.mark.parametrize(
    ("entorno", "nombres"),
    [
        ({**CON_NOMBRE, **WEBHOOK}, ("webhook",)),
        ({**CON_NOMBRE, **EMAIL}, ("email",)),
        ({**CON_NOMBRE, **EMAIL, **WEBHOOK}, ("email", "webhook")),
    ],
    ids=["solo-webhook", "solo-email", "ambos"],
)
def test_canales_desde_entorno_activa_los_canales_configurados(
    tmp_path: Path, entorno: dict[str, str], nombres: tuple[str, ...]
) -> None:
    canales = canales_desde_entorno(entorno, LectorEvidencias(tmp_path), TLS)

    assert canales.nombres == nombres


def test_canales_desde_entorno_arma_canales_reales_que_avisan_por_la_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    puerto = _puerto_cerrado()
    entorno = {
        **CON_NOMBRE,
        **EMAIL,
        **WEBHOOK,
        "EPP_ALERTAS_SMTP_SERVIDOR": "127.0.0.1",
        "EPP_ALERTAS_SMTP_PUERTO": str(puerto),
        "EPP_ALERTAS_WEBHOOK_URL": f"http://127.0.0.1:{puerto}/avisos",
    }
    canales = canales_desde_entorno(entorno, LectorEvidencias(tmp_path), TLS)

    with pytest.raises(
        NotificacionFallidaError,
        match=r"^email: No se pudo enviar el correo: .*; "
        r"webhook: No se pudo contactar el webhook: ",
    ):
        canales.enviar(aviso(7))


def test_canales_desde_entorno_sin_ningun_canal_falla(tmp_path: Path) -> None:
    with pytest.raises(ConfiguracionAlertasError, match=r"^No hay ningún canal de aviso"):
        canales_desde_entorno(CON_NOMBRE, LectorEvidencias(tmp_path), TLS)


def test_canales_desde_entorno_sin_la_variable_del_nombre_arma_el_canal(tmp_path: Path) -> None:
    canales = canales_desde_entorno(WEBHOOK, LectorEvidencias(tmp_path), TLS)

    assert canales.nombres == ("webhook",)


def test_los_errores_de_configuracion_no_repiten_los_secretos() -> None:
    entorno = {**WEBHOOK, "EPP_ALERTAS_WEBHOOK_URL": "http://remoto.example/x?t=secreto-webhook"}

    with pytest.raises(ConfiguracionAlertasError) as error:
        canales_desde_entorno({**CON_NOMBRE, **entorno}, LectorEvidencias(Path()), TLS)

    assert "secreto-webhook" not in str(error.value)
