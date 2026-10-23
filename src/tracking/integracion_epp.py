"""Puente entre el pipeline de cámaras y el caso de uso de EPP (SPEC/9 §5.1 y §5.3, C-07).

El pipeline calcula una sola vez el seguimiento y las zonas; este módulo traduce esas personas
y las detecciones de EPP y anclas del mismo frame a los tipos del dominio y llama al caso de uso.
Con poco CPU se evalúa cada `cada_n_frames` frames (la ventana temporal tolera los huecos) y entre
evaluaciones se conserva el último estado de cada persona que sigue en escena.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from src.inference.types import ClaseObjeto, Deteccion
from src.ppe.application.evaluar_cumplimiento import (
    EstadoCumplimiento,
    FotogramaEPP,
    PersonaEnEscena,
)
from src.ppe.domain.elementos import ElementoEPP, TipoAncla
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import AnclaDetectada, DeteccionEPP
from src.ppe.domain.validacion import exigir_al_menos_uno

ANCLAS = {ClaseObjeto.CABEZA: TipoAncla.CABEZA, ClaseObjeto.MANOS: TipoAncla.MANOS}
ELEMENTOS = {ClaseObjeto(elemento.value): elemento for elemento in ElementoEPP}
NOMBRE_DESCONOCIDO = "Unknown"


class EvaluadorEPP(Protocol):
    """Lo que la integración necesita del caso de uso EvaluarCumplimiento."""

    def evaluar(self, fotograma: FotogramaEPP) -> list[EstadoCumplimiento]:
        """Evalúa un frame y devuelve el estado por persona."""


def traducir_detecciones(
    detecciones: Iterable[Deteccion],
) -> tuple[tuple[AnclaDetectada, ...], tuple[DeteccionEPP, ...]]:
    """Anclas y EPP del frame en tipos del dominio; personas y celulares se ignoran."""
    lista = list(detecciones)
    anclas = tuple(AnclaDetectada(ANCLAS[d.clase], _caja(d)) for d in lista if d.clase in ANCLAS)
    epp = tuple(DeteccionEPP(ELEMENTOS[d.clase], _caja(d)) for d in lista if d.clase in ELEMENTOS)
    return anclas, epp


def personas_en_escena(track_data: Iterable[Mapping[str, Any]]) -> list[PersonaEnEscena]:
    """Personas seguidas por TrackingPipeline.process, con su caja, zonas y nombre."""
    return [
        PersonaEnEscena(
            dato["track_id"],
            Caja(*(float(coordenada) for coordenada in dato["bbox"])),
            dato["zones"],
            None if dato["name"] == NOMBRE_DESCONOCIDO else dato["name"],
        )
        for dato in track_data
    ]


class IntegracionEPP:
    """Evalúa el EPP del frame cada `cada_n_frames` frames (el primero siempre se evalúa)."""

    # Se asigna en la primera evaluación, que ocurre en el primer frame.
    _ultimos: dict[int, EstadoCumplimiento]

    def __init__(self, evaluador: EvaluadorEPP, cada_n_frames: int) -> None:
        self._evaluador = evaluador
        self._cada_n_frames = exigir_al_menos_uno("cada_n_frames", cada_n_frames)
        self._frames_para_evaluar = 0

    def evaluar(
        self, frame: object, personas: Sequence[PersonaEnEscena], detecciones: Sequence[Deteccion]
    ) -> dict[int, EstadoCumplimiento]:
        """Estado de cumplimiento de cada persona presente que ya fue evaluada."""
        if self._frames_para_evaluar == 0:
            anclas, epp = traducir_detecciones(detecciones)
            estados = self._evaluador.evaluar(FotogramaEPP(tuple(personas), anclas, epp, frame))
            self._ultimos = {estado.track_id: estado for estado in estados}
            self._frames_para_evaluar = self._cada_n_frames
        self._frames_para_evaluar -= 1
        return {
            p.track_id: self._ultimos[p.track_id] for p in personas if p.track_id in self._ultimos
        }


def _caja(deteccion: Deteccion) -> Caja:
    caja = deteccion.caja
    return Caja(caja.x1, caja.y1, caja.x2, caja.y2)
