"""Caso de uso EvaluarCumplimiento con puertos falsos en memoria (SPEC/9 §4.5)."""

import dataclasses
from collections.abc import Iterable
from datetime import timedelta

import pytest

from src.ppe.application.evaluar_cumplimiento import (
    EstadoCumplimiento,
    EvaluarCumplimiento,
    FotogramaEPP,
    PersonaEnEscena,
)
from src.ppe.domain.asociacion import ConfiguracionAsociacion
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.infracciones import (
    GestorInfracciones,
    Incumplimiento,
    InfraccionFinalizada,
    InfraccionIniciada,
)
from src.ppe.domain.reglas import ReglasEPP, ReglaZona
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from tests.dobles_ppe import INICIO, PuertosEnMemoria, RelojFalso
from tests.escenas_ppe import TODO_EL_EPP, Operario

CASCO, CHALECO, GUANTES = ElementoEPP.CASCO, ElementoEPP.CHALECO, ElementoEPP.GUANTES
SIN_CASCO = (CHALECO, GUANTES)
BOCA_DE_POZO = "Boca de pozo"
EN_LA_BOCA = frozenset({BOCA_DE_POZO})
VERSION = "epp-0.1.0"
UN_SEGUNDO = timedelta(seconds=1)
ANA = Operario(track_id=1)
BETO = Operario(track_id=2, x=300.0)


@dataclasses.dataclass
class Escenario:
    reloj: RelojFalso
    puertos: PuertosEnMemoria
    caso: EvaluarCumplimiento

    def correr(self, fotogramas: Iterable[FotogramaEPP]) -> list[list[EstadoCumplimiento]]:
        """Evalúa un fotograma por segundo."""
        return [self._evaluar(fotograma) for fotograma in fotogramas]

    def _evaluar(self, fotograma: FotogramaEPP) -> list[EstadoCumplimiento]:
        estados = self.caso.evaluar(fotograma)
        self.reloj.avanzar(UN_SEGUNDO)
        return estados


@pytest.fixture
def escenario() -> Escenario:
    reloj, puertos = RelojFalso(), PuertosEnMemoria()
    zona = ReglaZona(BOCA_DE_POZO, ((0, 0), (1, 0), (0, 1)), frozenset({CASCO, CHALECO, GUANTES}))
    ventana = ConfiguracionVentana(0.8, 4 * UN_SEGUNDO, 2, 10 * UN_SEGUNDO)
    caso = EvaluarCumplimiento(
        ConfiguracionAsociacion(ioa_minimo_ancla=0.5, ioa_minimo_epp=0.5),
        ReglasEPP(globales=frozenset(), zonas=(zona,)),
        VentanaTemporal(ventana, reloj),
        GestorInfracciones(timedelta(minutes=5), VERSION, reloj),
        puertos.como_puertos(),
    )
    return Escenario(reloj, puertos, caso)


def _en_escena(
    operario: Operario, zonas: frozenset[str] = EN_LA_BOCA, nombre: str | None = None
) -> PersonaEnEscena:
    return PersonaEnEscena(operario.track_id, operario.persona.caja, zonas, nombre)


def _fotogramas(
    cantidad: int, persona: PersonaEnEscena, epp: Iterable[ElementoEPP], desde: int = 0
) -> list[FotogramaEPP]:
    operario = Operario(track_id=persona.track_id, x=persona.caja.x1)
    detecciones = operario.epp(*epp)
    return [
        FotogramaEPP((persona,), operario.anclas, detecciones, f"frame-{desde + numero}")
        for numero in range(cantidad)
    ]


def _iniciada(incumplimiento: Incumplimiento, segundo: int) -> InfraccionIniciada:
    return InfraccionIniciada(incumplimiento, INICIO + segundo * UN_SEGUNDO, VERSION, None)


def test_evaluar_cumplimiento_operario_con_todo_cumple_y_no_genera_eventos(
    escenario: Escenario,
) -> None:
    estados = escenario.correr(_fotogramas(6, _en_escena(ANA), TODO_EL_EPP))

    assert ([estado.cumple for estado in estados[-1]], escenario.puertos.llamadas) == ([True], [])


def test_evaluar_cumplimiento_antes_de_confirmar_no_hay_infraccion(escenario: Escenario) -> None:
    estados = escenario.correr(_fotogramas(4, _en_escena(ANA), SIN_CASCO))

    assert (estados[-1][0].estados[CASCO], escenario.puertos.llamadas) == (
        EstadoElemento.PRESENTE,
        [],
    )


@pytest.mark.parametrize("nombre", [None, "Ana"], ids=["no_reconocido", "reconocido"])
def test_evaluar_cumplimiento_falta_confirmada_guarda_evidencia_persiste_y_publica(
    escenario: Escenario, nombre: str | None
) -> None:
    escenario.correr(_fotogramas(5, _en_escena(ANA, nombre=nombre), SIN_CASCO))

    iniciada = _iniciada(Incumplimiento(1, nombre, CASCO, BOCA_DE_POZO), 4)
    con_evidencia = dataclasses.replace(iniciada, evidencia="evidencia/frame-4")
    assert escenario.puertos.llamadas == [
        ("guardar_evidencia", ("frame-4", ANA.persona.caja, iniciada)),
        ("guardar", con_evidencia),
        ("publicar", con_evidencia),
    ]


def test_evaluar_cumplimiento_cabeza_no_visible_no_alerta_ni_cumple(escenario: Escenario) -> None:
    sin_cabeza = FotogramaEPP((_en_escena(ANA),), ANA.manos, ANA.epp(*TODO_EL_EPP), "frame")

    estados = escenario.correr([sin_cabeza] * 6)

    assert (estados[-1][0].estados[CASCO], estados[-1][0].cumple, escenario.puertos.llamadas) == (
        EstadoElemento.NO_VERIFICABLE,
        False,
        [],
    )


def test_evaluar_cumplimiento_al_entrar_a_la_zona_sin_guantes_inicia_la_infraccion(
    escenario: Escenario,
) -> None:
    afuera = escenario.correr(_fotogramas(6, _en_escena(ANA, frozenset()), (CASCO, CHALECO)))
    escenario.correr(_fotogramas(1, _en_escena(ANA), (CASCO, CHALECO), desde=6))

    iniciada = _iniciada(Incumplimiento(1, None, GUANTES, BOCA_DE_POZO), 6)
    assert (afuera[-1][0].exigidos, afuera[-1][0].cumple) == (frozenset(), True)
    assert escenario.puertos.publicados == [
        dataclasses.replace(iniciada, evidencia="evidencia/frame-6")
    ]


def test_evaluar_cumplimiento_al_recuperar_el_casco_finaliza_sin_nueva_evidencia(
    escenario: Escenario,
) -> None:
    sin_casco = _fotogramas(5, _en_escena(ANA), SIN_CASCO)
    escenario.correr([*sin_casco, *_fotogramas(2, _en_escena(ANA), TODO_EL_EPP, desde=5)])

    incumplimiento = Incumplimiento(1, None, CASCO, BOCA_DE_POZO)
    finalizada = InfraccionFinalizada(
        incumplimiento, INICIO + 4 * UN_SEGUNDO, VERSION, fin=INICIO + 6 * UN_SEGUNDO
    )
    assert escenario.puertos.llamadas[-2:] == [("guardar", finalizada), ("publicar", finalizada)]


def test_evaluar_cumplimiento_persona_que_deja_de_verse_finaliza_su_infraccion(
    escenario: Escenario,
) -> None:
    vacio = FotogramaEPP((), (), (), "vacio")

    escenario.correr([*_fotogramas(5, _en_escena(ANA), SIN_CASCO), vacio])

    ultimo = escenario.puertos.publicados[-1]
    assert (type(ultimo), ultimo.fin) == (InfraccionFinalizada, INICIO + 5 * UN_SEGUNDO)


def test_evaluar_cumplimiento_evalua_cada_persona_por_separado(escenario: Escenario) -> None:
    personas = (_en_escena(ANA), _en_escena(BETO))
    epp = (*ANA.epp(*TODO_EL_EPP), *BETO.epp(*SIN_CASCO))
    fotogramas = [
        FotogramaEPP(personas, (*ANA.anclas, *BETO.anclas), epp, f"frame-{n}") for n in range(5)
    ]

    estados = escenario.correr(fotogramas)

    iniciada = _iniciada(Incumplimiento(2, None, CASCO, BOCA_DE_POZO), 4)
    assert [estado.cumple for estado in estados[-1]] == [True, False]
    assert escenario.puertos.llamadas[0] == (
        "guardar_evidencia",
        ("frame-4", BETO.persona.caja, iniciada),
    )


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
        _en_escena(ANA),
        FotogramaEPP((), (), (), "frame"),
        EstadoCumplimiento(1, {}, frozenset()),
        PuertosEnMemoria().como_puertos(),
    ],
    ids=lambda valor: type(valor).__name__,
)
def test_valores_del_caso_de_uso_son_inmutables(valor: object) -> None:
    campo = dataclasses.fields(valor)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(valor, campo, None)


def test_evaluar_cumplimiento_no_cambia_de_colaboradores(escenario: Escenario) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        escenario.caso.reglas = ReglasEPP(globales=frozenset(), zonas=())
