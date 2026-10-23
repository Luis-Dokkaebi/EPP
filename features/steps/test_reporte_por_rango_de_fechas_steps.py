"""Pasos de features/reporte_por_rango_de_fechas.feature: traducen el texto al presentador."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.gui.selector_fecha import consultar_reporte

pytestmark = pytest.mark.bdd

scenarios("../reporte_por_rango_de_fechas.feature")


@dataclass
class Reporte:
    desde: str = ""
    hasta: str = ""
    consultas: list[tuple[str, str]] = field(default_factory=list)
    aviso: str = ""

    def consultar(self, desde: str, hasta: str, _empleado: str) -> Sequence[Any]:
        self.consultas.append((desde, hasta))
        return []


@given(
    parsers.parse('el rango de fechas desde "{desde}" hasta "{hasta}"'), target_fixture="reporte"
)
def rango(desde: str, hasta: str) -> Reporte:
    return Reporte(desde=desde, hasta=hasta)


@when("genero el reporte de asistencia")
def generar(reporte: Reporte) -> None:
    try:
        consultar_reporte(reporte.desde, reporte.hasta, "", reporte.consultar)
    except ValueError as error:
        reporte.aviso = str(error)


@then(parsers.parse('el reporte cubre del "{desde}" al "{hasta}"'))
def cubre(reporte: Reporte, desde: str, hasta: str) -> None:
    assert reporte.consultas == [(desde, hasta)]


@then(parsers.parse('se me avisa "{aviso}"'))
def avisa(reporte: Reporte, aviso: str) -> None:
    assert reporte.aviso == aviso


@then("no se consulta ningún dato")
def sin_consulta(reporte: Reporte) -> None:
    assert reporte.consultas == []
