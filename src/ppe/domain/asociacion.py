"""Asociación del EPP y de las anclas corporales a cada persona (SPEC/9 §4.1, ADR-002).

1. Cada ancla detectada va a la persona cuya región la cubre con mayor IoA (intersección sobre
   el área del ancla), si alcanza el mínimo configurado. La región de una cabeza es el tercio
   superior de la caja de la persona; la de una mano, la caja entera. En empate gana la persona
   de centro más cercano y, si persiste, la primera recibida.
2. Cada persona con caja no degenerada tiene además un torso, que no se detecta.
3. Por persona y elemento: sin anclas del tipo que el elemento necesita, NO_VERIFICABLE.

Las anclas sin persona se ignoran y se registran en el log (sin datos personales).
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, TipoAncla
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import ObservacionFrame, PersonaDetectada
from src.ppe.domain.validacion import exigir_fraccion

LOGGER = logging.getLogger(__name__)
FIN_DE_LA_CABEZA = 1 / 3


@dataclass(frozen=True)
class ConfiguracionAsociacion:
    """IoA mínimo para asignar un ancla a una persona, en (0, 1]. Sin valor por defecto."""

    ioa_minimo_ancla: float

    def __post_init__(self) -> None:
        exigir_fraccion("ioa_minimo_ancla", self.ioa_minimo_ancla)


class _AnclaDePersona(NamedTuple):
    track_id: int
    tipo: TipoAncla
    caja: Caja


def asociar_epp(
    observacion: ObservacionFrame, configuracion: ConfiguracionAsociacion
) -> dict[int, dict[ElementoEPP, EstadoElemento]]:
    """Estado de cada elemento de EPP para cada persona del frame, por track_id."""
    anclas = _anclas_de_personas(observacion, configuracion.ioa_minimo_ancla)
    anclas += _torsos(observacion.personas)
    return {
        persona.track_id: _estados(persona.track_id, anclas) for persona in observacion.personas
    }


def _mejor_region(
    caja: Caja, regiones: Iterable[tuple[int, Caja]], ioa_minimo: float
) -> int | None:
    """Clave de la región que más cubre a `caja`; en empate, centro más cercano y luego orden."""
    puntajes = {
        clave: (caja.ioa(region), -caja.distancia_entre_centros(region))
        for clave, region in regiones
    }
    candidatas = [clave for clave, (ioa, _) in puntajes.items() if ioa >= ioa_minimo]
    if not candidatas:
        return None
    return max(candidatas, key=puntajes.__getitem__)


def _region_del_ancla(persona: PersonaDetectada, tipo: TipoAncla) -> Caja:
    if tipo is TipoAncla.CABEZA:
        return persona.caja.franja_vertical(0, FIN_DE_LA_CABEZA)
    return persona.caja


def _anclas_de_personas(observacion: ObservacionFrame, ioa_minimo: float) -> list[_AnclaDePersona]:
    asignadas = []
    for ancla in observacion.anclas:
        regiones = [(p.track_id, _region_del_ancla(p, ancla.tipo)) for p in observacion.personas]
        track_id = _mejor_region(ancla.caja, regiones, ioa_minimo)
        if track_id is None:
            LOGGER.debug("Ancla %s sin persona: se ignora (%s)", ancla.tipo.name, ancla.caja)
        else:
            asignadas.append(_AnclaDePersona(track_id, ancla.tipo, ancla.caja))
    return asignadas


def _torsos(personas: Iterable[PersonaDetectada]) -> list[_AnclaDePersona]:
    return [
        _AnclaDePersona(persona.track_id, TipoAncla.TORSO, persona.caja)
        for persona in personas
        if not persona.caja.es_degenerada
    ]


def _estados(track_id: int, anclas: Sequence[_AnclaDePersona]) -> dict[ElementoEPP, EstadoElemento]:
    tipos_visibles = {ancla.tipo for ancla in anclas if ancla.track_id == track_id}
    return {
        elemento: (
            EstadoElemento.AUSENTE
            if elemento.ancla in tipos_visibles
            else EstadoElemento.NO_VERIFICABLE
        )
        for elemento in ElementoEPP
    }
