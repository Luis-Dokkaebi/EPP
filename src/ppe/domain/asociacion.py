"""Asociación del EPP y de las anclas corporales a cada persona (SPEC/9 §4.1, ADR-002).

1. Cada ancla detectada va a la persona cuya región la cubre con mayor IoA (intersección sobre
   el área del ancla), si alcanza el mínimo configurado. La región de una cabeza es el tercio
   superior de la caja de la persona; la de una mano, la caja entera.
2. Cada persona con caja no degenerada tiene además un torso: el tercio central de su caja.
3. Cada EPP va a una sola ancla compatible (casco, gafas y barbijo a la cabeza; guantes a las
   manos; chaleco al torso): la de mayor IoA sobre el área del EPP, con su propio mínimo.
4. Por persona y elemento: sin anclas del tipo que el elemento necesita, NO_VERIFICABLE; con el
   EPP en alguna de esas anclas, PRESENTE; si no, AUSENTE. Con dos manos visibles basta un
   guante: la verificación por mano queda para la iteración de guantes (D3).

En todo empate de IoA gana el centro más cercano y, si persiste, lo primero recibido. Las anclas
sin persona y el EPP sin ancla se ignoran y se registran en el log (sin datos personales).
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, TipoAncla
from src.ppe.domain.geometria import Caja
from src.ppe.domain.observacion import DeteccionEPP, ObservacionFrame, PersonaDetectada
from src.ppe.domain.validacion import exigir_fraccion

LOGGER = logging.getLogger(__name__)
FIN_DE_LA_CABEZA = 1 / 3
INICIO_DEL_TORSO = 1 / 3
FIN_DEL_TORSO = 2 / 3


@dataclass(frozen=True)
class ConfiguracionAsociacion:
    """IoA mínimos para asignar anclas a personas y EPP a anclas, en (0, 1]. Sin defaults."""

    ioa_minimo_ancla: float
    ioa_minimo_epp: float

    def __post_init__(self) -> None:
        exigir_fraccion("ioa_minimo_ancla", self.ioa_minimo_ancla)
        exigir_fraccion("ioa_minimo_epp", self.ioa_minimo_epp)


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
    con_epp = _anclas_con_epp(observacion.epp, anclas, configuracion.ioa_minimo_epp)
    return {
        persona.track_id: _estados(persona.track_id, anclas, con_epp)
        for persona in observacion.personas
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
        _AnclaDePersona(
            persona.track_id,
            TipoAncla.TORSO,
            persona.caja.franja_vertical(INICIO_DEL_TORSO, FIN_DEL_TORSO),
        )
        for persona in personas
        if not persona.caja.es_degenerada
    ]


def _anclas_con_epp(
    epp: Iterable[DeteccionEPP], anclas: Sequence[_AnclaDePersona], ioa_minimo: float
) -> set[tuple[int, ElementoEPP]]:
    """Pares (índice del ancla, elemento) de cada EPP asignado a un ancla compatible."""
    con_epp = set()
    for deteccion in epp:
        compatibles = [
            (indice, ancla.caja)
            for indice, ancla in enumerate(anclas)
            if ancla.tipo is deteccion.elemento.ancla
        ]
        indice = _mejor_region(deteccion.caja, compatibles, ioa_minimo)
        if indice is None:
            LOGGER.debug(
                "EPP %s sin ancla compatible: se ignora (%s)",
                deteccion.elemento.name,
                deteccion.caja,
            )
        else:
            con_epp.add((indice, deteccion.elemento))
    return con_epp


def _estados(
    track_id: int, anclas: Sequence[_AnclaDePersona], con_epp: set[tuple[int, ElementoEPP]]
) -> dict[ElementoEPP, EstadoElemento]:
    return {
        elemento: _estado(
            elemento,
            [
                indice
                for indice, ancla in enumerate(anclas)
                if ancla.track_id == track_id and ancla.tipo is elemento.ancla
            ],
            con_epp,
        )
        for elemento in ElementoEPP
    }


def _estado(
    elemento: ElementoEPP, anclas_propias: Sequence[int], con_epp: set[tuple[int, ElementoEPP]]
) -> EstadoElemento:
    if not anclas_propias:
        return EstadoElemento.NO_VERIFICABLE
    if any((indice, elemento) in con_epp for indice in anclas_propias):
        return EstadoElemento.PRESENTE
    return EstadoElemento.AUSENTE
