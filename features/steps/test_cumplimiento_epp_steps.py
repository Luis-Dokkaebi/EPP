"""Pasos de features/cumplimiento_epp.feature: solo traducen el texto y llaman a la simulación."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from tests.dobles_ppe import INICIO
from tests.escenas_ppe import TODO_EL_EPP
from tests.simulacion_cumplimiento_ppe import (
    SEGUNDO_DE_CONFIRMACION,
    TIEMPO_DE_CONFIRMACION,
    UN_SEGUNDO,
    SimulacionCumplimiento,
    elementos_de,
)

pytestmark = pytest.mark.bdd

scenarios("../cumplimiento_epp.feature")


def _todo_salvo(elemento: ElementoEPP) -> list[ElementoEPP]:
    return [otro for otro in TODO_EL_EPP if otro is not elemento]


@pytest.fixture
def simulacion() -> SimulacionCumplimiento:
    return SimulacionCumplimiento()


@given(parsers.parse('una zona "{zona}" que exige {elementos}'))
def zona_que_exige(simulacion: SimulacionCumplimiento, zona: str, elementos: str) -> None:
    simulacion.agregar_zona(zona, elementos_de(elementos))


@given(parsers.re(r'un operario en "(?P<zona>[^"]+)" con (?P<elementos>(?!todo).+)'))
def operario_con(simulacion: SimulacionCumplimiento, zona: str, elementos: str) -> None:
    simulacion.ubicar_operario({zona}, elementos_de(elementos))


@given(parsers.parse('un operario en "{zona}" con todo su EPP'))
def operario_con_todo(simulacion: SimulacionCumplimiento, zona: str) -> None:
    simulacion.ubicar_operario({zona}, TODO_EL_EPP)


@given(parsers.parse('un operario en "{zona}" sin {elemento}'))
def operario_sin(simulacion: SimulacionCumplimiento, zona: str, elemento: str) -> None:
    simulacion.ubicar_operario({zona}, _todo_salvo(ElementoEPP(elemento)))


@given(parsers.parse('un operario en "{zona}" cuya cabeza no se ve'))
def operario_sin_cabeza_visible(simulacion: SimulacionCumplimiento, zona: str) -> None:
    simulacion.ubicar_operario({zona}, TODO_EL_EPP)
    simulacion.ocultar_la_cabeza()


@given(parsers.parse('un operario en "{zona}" que lleva el casco en la mano'))
def operario_con_casco_en_la_mano(simulacion: SimulacionCumplimiento, zona: str) -> None:
    simulacion.ubicar_operario({zona}, _todo_salvo(ElementoEPP.CASCO))
    simulacion.poner_el_casco_en_la_mano()


@given("un operario sin guantes fuera de toda zona que exija guantes")
def operario_sin_guantes_fuera_de_zona(simulacion: SimulacionCumplimiento) -> None:
    simulacion.ubicar_operario(set(), _todo_salvo(ElementoEPP.GUANTES))


@given("su casco deja de verse durante menos que el tiempo de confirmación")
def casco_oculto_brevemente(simulacion: SimulacionCumplimiento) -> None:
    simulacion.ocultar_el_casco_durante(TIEMPO_DE_CONFIRMACION - UN_SEGUNDO)


@when("transcurre el tiempo de confirmación")
def transcurre_el_tiempo_de_confirmacion(simulacion: SimulacionCumplimiento) -> None:
    simulacion.transcurrir_hasta(SEGUNDO_DE_CONFIRMACION)


@when(parsers.parse('el operario entra a "{zona}"'))
def el_operario_entra(simulacion: SimulacionCumplimiento, zona: str) -> None:
    simulacion.entrar_a(zona)


@then(parsers.parse('el operario figura como "{situacion}"'))
def figura_como(simulacion: SimulacionCumplimiento, situacion: str) -> None:
    assert simulacion.situacion() == situacion


@then("no se genera ninguna alerta")
def ninguna_alerta(simulacion: SimulacionCumplimiento) -> None:
    assert simulacion.alertas == []


@then(parsers.parse('se genera una alerta por "{elemento}" faltante'))
def alerta_por(simulacion: SimulacionCumplimiento, elemento: str) -> None:
    faltantes = [alerta.incumplimiento.elemento for alerta in simulacion.alertas]

    assert faltantes == [ElementoEPP(elemento)]


@then("la alerta incluye la imagen del evento")
def alerta_con_imagen(simulacion: SimulacionCumplimiento) -> None:
    alerta = simulacion.alertas[0]

    assert simulacion.puertos.evidencias[alerta.evidencia] == simulacion.imagen_en(alerta.inicio)


@then(parsers.parse('el casco del operario figura como "{estado}"'))
def casco_figura_como(simulacion: SimulacionCumplimiento, estado: str) -> None:
    assert simulacion.estado_del(ElementoEPP.CASCO) is EstadoElemento(estado)


@then(
    parsers.parse(
        'al cumplirse el tiempo de confirmación se genera una alerta por "{elemento}" '
        'faltante en "{zona}"'
    )
)
def alerta_al_cumplirse_en_zona(
    simulacion: SimulacionCumplimiento, elemento: str, zona: str
) -> None:
    alertas = [
        (alerta.incumplimiento.elemento, alerta.incumplimiento.zona, alerta.inicio)
        for alerta in simulacion.alertas
    ]

    assert alertas == [(ElementoEPP(elemento), zona, INICIO + TIEMPO_DE_CONFIRMACION)]
