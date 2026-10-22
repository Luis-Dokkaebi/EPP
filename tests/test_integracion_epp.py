"""Puente entre el pipeline de cámaras y el caso de uso de EPP (SPEC/9 §5.1 y §5.3, C-07)."""

from typing import Any

import pytest

from src.inference.types import Caja, ClaseObjeto, Deteccion
from src.ppe.application.evaluar_cumplimiento import (
    EstadoCumplimiento,
    FotogramaEPP,
    PersonaEnEscena,
)
from src.ppe.domain import geometria
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, TipoAncla
from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.observacion import AnclaDetectada, DeteccionEPP
from src.tracking.integracion_epp import (
    IntegracionEPP,
    personas_en_escena,
    traducir_detecciones,
)

CAJA = Caja(10.0, 20.0, 30.0, 40.0)
CAJA_DOMINIO = geometria.Caja(10.0, 20.0, 30.0, 40.0)
CASCO = ElementoEPP.CASCO


class EvaluadorFalso:
    """Anota cada fotograma; el casco de la n-ésima evaluación vale el n-ésimo EstadoElemento."""

    def __init__(self) -> None:
        self.fotogramas: list[FotogramaEPP] = []

    def evaluar(self, fotograma: FotogramaEPP) -> list[EstadoCumplimiento]:
        self.fotogramas.append(fotograma)
        estado = list(EstadoElemento)[len(self.fotogramas) - 1]
        return [
            EstadoCumplimiento(p.track_id, {CASCO: estado}, frozenset()) for p in fotograma.personas
        ]


def _persona(track_id: int) -> PersonaEnEscena:
    return PersonaEnEscena(track_id, CAJA_DOMINIO, frozenset(), None)


def test_traducir_detecciones_separa_anclas_y_epp_e_ignora_lo_demas() -> None:
    detecciones = [Deteccion(clase, 0.9, CAJA) for clase in ClaseObjeto]

    anclas, epp = traducir_detecciones(detecciones)

    assert anclas == (
        AnclaDetectada(TipoAncla.CABEZA, CAJA_DOMINIO),
        AnclaDetectada(TipoAncla.MANOS, CAJA_DOMINIO),
    )
    assert epp == tuple(DeteccionEPP(elemento, CAJA_DOMINIO) for elemento in ElementoEPP)


@pytest.mark.parametrize(
    ("nombre", "esperado"), [("Unknown", None), ("Ana", "Ana")], ids=["desconocido", "reconocido"]
)
def test_personas_en_escena_toma_track_caja_zonas_y_nombre(
    nombre: str, esperado: str | None
) -> None:
    track_data: list[dict[str, Any]] = [
        {"track_id": 7, "bbox": (10, 20, 30, 40), "zones": frozenset({"Z"}), "name": nombre}
    ]

    assert personas_en_escena(track_data) == [
        PersonaEnEscena(7, CAJA_DOMINIO, frozenset({"Z"}), esperado)
    ]


def test_integracion_epp_evalua_cada_n_frames_y_conserva_el_ultimo_estado() -> None:
    evaluador = EvaluadorFalso()
    integracion = IntegracionEPP(evaluador, cada_n_frames=3)

    resultados = [integracion.evaluar("frame", [_persona(1)], []) for _ in range(7)]

    cascos = [estados[1].estados[CASCO] for estados in resultados]
    presente, ausente, no_verificable = EstadoElemento
    assert (len(evaluador.fotogramas), cascos) == (
        3,
        [presente] * 3 + [ausente] * 3 + [no_verificable],
    )


def test_integracion_epp_entrega_al_caso_de_uso_el_frame_y_las_detecciones() -> None:
    evaluador = EvaluadorFalso()
    casco = Deteccion(ClaseObjeto.CASCO, 0.9, CAJA)
    cabeza = Deteccion(ClaseObjeto.CABEZA, 0.9, CAJA)

    IntegracionEPP(evaluador, cada_n_frames=1).evaluar("imagen", [_persona(1)], [casco, cabeza])

    assert evaluador.fotogramas == [
        FotogramaEPP(
            (_persona(1),),
            (AnclaDetectada(TipoAncla.CABEZA, CAJA_DOMINIO),),
            (DeteccionEPP(ElementoEPP.CASCO, CAJA_DOMINIO),),
            "imagen",
        )
    ]


def test_integracion_epp_solo_devuelve_personas_presentes_ya_evaluadas() -> None:
    integracion = IntegracionEPP(EvaluadorFalso(), cada_n_frames=2)
    integracion.evaluar("frame", [_persona(1), _persona(2)], [])

    estados = integracion.evaluar("frame", [_persona(2), _persona(3)], [])

    assert list(estados) == [2]


def test_integracion_epp_rechaza_una_cadencia_menor_que_uno() -> None:
    with pytest.raises(ConfiguracionInvalidaError, match="^cada_n_frames debe ser al menos 1"):
        IntegracionEPP(EvaluadorFalso(), cada_n_frames=0)
