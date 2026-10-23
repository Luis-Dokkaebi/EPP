"""Lo que el dominio de EPP observa en un frame: personas, anclas y EPP (SPEC/9 §4.1)."""

import dataclasses

import pytest

from src.ppe.domain.elementos import ElementoEPP, TipoAncla
from src.ppe.domain.errores import ObservacionInvalidaError
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import (
    AnclaDetectada,
    DeteccionEPP,
    ObservacionFrame,
    PersonaDetectada,
)

CAJA = Caja(x1=0.0, y1=0.0, x2=10.0, y2=10.0)


@pytest.mark.parametrize("tipo", [TipoAncla.CABEZA, TipoAncla.MANOS], ids=["cabeza", "manos"])
def test_ancla_detectada_acepta_cabeza_y_manos(tipo: TipoAncla) -> None:
    ancla = AnclaDetectada(tipo=tipo, caja=CAJA)

    assert ancla.tipo is tipo


def test_ancla_detectada_rechaza_el_torso_porque_se_deriva_de_la_persona() -> None:
    with pytest.raises(
        ObservacionInvalidaError,
        match=r"^El ancla TORSO no se detecta: se deriva de la caja de la persona$",
    ):
        AnclaDetectada(tipo=TipoAncla.TORSO, caja=CAJA)


def test_observacion_frame_vacia_es_valida() -> None:
    observacion = ObservacionFrame(personas=(), anclas=(), epp=())

    assert (observacion.personas, observacion.anclas, observacion.epp) == ((), (), ())


def test_observacion_frame_con_track_id_repetido_es_invalida() -> None:
    personas = (PersonaDetectada(7, CAJA), PersonaDetectada(3, CAJA), PersonaDetectada(7, CAJA))

    with pytest.raises(
        ObservacionInvalidaError, match=r"^track_id repetido en el frame: \[3, 7, 7\]$"
    ):
        ObservacionFrame(personas=personas, anclas=(), epp=())


def test_observacion_frame_con_track_ids_distintos_es_valida() -> None:
    personas = (PersonaDetectada(1, CAJA), PersonaDetectada(2, CAJA))

    observacion = ObservacionFrame(personas=personas, anclas=(), epp=())

    assert observacion.personas == personas


@pytest.mark.parametrize(
    "valor",
    [
        PersonaDetectada(track_id=1, caja=CAJA),
        AnclaDetectada(tipo=TipoAncla.CABEZA, caja=CAJA),
        DeteccionEPP(elemento=ElementoEPP.CASCO, caja=CAJA),
        ObservacionFrame(personas=(), anclas=(), epp=()),
    ],
    ids=lambda valor: type(valor).__name__,
)
def test_valores_observados_son_inmutables(valor: object) -> None:
    campo = dataclasses.fields(valor)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(valor, campo, None)
