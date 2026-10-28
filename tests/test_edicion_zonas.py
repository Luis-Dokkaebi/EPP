"""Guardar el polígono de una zona sin perder su EPP exigido (SPEC/9 §8.3, §6.3; TASK-5.3)."""

import json
from pathlib import Path

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ZonaSinPoligonoError
from src.ppe.domain.reglas import ReglaZona
from src.zones.edicion_zonas import (
    NombreDeZonaInvalidoError,
    ZonaInexistenteError,
    borrar_zona,
    guardar_poligono,
)
from src.zones.formato_zonas import (
    VERSION_ACTUAL,
    FormatoZonasError,
    escribir_zonas,
    leer_zonas,
)

TRIANGULO = [(0, 0), (10, 0), (0, 10)]
CUADRADO = ((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0))
CASCO = frozenset({ElementoEPP.CASCO})


def test_guardar_en_un_archivo_nuevo_crea_la_zona_sin_epp(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas" / "zonas.json"

    guardar_poligono(ruta, "Boca de pozo", TRIANGULO)

    assert leer_zonas(ruta) == (
        ReglaZona("Boca de pozo", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)), frozenset()),
    )


def test_guardar_una_zona_existente_conserva_su_epp_y_las_demas(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(
        ruta,
        [ReglaZona("Boca de pozo", CUADRADO, CASCO), ReglaZona("Playa", CUADRADO, frozenset())],
    )

    guardar_poligono(ruta, "Boca de pozo", TRIANGULO)

    assert leer_zonas(ruta) == (
        ReglaZona("Boca de pozo", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)), CASCO),
        ReglaZona("Playa", CUADRADO, frozenset()),
    )


def test_guardar_sobre_un_archivo_v1_lo_migra_con_respaldo(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    ruta.write_text(json.dumps({"Playa": [[0, 0], [5, 0], [5, 5], [0, 5]]}), encoding="utf-8")

    guardar_poligono(ruta, "Pozo Ñandú", TRIANGULO)

    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Playa", "Pozo Ñandú"]
    assert json.loads(ruta.read_text(encoding="utf-8"))["version"] == VERSION_ACTUAL
    assert (tmp_path / "zonas.v1.bak.json").exists()


@pytest.mark.parametrize("nombre", ["Boca de pozo", "Pozo Ñandú", "zona_1-a"])
def test_guardar_acepta_nombres_con_letras_numeros_espacios_y_guiones(
    tmp_path: Path, nombre: str
) -> None:
    ruta = tmp_path / "zonas.json"

    guardar_poligono(ruta, nombre, TRIANGULO)

    assert [zona.nombre for zona in leer_zonas(ruta)] == [nombre]


@pytest.mark.parametrize(
    "nombre",
    ["", "   ", "../otra", "a/b", "a\\b", "c:", "x;y", "comilla'", 'doble"', "a.b", " borde"],
)
def test_guardar_rechaza_nombres_que_no_son_texto_simple(tmp_path: Path, nombre: str) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona("Playa", CUADRADO, CASCO)])
    antes = ruta.read_bytes()

    with pytest.raises(
        NombreDeZonaInvalidoError,
        match=r"^El nombre de zona solo admite letras, números, espacios, '_' y '-': ",
    ):
        guardar_poligono(ruta, nombre, TRIANGULO)

    assert ruta.read_bytes() == antes


def test_guardar_un_poligono_de_menos_de_tres_vertices_no_toca_el_archivo(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona("Playa", CUADRADO, CASCO)])
    antes = ruta.read_bytes()

    with pytest.raises(ZonaSinPoligonoError):
        guardar_poligono(ruta, "Boca de pozo", [(0, 0), (1, 1)])

    assert ruta.read_bytes() == antes


def test_guardar_sobre_un_archivo_corrupto_falla_sin_pisarlo(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    ruta.write_text("{roto", encoding="utf-8")

    with pytest.raises(FormatoZonasError):
        guardar_poligono(ruta, "Boca de pozo", TRIANGULO)

    assert ruta.read_text(encoding="utf-8") == "{roto"


# --- Borrar una zona (SPEC/9 §8.3: editor de zonas en la aplicación) ---------------------------


def test_borrar_una_zona_conserva_las_demas_con_su_epp(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(
        ruta,
        [ReglaZona("Boca de pozo", CUADRADO, CASCO), ReglaZona("Taller", CUADRADO, frozenset())],
    )

    borrar_zona(ruta, "Taller")

    assert leer_zonas(ruta) == (ReglaZona("Boca de pozo", CUADRADO, CASCO),)


def test_borrar_la_ultima_zona_deja_el_archivo_sin_zonas(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona("Taller", CUADRADO, CASCO)])

    borrar_zona(ruta, "Taller")

    assert leer_zonas(ruta) == ()


@pytest.mark.parametrize("existentes", [[], ["Boca de pozo"]], ids=["sin_zonas", "otra_zona"])
def test_borrar_una_zona_inexistente_falla_sin_tocar_el_archivo(
    tmp_path: Path, existentes: list[str]
) -> None:
    ruta = tmp_path / "zonas.json"
    escribir_zonas(ruta, [ReglaZona(nombre, CUADRADO, CASCO) for nombre in existentes])
    antes = ruta.read_text(encoding="utf-8")

    with pytest.raises(ZonaInexistenteError, match="No existe la zona 'Taller'"):
        borrar_zona(ruta, "Taller")

    assert ruta.read_text(encoding="utf-8") == antes
