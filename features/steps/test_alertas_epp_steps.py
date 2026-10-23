"""Pasos de features/alertas_epp.feature: solo traducen el texto y llaman a la simulación."""

import base64
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.simulacion_alertas_epp import SimulacionAlertas
from tests.simulacion_cumplimiento_ppe import elementos_de

pytestmark = pytest.mark.bdd

scenarios("../alertas_epp.feature")


@pytest.fixture
def alertas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimulacionAlertas]:
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with SimulacionAlertas(tmp_path) as simulacion:
        yield simulacion


@given(parsers.parse('una zona "{zona}" que exige {elementos}'))
def zona_que_exige(alertas: SimulacionAlertas, zona: str, elementos: str) -> None:
    alertas.cumplimiento.agregar_zona(zona, elementos_de(elementos))


@given(
    parsers.parse(
        'un operario identificado como "{nombre}" sin {elemento} en "{zona}" '
        "desde hace {minutos:d} minutos"
    )
)
def operario_identificado_sin(
    alertas: SimulacionAlertas, nombre: str, elemento: str, zona: str, minutos: int
) -> None:
    alertas.operario_sin(elemento, zona, nombre)
    alertas.transcurrir_despachando(timedelta(minutes=minutos))


@given(parsers.parse('un operario no identificado sin {elemento} en "{zona}"'))
def operario_no_identificado_sin(alertas: SimulacionAlertas, elemento: str, zona: str) -> None:
    alertas.operario_sin(elemento, zona, None)
    alertas.confirmar_la_infraccion()


@given("una infracción registrada y el canal de aviso caído")
def infraccion_con_el_canal_caido(alertas: SimulacionAlertas) -> None:
    alertas.operario_sin("casco", "Boca de pozo", "Ana")
    alertas.confirmar_la_infraccion()
    alertas.caer_el_canal()
    alertas.despachar()


@when("se evalúan las alertas pendientes")
def se_evaluan_las_alertas(alertas: SimulacionAlertas) -> None:
    alertas.despachar()


@when("el canal de aviso se restablece")
def el_canal_se_restablece(alertas: SimulacionAlertas) -> None:
    alertas.restablecer_el_canal()


@when("se genera la alerta")
def se_genera_la_alerta(alertas: SimulacionAlertas) -> None:
    alertas.despachar()


@then(parsers.parse('el responsable recibió exactamente una alerta por "{nombre}" sin {elemento}'))
def una_sola_alerta(alertas: SimulacionAlertas, nombre: str, elemento: str) -> None:
    recibidas = [(alerta["persona"], alerta["elemento"]) for alerta in alertas.recibidas]

    assert recibidas == [(nombre, elemento)]


@then("el responsable recibe la alerta pendiente")
def recibe_la_pendiente(alertas: SimulacionAlertas) -> None:
    assert [alerta["aviso"] for alerta in alertas.recibidas] == alertas.infracciones()


@then("la infracción figura como notificada")
def figura_como_notificada(alertas: SimulacionAlertas) -> None:
    assert alertas.estados_de_notificacion() == ["ENVIADA"]


@then(parsers.parse('la alerta indica "{persona}" y adjunta la imagen'))
def alerta_con_persona_e_imagen(alertas: SimulacionAlertas, persona: str) -> None:
    (alerta,) = alertas.recibidas

    assert alerta["persona"] == persona
    assert base64.b64decode(alerta["imagen_jpeg_base64"]) == alertas.imagen_de_la_infraccion()
