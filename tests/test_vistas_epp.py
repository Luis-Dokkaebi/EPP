"""Vistas del módulo de EPP en la navegación, con Tk real (SPEC/9 §8.2 y §8.4).

Integración: necesita una pantalla (el gate corre la suite bajo xvfb). El presentador del panel y
el generador del reporte tienen sus propias pruebas; aquí se verifica que la app los arme sobre
la base del tenant y que el reporte avise desde el hilo de la interfaz.
"""

import sqlite3
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
import pytest

from src.gui.presentador_alertas import PreferenciasPanel
from src.gui.vistas_epp import (
    PanelReporteCumplimiento,
    crear_vista_alertas,
    preferencias_del_equipo,
)
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones

pytestmark = pytest.mark.integration

HILO_DEL_REPORTE = "reporte-cumplimiento-epp"
PREFERENCIAS = PreferenciasPanel(usuario="Supervisora", zona_horaria=UTC, limite=10)
INICIO = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


@pytest.fixture
def conectar(tmp_path: Path) -> Callable[[], sqlite3.Connection]:
    ruta = tmp_path / "tenant.db"

    def abrir() -> sqlite3.Connection:
        return sqlite3.connect(ruta)

    crear_tabla_infracciones(abrir)
    incumplimiento = Incumplimiento(1, "Ana", ElementoEPP.CASCO, "Anden")
    RepositorioInfraccionesSQLite(abrir).guardar(
        InfraccionIniciada(incumplimiento, INICIO, "epp-1", evidencia=None)
    )
    return abrir


def _hijos(widget: Any) -> list[Any]:
    hijos = []
    for hijo in widget.winfo_children():
        hijos.append(hijo)
        hijos.extend(_hijos(hijo))
    return hijos


def _textos(widget: Any) -> list[str]:
    return [str(h.cget("text")) for h in _hijos(widget) if isinstance(h, ctk.CTkLabel)]


def _exportar(panel: PanelReporteCumplimiento, desde: str, hasta: str) -> None:
    panel.desde.delete(0, "end")
    panel.desde.insert(0, desde)
    panel.hasta.delete(0, "end")
    panel.hasta.insert(0, hasta)
    (boton,) = (h for h in _hijos(panel) if isinstance(h, ctk.CTkButton))
    boton.invoke()
    for hilo in threading.enumerate():
        if hilo.name == HILO_DEL_REPORTE:
            hilo.join()


def test_la_vista_de_alertas_muestra_las_infracciones_de_la_sucursal(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection]
) -> None:
    panel = crear_vista_alertas(raiz, conectar, PREFERENCIAS)
    raiz.update_idletasks()

    assert any("Ana · Anden · sin casco · Aviso pendiente" in t for t in _textos(panel))


def test_el_panel_de_reporte_arranca_con_hoy_un_boton_y_sin_mensaje(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)

    botones = [h.cget("text") for h in _hijos(panel) if isinstance(h, ctk.CTkButton)]
    assert botones == ["Exportar Excel"]
    assert _textos(panel) == [""]


def test_el_panel_de_reporte_separa_las_fechas_y_el_mensaje(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)
    (estado,) = (h for h in panel.winfo_children() if isinstance(h, ctk.CTkLabel))

    margenes = [int(w.pack_info()["padx"]) for w in (panel.desde, panel.hasta, estado)]

    assert margenes == [5, 5, 10]


def test_mientras_se_genera_el_reporte_lo_avisa(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)

    _exportar(panel, "2026-10-24", "2026-10-24")

    assert _textos(panel) == ["⏳ Generando el reporte..."]


def test_las_preferencias_del_equipo_usan_el_usuario_y_el_huso_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("getpass.getuser", lambda: "supervisora")

    preferencias = preferencias_del_equipo()

    assert (preferencias.usuario, preferencias.limite) == ("supervisora", 200)
    assert preferencias.zona_horaria == datetime.now().astimezone().tzinfo


def test_el_reporte_de_cumplimiento_se_exporta_y_avisa_desde_la_interfaz(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)
    _exportar(panel, "2026-10-24", "2026-10-24")

    panel.buzon.atender()

    archivo = tmp_path / "Cumplimiento_EPP_2026-10-24_a_2026-10-24.xlsx"
    assert archivo.is_file()
    assert f"✅ Reporte exportado: {archivo} (1 filas)" in _textos(panel)


def test_una_fecha_invalida_no_genera_el_reporte(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)

    _exportar(panel, "24/10/2026", "2026-10-24")

    assert "❌ Fecha inválida: «24/10/2026». Usa el formato AAAA-MM-DD." in _textos(panel)
    assert list(tmp_path.glob("*.xlsx")) == []


def test_un_rango_al_reves_no_genera_el_reporte(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)

    _exportar(panel, "2026-10-25", "2026-10-24")

    assert "❌ La fecha «Desde» (2026-10-25) es posterior a «Hasta» (2026-10-24)." in _textos(panel)


def test_una_falla_al_generar_se_muestra_al_atender_el_buzon(
    raiz: ctk.CTk, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    (tmp_path / "Cumplimiento_EPP_2026-10-24_a_2026-10-24.xlsx").mkdir()
    panel = PanelReporteCumplimiento(raiz, conectar, tmp_path, UTC)
    _exportar(panel, "2026-10-24", "2026-10-24")

    panel.buzon.atender()

    assert any(t.startswith("❌ No se pudo generar el reporte:") for t in _textos(panel))
