"""Canal de aviso por webhook contra un servidor local falso (SPEC/9 §7.1 a §7.5; D1).

Sin red real: el servidor escucha en 127.0.0.1 dentro de la prueba. El cuerpo va firmado con
HMAC-SHA256 y lleva la clave de idempotencia del aviso; el canal no sigue redirecciones y exige
https salvo hacia la propia máquina.
"""

import base64
import hashlib
import hmac
import json
import ssl
from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path

import pytest

from src.alerts.canal_webhook import CanalWebhook, ConfiguracionWebhook
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import NotificacionFallidaError
from src.alerts.domain.mensaje import DatosDeLaPersona
from src.alerts.evidencias import LectorEvidencias
from tests.dobles_alertas import aviso
from tests.servidores_falsos import (
    ServidorWebhookFalso,
    puerto_cerrado,
)

SECRETO = b"secreto-de-prueba"
JPEG = b"\xff\xd8\xff\xe0 imagen \xff\xd9"
UN_SEGUNDO = timedelta(seconds=1)


@pytest.fixture(autouse=True)
def sin_proxy_hacia_la_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    """El tráfico a 127.0.0.1 nunca pasa por un proxy del entorno."""
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    carpeta = tmp_path / "snapshots"
    (carpeta / "epp").mkdir(parents=True)
    (carpeta / "epp" / "7.jpg").write_bytes(JPEG)
    return carpeta


@pytest.fixture
def servidor() -> Iterator[ServidorWebhookFalso]:
    with ServidorWebhookFalso() as servidor:
        yield servidor


def _configuracion(
    url: str, tls: ssl.SSLContext | None = None, timeout: timedelta = UN_SEGUNDO
) -> ConfiguracionWebhook:
    contexto = ssl.create_default_context() if tls is None else tls
    return ConfiguracionWebhook(url=url, secreto=SECRETO, timeout=timeout, contexto_tls=contexto)


def _canal(
    carpeta: Path, configuracion: ConfiguracionWebhook, datos: DatosDeLaPersona
) -> CanalWebhook:
    return CanalWebhook(configuracion, datos, LectorEvidencias(carpeta))


def _con_nombre(carpeta: Path, url: str) -> CanalWebhook:
    return _canal(carpeta, _configuracion(url), DatosDeLaPersona.NOMBRE)


def _aviso_con_imagen(carpeta: Path) -> Aviso:
    return aviso(7, persona="Ana")._replace(evidencia=str(carpeta / "epp" / "7.jpg"))


def test_webhook_entrega_el_aviso_con_sus_datos_y_la_imagen(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    canal = _con_nombre(carpeta, servidor.url)

    canal.enviar(_aviso_con_imagen(carpeta))

    (pedido,) = servidor.recibidos
    assert pedido.ruta == "/avisos"
    assert json.loads(pedido.cuerpo) == {
        "aviso": 7,
        "persona": "Ana",
        "elemento": "casco",
        "zona": "Boca de pozo",
        "desde": "2026-10-22T08:00:00+00:00",
        "asunto": "EPP: Ana sin casco en Boca de pozo",
        "texto": (
            "Persona: Ana\nElemento faltante: casco\nZona: Boca de pozo\n"
            "Desde: 2026-10-22T08:00:00+00:00\nAviso N.º 7"
        ),
        "imagen_jpeg_base64": base64.b64encode(JPEG).decode(),
    }


def test_webhook_firma_el_cuerpo_y_envia_la_clave_de_idempotencia(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    canal = _con_nombre(carpeta, servidor.url)

    canal.enviar(_aviso_con_imagen(carpeta))

    (pedido,) = servidor.recibidos
    firma = hmac.new(SECRETO, pedido.cuerpo, hashlib.sha256).hexdigest()
    assert pedido.encabezados["Content-Type"] == "application/json; charset=utf-8"
    assert pedido.encabezados["Idempotency-Key"] == "epp-aviso-7"
    assert pedido.encabezados["X-EPP-Firma"] == f"sha256={firma}"


def test_webhook_el_cuerpo_es_json_canonico_en_utf8(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    canal = _con_nombre(carpeta, servidor.url)

    canal.enviar(aviso(7)._replace(zona="Pozo Ñandú"))

    cuerpo = servidor.recibidos[0].cuerpo
    canonico = json.dumps(json.loads(cuerpo), ensure_ascii=False, sort_keys=True).encode()
    assert cuerpo == canonico
    assert "Pozo Ñandú".encode() in cuerpo


def test_webhook_reintentar_un_aviso_repite_el_mismo_pedido(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    canal = _con_nombre(carpeta, servidor.url)

    canal.enviar(_aviso_con_imagen(carpeta))
    canal.enviar(_aviso_con_imagen(carpeta)._replace(intentos=1))

    primero, segundo = servidor.recibidos
    assert segundo.cuerpo == primero.cuerpo
    assert segundo.encabezados["Idempotency-Key"] == primero.encabezados["Idempotency-Key"]


def test_webhook_sin_imagen_disponible_avisa_igual(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    canal = _con_nombre(carpeta, servidor.url)

    canal.enviar(aviso(7)._replace(evidencia=None))

    assert json.loads(servidor.recibidos[0].cuerpo)["imagen_jpeg_base64"] is None


def test_webhook_anonimo_no_envia_el_nombre(carpeta: Path, servidor: ServidorWebhookFalso) -> None:
    canal = _canal(carpeta, _configuracion(servidor.url), DatosDeLaPersona.ANONIMO)

    canal.enviar(_aviso_con_imagen(carpeta))

    cuerpo = servidor.recibidos[0].cuerpo.decode()
    assert "Ana" not in cuerpo
    assert json.loads(cuerpo)["persona"] == "persona identificada (nombre omitido)"


@pytest.mark.parametrize(
    "estado",
    [HTTPStatus.UNAUTHORIZED, HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.SERVICE_UNAVAILABLE],
    ids=["token-invalido", "error-interno", "no-disponible"],
)
def test_webhook_una_respuesta_de_error_es_una_falla_de_entrega(
    carpeta: Path, servidor: ServidorWebhookFalso, estado: HTTPStatus
) -> None:
    servidor.estado = estado
    canal = _con_nombre(carpeta, servidor.url)

    with pytest.raises(NotificacionFallidaError, match=rf"^El webhook respondió {estado.value}$"):
        canal.enviar(aviso(7))


def test_webhook_no_sigue_redirecciones(carpeta: Path, servidor: ServidorWebhookFalso) -> None:
    servidor.estado = HTTPStatus.FOUND
    canal = _con_nombre(carpeta, servidor.url)

    with pytest.raises(NotificacionFallidaError, match=r"^El webhook respondió 302$"):
        canal.enviar(aviso(7))

    assert len(servidor.recibidos) == 1


def test_webhook_caido_es_una_falla_de_entrega(carpeta: Path) -> None:
    canal = _con_nombre(carpeta, f"http://127.0.0.1:{puerto_cerrado()}/avisos")

    with pytest.raises(NotificacionFallidaError, match=r"^No se pudo contactar el webhook: "):
        canal.enviar(aviso(7))


def test_webhook_lento_corta_por_tiempo_y_es_una_falla_de_entrega(
    carpeta: Path, servidor: ServidorWebhookFalso
) -> None:
    servidor.retener.clear()
    configuracion = _configuracion(servidor.url, timeout=timedelta(milliseconds=50))
    canal = _canal(carpeta, configuracion, DatosDeLaPersona.NOMBRE)

    with pytest.raises(NotificacionFallidaError, match=r"^No se pudo contactar el webhook: "):
        canal.enviar(aviso(7))
