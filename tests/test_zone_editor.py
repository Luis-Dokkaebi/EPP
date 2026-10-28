"""Editor de zonas heredado: guarda en v2 sin romper el EPP exigido (SPEC/9 §8.3, C-12).

Antes escribía el formato v1 encima de cualquier archivo: con un archivo v2 lo mezclaba y lo
dejaba ilegible. Solo se prueba el guardado; la ventana interactiva de OpenCV no se abre.
"""

from pathlib import Path

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
