"""Vista del editor de EPP por zona con Tk real (SPEC/9 §8.3, §8.5).

Integración: necesita una pantalla (el gate corre la suite bajo xvfb). La lógica se prueba en
test_presentador_zonas.py; aquí solo se verifica que la vista muestre lo que dice el
presentador y le pase los clics.
"""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import customtkinter as ctk
import numpy as np
import pytest

from config import config
from src.gui import views
from src.gui.panel_dibujo_zonas import PanelDibujoZonas
from src.gui.panel_zonas import PanelZonas
from src.gui.presentador_zonas import PresentadorZonas
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import escribir_zonas, leer_zonas

pytestmark = pytest.mark.integration

CASCO = ElementoEPP.CASCO
CHALECO = ElementoEPP.CHALECO
CUADRADO = ((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0))


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


@pytest.fixture
def ruta(tmp_path: Path) -> Path:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona("Boca de pozo", CUADRADO, frozenset({CASCO}))])
    return ruta


def _hijos(widget: ctk.CTkBaseClass) -> list[ctk.CTkBaseClass]:
    hijos = []
    for hijo in widget.winfo_children():
        hijos.append(hijo)
        hijos.extend(_hijos(hijo))
    return hijos


def _casillas(panel: PanelZonas) -> dict[str, ctk.CTkCheckBox]:
    return {hijo.cget("text"): hijo for hijo in _hijos(panel) if isinstance(hijo, ctk.CTkCheckBox)}


def _boton(panel: PanelZonas, texto: str) -> ctk.CTkButton:
    (boton,) = (
        h for h in _hijos(panel) if isinstance(h, ctk.CTkButton) and h.cget("text") == texto
    )
    return boton


def _textos(panel: PanelZonas) -> list[str]:
    return [hijo.cget("text") for hijo in _hijos(panel) if isinstance(hijo, ctk.CTkLabel)]


def _panel(raiz: ctk.CTk, ruta: Path) -> PanelZonas:
    return PanelZonas(raiz, PresentadorZonas(ruta, (CASCO, CHALECO)))


def test_panel_muestra_las_casillas_de_cada_zona_con_lo_exigido(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)

    casillas = _casillas(panel)
    assert "Boca de pozo" in _textos(panel)
    assert {texto: casilla.get() for texto, casilla in casillas.items()} == {
        "Casco": 1,
        "Chaleco": 0,
    }


def test_panel_muestra_titulo_sin_aviso_y_el_nombre_de_cada_zona(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)

    # El último texto es el rótulo vacío de la lista desplazable.
    assert _textos(panel) == ["Zonas y EPP exigido", "", "Boca de pozo", ""]


def test_panel_marcar_una_casilla_y_guardar_escribe_el_epp(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)

    _casillas(panel)["Chaleco"].toggle()
    _boton(panel, "Guardar").invoke()

    assert leer_zonas(ruta)[0].exigidos == frozenset({CASCO, CHALECO})
    assert "Zonas guardadas" in _textos(panel)


def test_panel_descartar_vuelve_a_lo_guardado(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    _casillas(panel)["Casco"].toggle()

    _boton(panel, "Descartar cambios").invoke()

    assert _casillas(panel)["Casco"].get() == 1
    assert leer_zonas(ruta)[0].exigidos == frozenset({CASCO})


def test_panel_muestra_el_aviso_si_no_hay_zonas(raiz: ctk.CTk, tmp_path: Path) -> None:
    panel = _panel(raiz, tmp_path / "zonas.json")

    assert "No hay zonas configuradas para esta sucursal" in _textos(panel)
    assert _casillas(panel) == {}


def _vista_de_la_aplicacion(
    raiz: ctk.CTk,
    ruta: Path,
    monkeypatch: pytest.MonkeyPatch,
    camara: tuple[int, int] = (800, 450),
) -> tuple[PanelDibujoZonas, PanelZonas]:
    monkeypatch.setattr(config, "get_zonas_file", lambda: str(ruta))
    ancho, alto = camara
    vista = views.create_zones_view(raiz, lambda: np.zeros((alto, ancho, 3), dtype=np.uint8))
    (dibujo,) = (h for h in _hijos(vista) if isinstance(h, PanelDibujoZonas))
    (epp,) = (h for h in _hijos(vista) if isinstance(h, PanelZonas))
    return dibujo, epp


def test_la_vista_de_zonas_de_la_aplicacion_usa_el_editor_de_epp(
    raiz: ctk.CTk, ruta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dibujo, epp = _vista_de_la_aplicacion(raiz, ruta, monkeypatch)

    assert set(_casillas(epp)) == {"Casco", "Chaleco"}


def test_una_zona_dibujada_en_la_aplicacion_aparece_en_el_editor_de_epp(
    raiz: ctk.CTk, ruta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dibujo, epp = _vista_de_la_aplicacion(raiz, ruta, monkeypatch)
    dibujo.tomar_foto()
    dibujo.clic(SimpleNamespace(x=200, y=200))
    dibujo.clic(SimpleNamespace(x=300, y=200))
    dibujo.clic(SimpleNamespace(x=300, y=300))
    dibujo.nombre.insert(0, "Taller")

    dibujo.guardar()

    assert "Taller" in _textos(epp)
    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Boca de pozo", "Taller"]


def test_la_vista_de_zonas_pone_el_dibujo_a_la_izquierda_y_el_epp_a_la_derecha(
    raiz: ctk.CTk, ruta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dibujo, epp = _vista_de_la_aplicacion(raiz, ruta, monkeypatch)
    marco = dibujo.master
    lugar_dibujo, lugar_epp = dibujo.grid_info(), epp.grid_info()

    assert (lugar_dibujo["row"], lugar_dibujo["column"], lugar_dibujo["padx"]) == (0, 0, (0, 10))
    assert (lugar_epp["row"], lugar_epp["column"]) == (0, 1)
    assert [marco.grid_columnconfigure(c)["weight"] for c in (0, 1, 2)] == [0, 1, 0]
    assert [marco.grid_rowconfigure(r)["weight"] for r in (0, 1)] == [1, 0]


@pytest.mark.parametrize(
    ("camara", "lienzo"),
    [((1600, 400), (720, 180)), ((400, 900), (180, 405))],
    ids=["limitada_a_720_de_ancho", "limitada_a_405_de_alto"],
)
def test_la_foto_de_la_camara_entra_en_720_por_405_para_dibujar(
    raiz: ctk.CTk,
    ruta: Path,
    monkeypatch: pytest.MonkeyPatch,
    camara: tuple[int, int],
    lienzo: tuple[int, int],
) -> None:
    dibujo, _epp = _vista_de_la_aplicacion(raiz, ruta, monkeypatch, camara)

    dibujo.tomar_foto()

    assert (int(dibujo.lienzo.cget("width")), int(dibujo.lienzo.cget("height"))) == lienzo
