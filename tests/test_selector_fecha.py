"""Selector de fecha propio que reemplaza a tkcalendar (GPLv3), SPEC/9 §1.11."""

import tkinter as tk
from collections.abc import Iterator
from datetime import date

import pytest

from src.gui.selector_fecha import (
    FechaInvalidaError,
    RangoDeFechasInvalidoError,
    SelectorDeFecha,
    consultar_reporte,
    leer_fecha,
)

FECHA_UNICODE = "\uff12\uff10\uff12\uff16-10-22"  # dígitos Unicode, no ASCII


class ConsultaFalsa:
    def __init__(self) -> None:
        self.recibidas: list[tuple[str, str, str]] = []

    def __call__(self, desde: str, hasta: str, empleado: str) -> list[tuple[str, ...]]:
        self.recibidas.append((desde, hasta, empleado))
        return [("Ana", desde)]


def test_leer_fecha_acepta_el_formato_iso() -> None:
    assert leer_fecha("2026-10-22") == date(2026, 10, 22)


@pytest.mark.parametrize(
    "texto",
    ["", "22/10/2026", "2026-13-01", "2026-02-30", "2026-2-1", " 2026-10-22", FECHA_UNICODE],
    ids=["vacio", "dia-mes-anio", "mes-13", "30-de-febrero", "sin-ceros", "espacio", "unicode"],
)
def test_leer_fecha_rechaza_lo_que_no_es_aaaa_mm_dd(texto: str) -> None:
    with pytest.raises(FechaInvalidaError) as error:
        leer_fecha(texto)

    assert str(error.value) == f"Fecha inválida: «{texto}». Usa el formato AAAA-MM-DD."


def test_consultar_reporte_pasa_las_fechas_en_formato_iso_y_devuelve_las_filas() -> None:
    consulta = ConsultaFalsa()

    filas = consultar_reporte("2026-10-01", "2026-10-22", "Ana", consulta)

    assert consulta.recibidas == [("2026-10-01", "2026-10-22", "Ana")]
    assert filas == [("Ana", "2026-10-01")]


def test_consultar_reporte_acepta_un_rango_de_un_solo_dia() -> None:
    consulta = ConsultaFalsa()

    consultar_reporte("2026-10-22", "2026-10-22", "", consulta)

    assert consulta.recibidas == [("2026-10-22", "2026-10-22", "")]


def test_consultar_reporte_con_fecha_invalida_no_consulta() -> None:
    consulta = ConsultaFalsa()

    with pytest.raises(FechaInvalidaError):
        consultar_reporte("2026-10-01", "mañana", "", consulta)

    assert consulta.recibidas == []


def test_consultar_reporte_con_desde_posterior_a_hasta_no_consulta() -> None:
    consulta = ConsultaFalsa()

    with pytest.raises(RangoDeFechasInvalidoError) as error:
        consultar_reporte("2026-10-23", "2026-10-22", "", consulta)

    assert consulta.recibidas == []
    assert str(error.value) == "La fecha «Desde» (2026-10-23) es posterior a «Hasta» (2026-10-22)."


@pytest.fixture
def raiz() -> Iterator[tk.Tk]:
    ventana = tk.Tk()
    yield ventana
    ventana.destroy()


@pytest.mark.integration
def test_selector_muestra_la_fecha_inicial_en_formato_iso(raiz: tk.Tk) -> None:
    selector = SelectorDeFecha(raiz, inicial=date(2026, 1, 5))

    assert selector.get() == "2026-01-05"


@pytest.mark.integration
def test_selector_reemplaza_el_texto_al_fijar_otra_fecha(raiz: tk.Tk) -> None:
    selector = SelectorDeFecha(raiz, inicial=date(2026, 1, 5))

    selector.set_date(date(2025, 12, 31))

    assert selector.get() == "2025-12-31"
    assert int(selector.cget("width")) == len("AAAA-MM-DD") + 2
