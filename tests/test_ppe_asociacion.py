"""Asociación del EPP y de las anclas corporales a cada persona (SPEC/9 §4.1, AC-010, AC-011)."""

import dataclasses
import logging
from collections.abc import Iterable

import pytest

from src.ppe.domain.asociacion import ConfiguracionAsociacion, asociar_epp
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, TipoAncla
from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import (
    AnclaDetectada,
    DeteccionEPP,
    ObservacionFrame,
    PersonaDetectada,
)
from tests.escenas_ppe import TODO_EL_EPP, Operario

EstadosPorElemento = dict[ElementoEPP, EstadoElemento]

CONFIGURACION = ConfiguracionAsociacion(ioa_minimo_ancla=0.5, ioa_minimo_epp=0.5)
PRESENTE = EstadoElemento.PRESENTE
AUSENTE = EstadoElemento.AUSENTE
NO_VERIFICABLE = EstadoElemento.NO_VERIFICABLE
CASCO = ElementoEPP.CASCO
GUANTES = ElementoEPP.GUANTES
DE_LA_CABEZA = (CASCO, ElementoEPP.GAFAS, ElementoEPP.BARBIJO)
ANA = Operario(track_id=1)
BETO = Operario(track_id=2, x=60.0)


def _asociar(
    personas: Iterable[PersonaDetectada],
    anclas: Iterable[AnclaDetectada] = (),
    epp: Iterable[DeteccionEPP] = (),
) -> dict[int, EstadosPorElemento]:
    observacion = ObservacionFrame(personas=tuple(personas), anclas=tuple(anclas), epp=tuple(epp))
    return asociar_epp(observacion, CONFIGURACION)


def _todos(estado: EstadoElemento) -> EstadosPorElemento:
    return dict.fromkeys(ElementoEPP, estado)


def _persona(track_id: int, x1: float, x2: float) -> PersonaDetectada:
    return PersonaDetectada(track_id=track_id, caja=Caja(x1, 0.0, x2, 300.0))


def _ancla(tipo: TipoAncla, *esquinas: float) -> AnclaDetectada:
    return AnclaDetectada(tipo=tipo, caja=Caja(*esquinas))


def _epp(elemento: ElementoEPP, *esquinas: float) -> DeteccionEPP:
    return DeteccionEPP(elemento=elemento, caja=Caja(*esquinas))


def _de(elemento: ElementoEPP, resultado: dict[int, EstadosPorElemento]) -> dict[int, object]:
    return {track_id: estados[elemento] for track_id, estados in resultado.items()}


def test_asociar_epp_sin_personas_retorna_vacio() -> None:
    assert _asociar(personas=(), anclas=ANA.anclas) == {}


def test_asociar_epp_persona_visible_sin_epp_queda_ausente() -> None:
    assert _asociar([ANA.persona], ANA.anclas) == {1: _todos(AUSENTE)}


def test_asociar_epp_n_personas_sin_epp_quedan_todas_ausentes() -> None:
    operarios = [Operario(track_id=numero, x=200.0 * numero) for numero in (1, 2, 3)]

    resultado = _asociar(
        [operario.persona for operario in operarios],
        [ancla for operario in operarios for ancla in operario.anclas],
    )

    assert resultado == {1: _todos(AUSENTE), 2: _todos(AUSENTE), 3: _todos(AUSENTE)}


def test_asociar_epp_sin_cabeza_visible_lo_de_la_cabeza_no_es_verificable() -> None:
    resultado = _asociar([ANA.persona], ANA.manos)

    assert resultado == {1: _todos(AUSENTE) | dict.fromkeys(DE_LA_CABEZA, NO_VERIFICABLE)}


def test_asociar_epp_sin_manos_visibles_los_guantes_no_son_verificables() -> None:
    resultado = _asociar([ANA.persona], [ANA.cabeza])

    assert resultado == {1: _todos(AUSENTE) | {GUANTES: NO_VERIFICABLE}}


@pytest.mark.parametrize(
    ("cabeza", "esperado"),
    [(ANA.cabeza, {1: AUSENTE, 2: NO_VERIFICABLE}), (BETO.cabeza, {1: NO_VERIFICABLE, 2: AUSENTE})],
    ids=["cabeza_de_ana", "cabeza_de_beto_dentro_de_la_caja_de_ana"],
)
def test_asociar_epp_operarios_solapados_cada_cabeza_va_a_su_persona(
    cabeza: AnclaDetectada, esperado: dict[int, EstadoElemento]
) -> None:
    resultado = _asociar([ANA.persona, BETO.persona], [cabeza])

    assert _de(CASCO, resultado) == esperado


@pytest.mark.parametrize(
    ("personas", "mano", "dueno"),
    [
        ((_persona(1, 0, 100), _persona(2, 50, 150)), (55.0, 140.0, 70.0, 160.0), 1),
        ((_persona(2, 50, 150), _persona(1, 0, 100)), (55.0, 140.0, 70.0, 160.0), 1),
        ((_persona(1, 0, 100), _persona(2, 50, 150)), (70.0, 140.0, 80.0, 160.0), 1),
        ((_persona(2, 50, 150), _persona(1, 0, 100)), (70.0, 140.0, 80.0, 160.0), 2),
    ],
    ids=[
        "centro_mas_cercano",
        "centro_mas_cercano_otro_orden",
        "empate_total",
        "empate_otro_orden",
    ],
)
def test_asociar_epp_ancla_cubierta_por_dos_personas_desempata_por_centro_y_orden(
    personas: tuple[PersonaDetectada, ...], mano: tuple[float, ...], dueno: int
) -> None:
    resultado = _asociar(personas, [_ancla(TipoAncla.MANOS, *mano)])

    assert _de(GUANTES, resultado) == {1: NO_VERIFICABLE, 2: NO_VERIFICABLE} | {dueno: AUSENTE}


@pytest.mark.parametrize(
    ("cabeza", "esperado"),
    [((40.0, 90.0, 60.0, 110.0), AUSENTE), ((40.0, 91.0, 60.0, 111.0), NO_VERIFICABLE)],
    ids=["mitad_en_el_tercio_superior", "apenas_menos_de_la_mitad"],
)
def test_asociar_epp_la_cabeza_debe_estar_en_el_tercio_superior_de_la_persona(
    cabeza: tuple[float, ...], esperado: EstadoElemento
) -> None:
    resultado = _asociar([_persona(1, 0, 100)], [_ancla(TipoAncla.CABEZA, *cabeza)])

    assert resultado[1][CASCO] is esperado


def test_asociar_epp_las_manos_valen_en_cualquier_parte_de_la_persona() -> None:
    mano_abajo = _ancla(TipoAncla.MANOS, 40.0, 270.0, 60.0, 290.0)

    resultado = _asociar([_persona(1, 0, 100)], [mano_abajo])

    assert resultado[1][GUANTES] is AUSENTE


def test_asociar_epp_persona_degenerada_no_es_verificable() -> None:
    sin_ancho = PersonaDetectada(track_id=1, caja=Caja(50.0, 0.0, 50.0, 300.0))

    assert _asociar([sin_ancho], ANA.anclas) == {1: _todos(NO_VERIFICABLE)}


def test_asociar_epp_cabeza_degenerada_no_es_verificable() -> None:
    cabeza_sin_ancho = _ancla(TipoAncla.CABEZA, 50.0, 10.0, 50.0, 40.0)

    resultado = _asociar([ANA.persona], [cabeza_sin_ancho])

    assert resultado[1][CASCO] is NO_VERIFICABLE


def test_asociar_epp_con_coordenadas_negativas_asocia_igual() -> None:
    saliendo_del_cuadro = Operario(track_id=1, x=-50.0, y=-20.0)

    resultado = _asociar(
        [saliendo_del_cuadro.persona],
        saliendo_del_cuadro.anclas,
        saliendo_del_cuadro.epp(*TODO_EL_EPP),
    )

    assert resultado == {1: _todos(PRESENTE)}


def test_asociar_epp_ignora_y_registra_el_ancla_sin_persona(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mano_suelta = _ancla(TipoAncla.MANOS, 500.0, 140.0, 520.0, 160.0)
    caplog.set_level(logging.DEBUG, logger="src.ppe.domain.asociacion")

    resultado = _asociar([ANA.persona], [mano_suelta])

    assert resultado[1][GUANTES] is NO_VERIFICABLE
    assert caplog.messages == [f"Ancla MANOS sin persona: se ignora ({mano_suelta.caja})"]


@pytest.mark.parametrize("campo", ["ioa_minimo_ancla", "ioa_minimo_epp"])
def test_configuracion_asociacion_rechaza_un_ioa_fuera_de_rango(campo: str) -> None:
    valores = {"ioa_minimo_ancla": 0.5, "ioa_minimo_epp": 0.5} | {campo: 0.0}

    with pytest.raises(ConfiguracionInvalidaError, match=rf"^{campo} debe estar en "):
        ConfiguracionAsociacion(**valores)


def test_configuracion_asociacion_es_inmutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        CONFIGURACION.ioa_minimo_ancla = 0.1


def test_asociar_epp_persona_con_todo_el_epp_queda_presente() -> None:
    resultado = _asociar([ANA.persona], ANA.anclas, ANA.epp(*TODO_EL_EPP))

    assert resultado == {1: _todos(PRESENTE)}


def test_asociar_epp_una_persona_con_epp_repetido_queda_presente() -> None:
    epp = (*ANA.epp(*TODO_EL_EPP), *ANA.epp(CASCO), *ANA.epp(ElementoEPP.CHALECO))

    assert _asociar([ANA.persona], ANA.anclas, epp) == {1: _todos(PRESENTE)}


def test_asociar_epp_casco_en_la_mano_no_cuenta_como_casco_puesto() -> None:
    resultado = _asociar([ANA.persona], ANA.anclas, [ANA.casco_en_la_mano()])

    assert resultado[1][CASCO] is AUSENTE


def test_asociar_epp_casco_sin_cabeza_visible_no_es_verificable() -> None:
    resultado = _asociar([ANA.persona], ANA.manos, ANA.epp(*TODO_EL_EPP))

    assert resultado == {1: _todos(PRESENTE) | dict.fromkeys(DE_LA_CABEZA, NO_VERIFICABLE)}


def test_asociar_epp_basta_un_guante_aunque_se_vean_las_dos_manos() -> None:
    un_guante = ANA.epp(GUANTES)[:1]

    resultado = _asociar([ANA.persona], ANA.anclas, un_guante)

    assert resultado[1][GUANTES] is PRESENTE


@pytest.mark.parametrize(
    ("casco", "esperado"),
    [(ANA.epp(CASCO), {1: PRESENTE, 2: AUSENTE}), (BETO.epp(CASCO), {1: AUSENTE, 2: PRESENTE})],
    ids=["casco_de_ana", "casco_de_beto_dentro_de_la_caja_de_ana"],
)
def test_asociar_epp_operarios_solapados_cada_casco_va_a_su_cabeza(
    casco: tuple[DeteccionEPP, ...], esperado: dict[int, EstadoElemento]
) -> None:
    resultado = _asociar([ANA.persona, BETO.persona], [ANA.cabeza, BETO.cabeza], casco)

    assert _de(CASCO, resultado) == esperado


CABEZA_IZQUIERDA = _ancla(TipoAncla.CABEZA, 60.0, 10.0, 100.0, 50.0)
CABEZA_DERECHA_ANCHA = _ancla(TipoAncla.CABEZA, 100.0, 10.0, 160.0, 50.0)
CABEZA_DERECHA_ESPEJO = _ancla(TipoAncla.CABEZA, 100.0, 10.0, 140.0, 50.0)


@pytest.mark.parametrize(
    ("anclas", "dueno"),
    [
        ((CABEZA_IZQUIERDA, CABEZA_DERECHA_ANCHA), 1),
        ((CABEZA_DERECHA_ANCHA, CABEZA_IZQUIERDA), 1),
        ((CABEZA_IZQUIERDA, CABEZA_DERECHA_ESPEJO), 1),
        ((CABEZA_DERECHA_ESPEJO, CABEZA_IZQUIERDA), 2),
    ],
    ids=[
        "centro_mas_cercano",
        "centro_mas_cercano_otro_orden",
        "empate_total",
        "empate_otro_orden",
    ],
)
def test_asociar_epp_epp_entre_dos_anclas_desempata_por_centro_y_orden(
    anclas: tuple[AnclaDetectada, ...], dueno: int
) -> None:
    personas = [_persona(1, 0, 100), _persona(2, 100, 200)]
    casco_entre_dos_cabezas = _epp(CASCO, 90.0, 10.0, 110.0, 30.0)

    resultado = _asociar(personas, anclas, [casco_entre_dos_cabezas])

    assert _de(CASCO, resultado) == {1: AUSENTE, 2: AUSENTE} | {dueno: PRESENTE}


@pytest.mark.parametrize(
    ("casco", "esperado"),
    [((40.0, 0.0, 60.0, 20.0), PRESENTE), ((40.0, -1.0, 60.0, 19.0), AUSENTE)],
    ids=["ioa_justo_en_el_minimo", "ioa_apenas_bajo_el_minimo"],
)
def test_asociar_epp_casco_cuenta_solo_desde_el_ioa_minimo(
    casco: tuple[float, ...], esperado: EstadoElemento
) -> None:
    cabeza = _ancla(TipoAncla.CABEZA, 40.0, 10.0, 60.0, 30.0)

    resultado = _asociar([_persona(1, 0, 100)], [cabeza], [_epp(CASCO, *casco)])

    assert resultado[1][CASCO] is esperado


@pytest.mark.parametrize(
    ("chaleco", "esperado"),
    [
        ((10.0, 100.0, 90.0, 200.0), PRESENTE),
        ((10.0, 100.0, 90.0, 150.0), PRESENTE),
        ((10.0, 150.0, 90.0, 200.0), PRESENTE),
        ((10.0, 40.0, 90.0, 140.0), AUSENTE),
        ((10.0, 160.0, 90.0, 260.0), AUSENTE),
    ],
    ids=["torso_entero", "mitad_superior", "mitad_inferior", "sobre_el_pecho", "sobre_las_piernas"],
)
def test_asociar_epp_el_chaleco_se_verifica_en_el_tercio_central(
    chaleco: tuple[float, ...], esperado: EstadoElemento
) -> None:
    resultado = _asociar([_persona(1, 0, 100)], epp=[_epp(ElementoEPP.CHALECO, *chaleco)])

    assert resultado[1][ElementoEPP.CHALECO] is esperado


def test_asociar_epp_casco_degenerado_no_cuenta() -> None:
    casco_sin_alto = _epp(CASCO, 40.0, 10.0, 60.0, 10.0)

    resultado = _asociar([ANA.persona], [ANA.cabeza], [casco_sin_alto])

    assert resultado[1][CASCO] is AUSENTE


def test_asociar_epp_ignora_y_registra_el_epp_sin_ancla_compatible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    casco_suelto = _epp(CASCO, 500.0, 0.0, 520.0, 20.0)
    caplog.set_level(logging.DEBUG, logger="src.ppe.domain.asociacion")

    resultado = _asociar([ANA.persona], ANA.anclas, [casco_suelto])

    assert resultado[1][CASCO] is AUSENTE
    assert caplog.messages == [f"EPP CASCO sin ancla compatible: se ignora ({casco_suelto.caja})"]
