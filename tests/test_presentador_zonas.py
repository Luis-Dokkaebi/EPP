"""Presentador del editor de EPP por zona (SPEC/9 §8.3): toda la lógica, sin Tk.

Las casillas marcan qué elementos exige cada zona; guardar escribe el formato v2.
"""

import json
from pathlib import Path

import pytest

from src.gui.presentador_zonas import FilaZona, PresentadorZonas
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import escribir_zonas, leer_zonas

CASCO = ElementoEPP.CASCO
CHALECO = ElementoEPP.CHALECO
OFRECIDOS = (CASCO, CHALECO)
CUADRADO = ((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0))


@pytest.fixture
def ruta(tmp_path: Path) -> Path:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(
        ruta,
        [
            ReglaZona("Boca de pozo", CUADRADO, frozenset({CASCO})),
            ReglaZona("Playa", CUADRADO, frozenset()),
        ],
    )
    return ruta


def _presentador(ruta: Path) -> PresentadorZonas:
    presentador = PresentadorZonas(ruta, OFRECIDOS)
    presentador.cargar()
    return presentador


def test_presentador_muestra_cada_zona_con_su_epp_exigido(ruta: Path) -> None:
    presentador = _presentador(ruta)

    assert presentador.filas == [
        FilaZona("Boca de pozo", frozenset({CASCO})),
        FilaZona("Playa", frozenset()),
    ]
    assert (presentador.hay_cambios, presentador.mensaje) == (False, None)


def test_presentador_ofrece_los_elementos_configurados_con_su_texto(ruta: Path) -> None:
    presentador = _presentador(ruta)

    assert presentador.casillas == [(CASCO, "Casco"), (CHALECO, "Chaleco")]


def test_presentador_alternar_marca_y_desmarca_un_elemento(ruta: Path) -> None:
    presentador = _presentador(ruta)

    presentador.alternar("Playa", CHALECO)
    presentador.alternar("Boca de pozo", CASCO)

    assert presentador.filas == [
        FilaZona("Boca de pozo", frozenset()),
        FilaZona("Playa", frozenset({CHALECO})),
    ]
    assert presentador.hay_cambios is True


def test_presentador_guardar_escribe_v2_y_conserva_los_poligonos(ruta: Path) -> None:
    presentador = _presentador(ruta)
    presentador.alternar("Playa", CHALECO)

    presentador.guardar()

    assert leer_zonas(ruta) == (
        ReglaZona("Boca de pozo", CUADRADO, frozenset({CASCO})),
        ReglaZona("Playa", CUADRADO, frozenset({CHALECO})),
    )
    assert (presentador.hay_cambios, presentador.mensaje) == (False, "Zonas guardadas")


def test_presentador_descartar_vuelve_a_lo_guardado(ruta: Path) -> None:
    presentador = _presentador(ruta)
    presentador.alternar("Playa", CHALECO)

    presentador.cargar()

    assert presentador.filas[1] == FilaZona("Playa", frozenset())
    assert presentador.hay_cambios is False


def test_presentador_lee_un_archivo_v1_como_zonas_sin_epp(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    ruta.write_text(json.dumps({"Playa": [[0, 0], [5, 0], [5, 5]]}), encoding="utf-8")

    presentador = _presentador(ruta)

    assert presentador.filas == [FilaZona("Playa", frozenset())]


def test_presentador_sin_archivo_no_tiene_zonas(tmp_path: Path) -> None:
    presentador = _presentador(tmp_path / "zonas.json")

    assert presentador.filas == []
    assert presentador.mensaje == "No hay zonas configuradas para esta sucursal"


def test_presentador_con_un_archivo_corrupto_avisa_y_no_lo_pisa(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    ruta.write_text("{roto", encoding="utf-8")
    presentador = _presentador(ruta)

    presentador.guardar()

    assert presentador.filas == []
    assert presentador.mensaje is not None
    assert presentador.mensaje.startswith("No se pudo leer el archivo de zonas: ")
    assert ruta.read_text(encoding="utf-8") == "{roto"


def test_presentador_avisa_si_no_puede_guardar(tmp_path: Path, ruta: Path) -> None:
    presentador = _presentador(ruta)
    presentador.alternar("Playa", CHALECO)
    ruta.unlink()
    ruta.mkdir()

    presentador.guardar()

    assert presentador.mensaje is not None
    assert presentador.mensaje.startswith("No se pudieron guardar las zonas: ")
    assert presentador.hay_cambios is True


def test_presentador_alternar_una_zona_desconocida_falla(ruta: Path) -> None:
    presentador = _presentador(ruta)

    with pytest.raises(KeyError, match=r"^'Zona desconocida: Otra'$"):
        presentador.alternar("Otra", CASCO)


def test_presentador_antes_de_cargar_no_muestra_ni_guarda_nada(ruta: Path) -> None:
    antes = ruta.read_bytes()
    presentador = PresentadorZonas(ruta, OFRECIDOS)

    presentador.guardar()

    assert (presentador.filas, presentador.hay_cambios, presentador.mensaje) == ([], False, None)
    assert ruta.read_bytes() == antes


def test_presentador_exige_ofrecer_al_menos_un_elemento(ruta: Path) -> None:
    with pytest.raises(ValueError, match=r"^El editor debe ofrecer al menos un elemento de EPP$"):
        PresentadorZonas(ruta, ())
