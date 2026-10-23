"""Formato de zonas v1 y v2: lector dual y escritor v2 con copia de seguridad (SPEC/9 §6.3)."""

import json
from pathlib import Path

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ElementoDesconocidoError, ZonaSinPoligonoError
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import FormatoZonasError, escribir_zonas, leer_zonas

TRIANGULO = [[0, 0], [10, 0], [10, 10]]
CUADRADO = [[20, 20], [30, 20], [30, 30], [20, 30]]
V1 = {"Boca de pozo": TRIANGULO, "Taller": CUADRADO}
V2 = {
    "version": 2,
    "zonas": {"Boca de pozo": {"poligono": TRIANGULO, "epp_requerido": ["chaleco", "casco"]}},
}
BOCA_DE_POZO = ReglaZona(
    "Boca de pozo",
    ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)),
    frozenset({ElementoEPP.CASCO, ElementoEPP.CHALECO}),
)
TALLER = ReglaZona("Taller", ((20.0, 20.0), (30.0, 20.0), (30.0, 30.0), (20.0, 30.0)), frozenset())


def _archivo(tmp_path: Path, contenido: object) -> Path:
    ruta = tmp_path / "zonas_config.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def test_leer_zonas_sin_archivo_no_hay_zonas(tmp_path: Path) -> None:
    assert leer_zonas(tmp_path / "zonas_config.json") == ()


def test_leer_zonas_v1_se_lee_sin_epp_exigido(tmp_path: Path) -> None:
    zonas = leer_zonas(_archivo(tmp_path, V1))

    assert zonas == (ReglaZona(BOCA_DE_POZO.nombre, BOCA_DE_POZO.poligono, frozenset()), TALLER)


def test_leer_zonas_v1_con_una_zona_llamada_version_sigue_siendo_v1(tmp_path: Path) -> None:
    zonas = leer_zonas(_archivo(tmp_path, {"version": TRIANGULO}))

    assert [zona.nombre for zona in zonas] == ["version"]


def test_leer_zonas_v2_trae_el_epp_exigido(tmp_path: Path) -> None:
    assert leer_zonas(_archivo(tmp_path, V2)) == (BOCA_DE_POZO,)


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        ("{no es json", r"^El archivo de zonas .+ no es JSON válido: "),
        ("[1, 2]", r"^El archivo de zonas .+ debe ser un objeto JSON$"),
        ('{"version": 3, "zonas": {}}', r"^Versión de zonas no soportada: 3$"),
        ('{"version": 2}', r"^Formato v2 sin el objeto \"zonas\"$"),
        ('{"version": 2, "zonas": {"Z": [[0, 0]]}}', r'^La zona "Z" no tiene "poligono" y '),
        (
            '{"Z": [[0, 0], [1, 1, 1], [2, 2]]}',
            r'^La zona "Z" tiene un vértice inválido: \[1, 1, 1\]$',
        ),
        (
            '{"Z": [[0, 0], [true, 1], [2, 2]]}',
            r'^La zona "Z" tiene un vértice inválido: \[true, 1\]$',
        ),
        ('{"Z": "no es lista"}', r'^La zona "Z" tiene un polígono que no es una lista$'),
        (
            '{"version": 2, "zonas": {"Z": {"poligono": [], "epp_requerido": "casco"}}}',
            r'^La zona "Z" tiene un "epp_requerido" que no es una lista de nombres$',
        ),
    ],
    ids=[
        "corrupto",
        "no_objeto",
        "version_3",
        "v2_sin_zonas",
        "v2_sin_claves",
        "vertice_3d",
        "vertice_booleano",
        "poligono_texto",
        "epp_no_lista",
    ],
)
def test_leer_zonas_invalidas_falla_con_un_error_tipado(
    tmp_path: Path, contenido: str, mensaje: str
) -> None:
    ruta = tmp_path / "zonas_config.json"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(FormatoZonasError, match=mensaje):
        leer_zonas(ruta)


def test_leer_zonas_v2_con_un_elemento_desconocido_falla(tmp_path: Path) -> None:
    v2 = {"version": 2, "zonas": {"Z": {"poligono": TRIANGULO, "epp_requerido": ["botas"]}}}

    with pytest.raises(ElementoDesconocidoError):
        leer_zonas(_archivo(tmp_path, v2))


def test_leer_zonas_con_menos_de_tres_vertices_falla(tmp_path: Path) -> None:
    with pytest.raises(ZonaSinPoligonoError):
        leer_zonas(_archivo(tmp_path, {"Z": [[0, 0], [1, 1]]}))


def test_escribir_zonas_guarda_v2_y_respalda_el_v1_una_sola_vez(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, V1)
    original = ruta.read_text(encoding="utf-8")

    escribir_zonas(ruta, [BOCA_DE_POZO])
    escribir_zonas(ruta, [BOCA_DE_POZO, TALLER])

    copia = tmp_path / "zonas_config.v1.bak.json"
    assert (copia.read_text(encoding="utf-8"), leer_zonas(ruta)) == (
        original,
        (BOCA_DE_POZO, TALLER),
    )


def test_escribir_zonas_produce_el_formato_v2_del_plan(tmp_path: Path) -> None:
    ruta = tmp_path / "tenant" / "zonas" / "zonas_config.json"
    andamio = ReglaZona("Andamio Ñ", BOCA_DE_POZO.poligono, frozenset({ElementoEPP.CASCO}))

    escribir_zonas(ruta, [andamio])

    lineas = ["{", '    "version": 2,', '    "zonas": {', '        "Andamio Ñ": {']
    lineas += ['            "poligono": [', "                [", "                    0.0,"]
    assert ruta.read_text(encoding="utf-8").startswith("\n".join(lineas))
    assert json.loads(ruta.read_text(encoding="utf-8"))["zonas"]["Andamio Ñ"] == {
        "poligono": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
        "epp_requerido": ["casco"],
    }


def test_escribir_zonas_es_idempotente_y_no_respalda_un_v2(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, V2)
    escribir_zonas(ruta, [BOCA_DE_POZO])
    primera = ruta.read_bytes()

    escribir_zonas(ruta, [BOCA_DE_POZO])

    assert (ruta.read_bytes(), sorted(p.name for p in tmp_path.iterdir())) == (
        primera,
        ["zonas_config.json"],
    )


def test_escribir_zonas_sobre_un_archivo_corrupto_falla_sin_pisarlo(tmp_path: Path) -> None:
    ruta = tmp_path / "zonas_config.json"
    ruta.write_text("{corrupto", encoding="utf-8")

    with pytest.raises(FormatoZonasError):
        escribir_zonas(ruta, [BOCA_DE_POZO])

    assert ruta.read_text(encoding="utf-8") == "{corrupto"


def test_escribir_zonas_nunca_pisa_la_copia_del_v1_original(tmp_path: Path) -> None:
    ruta = _archivo(tmp_path, V1)
    original = ruta.read_text(encoding="utf-8")
    escribir_zonas(ruta, [BOCA_DE_POZO])
    _archivo(tmp_path, {"Taller": CUADRADO})

    escribir_zonas(ruta, [TALLER])

    assert (tmp_path / "zonas_config.v1.bak.json").read_text(encoding="utf-8") == original
