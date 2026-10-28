"""Editor de zonas heredado: guarda en v2 sin romper el EPP exigido (SPEC/9 §8.3, C-12).

Antes escribía el formato v1 encima de cualquier archivo: con un archivo v2 lo mezclaba y lo
dejaba ilegible. Solo se prueba el guardado; la ventana interactiva de OpenCV no se abre.
"""

import runpy
import sys
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pytest

from config import config
from config.path_utils import ConfigManager
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.edicion_zonas import NombreDeZonaInvalidoError
from src.zones.formato_zonas import escribir_zonas, leer_zonas
from src.zones.zone_editor import ZoneEditor

CUADRADO = ((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0))
CASCO = frozenset({ElementoEPP.CASCO})


def _editor(ruta: Path) -> ZoneEditor:
    editor = ZoneEditor(output_path=str(ruta))
    editor.points = [(0, 0), (10, 0), (0, 10)]
    return editor


def test_zone_editor_sobre_un_archivo_v2_conserva_el_epp_exigido(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona("Boca de pozo", CUADRADO, CASCO)])

    _editor(ruta).save_zone("Boca de pozo")

    assert leer_zonas(ruta) == (
        ReglaZona("Boca de pozo", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)), CASCO),
    )


def test_zone_editor_crea_la_carpeta_y_el_archivo_si_faltan(tmp_path: Path) -> None:
    ruta = tmp_path / "data" / "zonas" / "zonas.json"

    _editor(ruta).save_zone("Playa")

    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Playa"]


def test_zone_editor_rechaza_un_nombre_con_separadores_de_ruta(tmp_path: Path) -> None:
    with pytest.raises(NombreDeZonaInvalidoError):
        _editor(tmp_path / "zonas.json").save_zone("../afuera")

    assert not (tmp_path / "zonas.json").exists()


def test_zone_editor_sin_ruta_guarda_en_las_zonas_de_la_sucursal_activa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regresión: buscaba config.ZONAS_FILE, que no existe, y guardaba en data/zonas/zonas.json,
    un archivo que la aplicación no lee."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Planta_Norte")
    editor = ZoneEditor()
    editor.points = [(0, 0), (10, 0), (0, 10)]

    editor.save_zone("Playa")

    ruta_de_la_sucursal = Path(config.get_zonas_file())
    assert ruta_de_la_sucursal.is_relative_to(tmp_path / "OficinaEficiencia" / "Tenants")
    assert [zona.nombre for zona in leer_zonas(ruta_de_la_sucursal)] == ["Playa"]


def test_zone_editor_un_clic_izquierdo_agrega_una_esquina(tmp_path: Path) -> None:
    editor = ZoneEditor(output_path=str(tmp_path / "zonas.json"))

    editor.click_event(cv2.EVENT_LBUTTONDOWN, 7, 9, 0, None)
    editor.click_event(cv2.EVENT_RBUTTONDOWN, 1, 1, 0, None)

    assert editor.points == [(7, 9)]


class VentanaFalsa:
    """Dobles de las funciones de ventana de OpenCV: guarda los clics y pulsa 's' a la segunda."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.teclas = iter([-1, ord("s")])
        self.mostradas: list[np.ndarray] = []
        self.cerrada = False
        monkeypatch.setattr(cv2, "namedWindow", lambda *_: None)
        monkeypatch.setattr(cv2, "setMouseCallback", self._registrar)
        monkeypatch.setattr(cv2, "imshow", lambda _nombre, imagen: self.mostradas.append(imagen))
        monkeypatch.setattr(cv2, "waitKey", lambda _ms: next(self.teclas))
        monkeypatch.setattr(cv2, "destroyAllWindows", self._cerrar)

    def _registrar(self, _ventana: str, al_clic: Callable[..., None]) -> None:
        al_clic(cv2.EVENT_LBUTTONDOWN, 0, 0, 0, None)
        al_clic(cv2.EVENT_LBUTTONDOWN, 10, 0, 0, None)
        al_clic(cv2.EVENT_LBUTTONDOWN, 0, 10, 0, None)

    def _cerrar(self) -> None:
        self.cerrada = True


def test_zone_editor_dibuja_los_clics_y_guarda_al_pulsar_s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foto = tmp_path / "frame.jpg"
    cv2.imwrite(str(foto), np.zeros((20, 20, 3), dtype=np.uint8))
    ruta = tmp_path / "zonas.json"
    ventana = VentanaFalsa(monkeypatch)

    ZoneEditor(output_path=str(ruta)).run(str(foto), "Playa")

    assert ventana.cerrada
    assert ventana.mostradas[0][0, 0].tolist() == [0, 255, 0]
    assert leer_zonas(ruta)[0].poligono == ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))


def test_zone_editor_sin_foto_no_abre_la_ventana_ni_guarda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ventana = VentanaFalsa(monkeypatch)
    ruta = tmp_path / "zonas.json"

    ZoneEditor(output_path=str(ruta)).run(str(tmp_path / "no_existe.jpg"), "Playa")

    assert "No se pudo cargar la imagen" in caplog.text
    assert not ventana.cerrada
    assert not ruta.exists()


def test_zone_editor_ejecutado_directamente_guarda_en_la_sucursal_del_argumento(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", None)
    monkeypatch.setattr(sys, "argv", ["zone_editor.py", "Planta_Sur"])
    VentanaFalsa(monkeypatch)
    monkeypatch.setattr(cv2, "imread", lambda _ruta: np.zeros((20, 20, 3), dtype=np.uint8))

    runpy.run_path("src/zones/zone_editor.py", run_name="__main__")

    assert [zona.nombre for zona in leer_zonas(Path(config.get_zonas_file()))] == ["Zona"]
    assert ConfigManager.get_active_tenant() == "Planta_Sur"
