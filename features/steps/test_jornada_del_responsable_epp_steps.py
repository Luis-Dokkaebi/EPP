"""Pasos de features/jornada_del_responsable_epp.feature: traducen el texto y usan la simulación."""

import json
from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.ppe.domain.elementos import ElementoEPP
from tests.servidores_falsos import ServidorWebhookFalso
from tests.simulacion_jornada_epp import (
    FUERA_DE_TODA_ZONA,
    POLIGONO_BOCA_DE_POZO,
    SucursalSimulada,
    operario,
)

pytestmark = pytest.mark.bdd

scenarios("../jornada_del_responsable_epp.feature")

DURACIONES = {
    "el tiempo de confirmación": timedelta(seconds=4),
    "diez minutos": timedelta(minutes=10),
}
TEXTO_DEL_AVISO = {"enviado": "Aviso enviado", "pendiente": "Aviso pendiente"}


@pytest.fixture
def sucursal(tmp_path: Path) -> SucursalSimulada:
    return SucursalSimulada(tmp_path)


@pytest.fixture
def webhook(monkeypatch: pytest.MonkeyPatch) -> Iterator[ServidorWebhookFalso]:
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    with ServidorWebhookFalso() as servidor:
        yield servidor


@given(parsers.parse('una zona "{zona}" configurada que exige {elemento}'))
def zona_configurada(sucursal: SucursalSimulada, zona: str, elemento: str) -> None:
    sucursal.dibujar_zona(zona, POLIGONO_BOCA_DE_POZO)
    sucursal.exigir(zona, ElementoEPP(elemento))
    sucursal.conectar_camara()


@given("un aviso por webhook configurado para la sucursal")
def aviso_configurado(webhook: ServidorWebhookFalso) -> None:
    """El webhook falso ya escucha en la propia máquina."""


@given(parsers.parse('que "{nombre}" trabaja sin casco en "{zona}" durante {duracion}'))
def trabaja_en_la_zona(sucursal: SucursalSimulada, nombre: str, zona: str, duracion: str) -> None:
    del zona  # El operario se ubica dentro del único polígono configurado.
    sucursal.filmar([operario(nombre, ElementoEPP.CHALECO)], DURACIONES[duracion])


@given(parsers.parse('que "{nombre}" trabaja sin casco fuera de toda zona durante {duracion}'))
def trabaja_fuera(sucursal: SucursalSimulada, nombre: str, duracion: str) -> None:
    sucursal.filmar([operario(nombre, x=FUERA_DE_TODA_ZONA)], DURACIONES[duracion])


@given("el canal de aviso está caído")
def canal_caido(webhook: ServidorWebhookFalso) -> None:
    webhook.estado = HTTPStatus.SERVICE_UNAVAILABLE


@when("la sucursal despacha los avisos pendientes")
def despachar(sucursal: SucursalSimulada, webhook: ServidorWebhookFalso) -> None:
    sucursal.abrir_con_webhook(webhook.url)


@then(
    parsers.parse(
        'el responsable recibió un aviso por "{nombre}" sin {elemento} con la imagen del evento'
    )
)
def aviso_recibido(webhook: ServidorWebhookFalso, nombre: str, elemento: str) -> None:
    (pedido,) = webhook.aceptados
    cuerpo = json.loads(pedido.cuerpo)
    assert (cuerpo["persona"], cuerpo["elemento"]) == (nombre, elemento)
    assert cuerpo["imagen_jpeg_base64"]


@then("el responsable no recibió ningún aviso")
def sin_avisos(webhook: ServidorWebhookFalso) -> None:
    assert webhook.aceptados == []


@then(
    parsers.parse('el panel de alertas muestra a "{nombre}" sin {elemento} con el aviso {estado}')
)
def panel_muestra(sucursal: SucursalSimulada, nombre: str, elemento: str, estado: str) -> None:
    (alerta,) = sucursal.alertas()
    assert (alerta.persona, alerta.elemento, alerta.aviso) == (
        nombre,
        elemento,
        TEXTO_DEL_AVISO[estado],
    )


@then("el panel de alertas está vacío")
def panel_vacio(sucursal: SucursalSimulada) -> None:
    assert sucursal.alertas() == []
