"""Caso de uso EvaluarCumplimiento con puertos falsos en memoria (SPEC/9 §4.5)."""

import dataclasses

import pytest

from src.ppe.application.evaluar_cumplimiento import (
    EstadoCumplimiento,
    FotogramaEPP,
    PersonaEnEscena,
)
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.geometria import Caja

CASCO = ElementoEPP.CASCO


@pytest.mark.parametrize(
    ("exigidos", "estado_del_casco", "cumple"),
    [
        (frozenset({CASCO}), EstadoElemento.PRESENTE, True),
        (frozenset({CASCO}), EstadoElemento.AUSENTE, False),
        (frozenset({CASCO}), EstadoElemento.NO_VERIFICABLE, False),
        (frozenset(), EstadoElemento.AUSENTE, True),
    ],
    ids=["presente", "ausente", "no_verificable", "nada_exigido"],
)
def test_estado_cumplimiento_cumple_si_todo_lo_exigido_esta_presente(
    exigidos: frozenset[ElementoEPP], estado_del_casco: EstadoElemento, cumple: bool
) -> None:
    estado = EstadoCumplimiento(1, {CASCO: estado_del_casco}, exigidos)

    assert estado.cumple is cumple


@pytest.mark.parametrize(
    "valor",
    [
        PersonaEnEscena(1, Caja(0.0, 0.0, 1.0, 1.0), frozenset(), None),
        FotogramaEPP((), (), (), "frame"),
        EstadoCumplimiento(1, {}, frozenset()),
    ],
    ids=lambda valor: type(valor).__name__,
)
def test_valores_del_caso_de_uso_son_inmutables(valor: object) -> None:
    campo = dataclasses.fields(valor)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(valor, campo, None)
