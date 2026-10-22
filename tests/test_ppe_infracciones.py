"""Infracciones de EPP y enfriamiento de alertas (SPEC/9 §4.4, AC-013, AC-014)."""

import dataclasses
from datetime import timedelta

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.infracciones import (
    GestorInfracciones,
    Incumplimiento,
    InfraccionFinalizada,
    InfraccionIniciada,
)
from tests.dobles_ppe import INICIO, RelojFalso

ENFRIAMIENTO = timedelta(minutes=5)
UN_MINUTO = timedelta(minutes=1)
VERSION = "epp-0.1.0"
BOCA_DE_POZO = "Boca de pozo"
ANA_SIN_CASCO = Incumplimiento(1, "Ana", ElementoEPP.CASCO, BOCA_DE_POZO)


@pytest.fixture
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture
def gestor(reloj: RelojFalso) -> GestorInfracciones:
    return GestorInfracciones(ENFRIAMIENTO, VERSION, reloj)


def _iniciada(incumplimiento: Incumplimiento, minuto: float) -> InfraccionIniciada:
    return InfraccionIniciada(incumplimiento, INICIO + minuto * UN_MINUTO, VERSION, None)


def test_gestor_infracciones_un_incumplimiento_nuevo_inicia_una_infraccion(
    gestor: GestorInfracciones,
) -> None:
    assert gestor.actualizar([ANA_SIN_CASCO]) == [_iniciada(ANA_SIN_CASCO, 0)]


def test_gestor_infracciones_un_incumplimiento_sostenido_avisa_una_sola_vez(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(2 * ENFRIAMIENTO)

    assert gestor.actualizar([ANA_SIN_CASCO]) == []


def test_gestor_infracciones_al_dejar_de_incumplir_finaliza_con_su_duracion(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(timedelta(seconds=90))

    eventos = gestor.actualizar([])

    fin = INICIO + timedelta(seconds=90)
    assert eventos == [InfraccionFinalizada(ANA_SIN_CASCO, INICIO, VERSION, fin=fin)]
    assert eventos[0].duracion == timedelta(seconds=90)


@pytest.mark.parametrize(
    ("minutos_desde_el_aviso", "eventos_esperados"),
    [(4.5, []), (5, [_iniciada(ANA_SIN_CASCO, 5)])],
    ids=["dentro_del_enfriamiento_no_avisa", "al_vencer_vuelve_a_avisar"],
)
def test_gestor_infracciones_no_repite_el_aviso_dentro_del_enfriamiento(
    gestor: GestorInfracciones,
    reloj: RelojFalso,
    minutos_desde_el_aviso: float,
    eventos_esperados: list[InfraccionIniciada],
) -> None:
    gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(UN_MINUTO)
    gestor.actualizar([])
    reloj.avanzar((minutos_desde_el_aviso - 1) * UN_MINUTO)

    assert gestor.actualizar([ANA_SIN_CASCO]) == eventos_esperados


def test_gestor_infracciones_incumplimiento_que_sigue_tras_el_enfriamiento_avisa_al_vencer(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(UN_MINUTO)
    gestor.actualizar([])
    reloj.avanzar(UN_MINUTO)
    silenciado = gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(3 * UN_MINUTO)

    assert (silenciado, gestor.actualizar([ANA_SIN_CASCO])) == ([], [_iniciada(ANA_SIN_CASCO, 5)])


def test_gestor_infracciones_empleado_reconocido_que_cambia_de_track_no_duplica_la_alerta(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    mismo_empleado_otro_track = dataclasses.replace(ANA_SIN_CASCO, track_id=2)
    eventos = gestor.actualizar([ANA_SIN_CASCO])
    reloj.avanzar(UN_MINUTO)
    eventos += gestor.actualizar([mismo_empleado_otro_track])
    reloj.avanzar(UN_MINUTO)
    eventos += gestor.actualizar([])
    reloj.avanzar(UN_MINUTO)
    eventos += gestor.actualizar([mismo_empleado_otro_track])

    iniciadas = [evento for evento in eventos if isinstance(evento, InfraccionIniciada)]
    assert iniciadas == [_iniciada(ANA_SIN_CASCO, 0)]


def test_gestor_infracciones_persona_no_reconocida_se_identifica_por_su_track(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    desconocido = Incumplimiento(7, None, ElementoEPP.CHALECO, BOCA_DE_POZO)
    otro_desconocido = dataclasses.replace(desconocido, track_id=8)
    gestor.actualizar([desconocido])
    reloj.avanzar(UN_MINUTO)

    eventos = gestor.actualizar([desconocido, otro_desconocido])

    assert eventos == [_iniciada(otro_desconocido, 1)]


def test_gestor_infracciones_cambiar_de_zona_finaliza_en_una_e_inicia_en_la_otra(
    gestor: GestorInfracciones, reloj: RelojFalso
) -> None:
    fuera_de_zona = dataclasses.replace(ANA_SIN_CASCO, zona=None)
    gestor.actualizar([fuera_de_zona])
    reloj.avanzar(UN_MINUTO)

    eventos = gestor.actualizar([ANA_SIN_CASCO])

    fin = INICIO + UN_MINUTO
    assert eventos == [
        InfraccionFinalizada(fuera_de_zona, INICIO, VERSION, fin=fin),
        _iniciada(ANA_SIN_CASCO, 1),
    ]


def test_gestor_infracciones_rechaza_una_version_de_modelo_vacia(reloj: RelojFalso) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match="^version_modelo no puede estar vacía$"):
        GestorInfracciones(ENFRIAMIENTO, "", reloj)


def test_gestor_infracciones_rechaza_un_enfriamiento_no_positivo(reloj: RelojFalso) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match="^enfriamiento debe ser positivo"):
        GestorInfracciones(timedelta(0), VERSION, reloj)


@pytest.mark.parametrize(
    "valor",
    [ANA_SIN_CASCO, _iniciada(ANA_SIN_CASCO, 0)],
    ids=lambda valor: type(valor).__name__,
)
def test_valores_de_infracciones_son_inmutables(valor: object) -> None:
    campo = dataclasses.fields(valor)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(valor, campo, None)
