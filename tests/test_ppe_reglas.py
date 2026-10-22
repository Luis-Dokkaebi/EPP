"""EPP exigido por zona y regla global (SPEC/9 §4.3, AC-013)."""

import dataclasses

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ZonaSinPoligonoError
from src.ppe.domain.reglas import Exigencia, ReglasEPP, ReglaZona

CASCO, CHALECO, GUANTES, GAFAS = (
    ElementoEPP.CASCO,
    ElementoEPP.CHALECO,
    ElementoEPP.GUANTES,
    ElementoEPP.GAFAS,
)
TRIANGULO = ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))
BOCA_DE_POZO = ReglaZona("Boca de pozo", TRIANGULO, frozenset({CASCO, CHALECO, GUANTES}))
TALLER = ReglaZona("Taller", TRIANGULO, frozenset({CASCO, GAFAS}))
REGLAS = ReglasEPP(globales=frozenset({CASCO}), zonas=(BOCA_DE_POZO, TALLER))


def test_reglas_fuera_de_toda_zona_solo_exige_la_regla_global() -> None:
    assert REGLAS.exigencias(frozenset()) == (Exigencia(CASCO, None),)


def test_reglas_en_una_zona_no_configurada_solo_exige_la_regla_global() -> None:
    assert REGLAS.exigencias(frozenset({"Pasillo"})) == (Exigencia(CASCO, None),)


def test_reglas_sin_regla_global_ni_zona_no_exige_nada() -> None:
    reglas = ReglasEPP(globales=frozenset(), zonas=(BOCA_DE_POZO,))

    assert reglas.exigencias(frozenset()) == ()


def test_reglas_en_una_zona_la_zona_cubre_lo_que_tambien_exige_la_global() -> None:
    reglas = ReglasEPP(globales=frozenset({CASCO, GAFAS}), zonas=(BOCA_DE_POZO,))

    exigencias = reglas.exigencias(frozenset({"Boca de pozo"}))

    assert exigencias == (
        Exigencia(CASCO, "Boca de pozo"),
        Exigencia(CHALECO, "Boca de pozo"),
        Exigencia(GUANTES, "Boca de pozo"),
        Exigencia(GAFAS, None),
    )


def test_reglas_en_varias_zonas_exige_la_union_atribuida_a_cada_zona() -> None:
    exigencias = REGLAS.exigencias(frozenset({"Taller", "Boca de pozo"}))

    assert exigencias == (
        Exigencia(CASCO, "Boca de pozo"),
        Exigencia(CHALECO, "Boca de pozo"),
        Exigencia(GUANTES, "Boca de pozo"),
        Exigencia(CASCO, "Taller"),
        Exigencia(GAFAS, "Taller"),
    )


@pytest.mark.parametrize("vertices", [0, 2], ids=["sin_poligono", "dos_vertices"])
def test_regla_zona_sin_poligono_valido_es_invalida(vertices: int) -> None:
    with pytest.raises(
        ZonaSinPoligonoError,
        match=rf'^La zona "Boca de pozo" necesita un polígono de al menos 3 vértices; tiene '
        rf"{vertices}$",
    ):
        ReglaZona("Boca de pozo", TRIANGULO[:vertices], frozenset({CASCO}))


def test_regla_zona_con_tres_vertices_es_valida() -> None:
    assert BOCA_DE_POZO.poligono == TRIANGULO


@pytest.mark.parametrize(
    "valor", [Exigencia(CASCO, None), BOCA_DE_POZO, REGLAS], ids=lambda v: type(v).__name__
)
def test_valores_de_las_reglas_son_inmutables(valor: object) -> None:
    campo = dataclasses.fields(valor)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(valor, campo, None)
