"""Pasos de features/modo_sombra_epp.feature: traducen el texto y llaman a la simulación."""

from datetime import timedelta
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.simulacion_modo_sombra import FIN_DEL_MODO_SOMBRA, UNA_HORA, SucursalEnSombra

pytestmark = pytest.mark.bdd

scenarios("../modo_sombra_epp.feature")

MOMENTOS = {
    "pendiente de aviso": -UNA_HORA,
    "registrada durante el modo sombra": -UNA_HORA,
    "registrada después del modo sombra": UNA_HORA,
    "registrada al salir del modo sombra": timedelta(0),
}
SALIDA = {"EPP_FIN_MODO_SOMBRA": FIN_DEL_MODO_SOMBRA.isoformat()}
SALIDA_SIN_HUSO = {"EPP_FIN_MODO_SOMBRA": FIN_DEL_MODO_SOMBRA.replace(tzinfo=None).isoformat()}


@pytest.fixture
def sucursal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SucursalEnSombra:
    return SucursalEnSombra(tmp_path, monkeypatch)


@given("un canal de aviso configurado para la sucursal")
def canal_configurado(sucursal: SucursalEnSombra) -> None:
    """El canal en memoria de la simulación ya está conectado."""


@given(parsers.parse('una infracción de "{nombre}" sin {elemento} {momento}'))
def infraccion(sucursal: SucursalEnSombra, nombre: str, elemento: str, momento: str) -> None:
    sucursal.registrar(nombre, elemento, MOMENTOS[momento])


@when("abro la sucursal en modo sombra")
def abrir_en_sombra(sucursal: SucursalEnSombra) -> None:
    sucursal.abrir({"EPP_MODO_SOMBRA": "1"})


@when("abro la sucursal tras salir del modo sombra")
def abrir_tras_la_sombra(sucursal: SucursalEnSombra) -> None:
    sucursal.abrir(SALIDA)


@when("abro la sucursal con una fecha de salida del modo sombra sin huso horario")
def abrir_con_fecha_invalida(sucursal: SucursalEnSombra) -> None:
    sucursal.abrir(SALIDA_SIN_HUSO)


@then("el responsable no recibió ningún aviso")
def sin_avisos(sucursal: SucursalEnSombra) -> None:
    assert sucursal.canal.avisados == []


@then(parsers.parse('el responsable recibió avisos solo por "{nombre}"'))
def avisos_solo_por(sucursal: SucursalEnSombra, nombre: str) -> None:
    assert sucursal.canal.avisados == [nombre]


@then(parsers.parse('la infracción de "{nombre}" sigue pendiente de aviso'))
def sigue_pendiente(sucursal: SucursalEnSombra, nombre: str) -> None:
    assert sucursal.estado_de(nombre) == "PENDIENTE"


@then(parsers.parse('la infracción de "{nombre}" figura como descartada'))
def descartada(sucursal: SucursalEnSombra, nombre: str) -> None:
    assert sucursal.estado_de(nombre) == "DESCARTADA"


@then("la apertura se rechaza por la fecha de salida del modo sombra")
def apertura_rechazada(sucursal: SucursalEnSombra) -> None:
    assert "EPP_FIN_MODO_SOMBRA debe llevar huso horario" in str(sucursal.error)
