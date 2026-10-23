"""Caso de uso por frame: asociación, ventana temporal, reglas e infracciones (SPEC/9 §4.5).

Recibe las personas seguidas (con sus zonas y su nombre si fueron reconocidas), las anclas y el
EPP del frame. Cada infracción que empieza se guarda con su evidencia; todo evento se persiste
antes de publicarse (outbox, SPEC/9 §7.1). Devuelve el estado por persona para que la UI lo
dibuje.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from src.ppe.application.ports import (
    AlmacenEvidenciasPort,
    PublicadorEventosPort,
    RepositorioInfraccionesPort,
)
from src.ppe.domain.asociacion import ConfiguracionAsociacion, asociar_epp
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import (
    EventoInfraccion,
    GestorInfracciones,
    Incumplimiento,
    InfraccionIniciada,
)
from src.ppe.domain.observacion import (
    AnclaDetectada,
    DeteccionEPP,
    ObservacionFrame,
    PersonaDetectada,
)
from src.ppe.domain.reglas import Exigencia, ReglasEPP
from src.ppe.domain.ventana_temporal import VentanaTemporal


@dataclass(frozen=True)
class PersonaEnEscena:
    """Persona seguida, las zonas donde está y su nombre si fue reconocida."""

    track_id: int
    caja: Caja
    zonas: frozenset[str]
    nombre: str | None


@dataclass(frozen=True)
class FotogramaEPP:
    """Lo que el pipeline entrega por frame; la imagen es opaca para el dominio."""

    personas: tuple[PersonaEnEscena, ...]
    anclas: tuple[AnclaDetectada, ...]
    epp: tuple[DeteccionEPP, ...]
    imagen: object


@dataclass(frozen=True)
class EstadoCumplimiento:
    """Estado filtrado de cada elemento de una persona y lo que se le exige."""

    track_id: int
    estados: Mapping[ElementoEPP, EstadoElemento]
    exigidos: frozenset[ElementoEPP]

    @property
    def cumple(self) -> bool:
        """Todo lo exigido está presente (lo no verificable no cuenta como cumplido)."""
        return all(self.estados[elemento] is EstadoElemento.PRESENTE for elemento in self.exigidos)


@dataclass(frozen=True)
class PuertosCumplimiento:
    """Adaptadores de salida que necesita el caso de uso."""

    repositorio: RepositorioInfraccionesPort
    almacen: AlmacenEvidenciasPort
    publicador: PublicadorEventosPort


@dataclass(frozen=True)
class EvaluarCumplimiento:
    """Evalúa el cumplimiento de EPP de cada persona, frame a frame.

    La ventana y el gestor de infracciones guardan el estado entre frames; ambos comparten
    el mismo RelojPort.
    """

    asociacion: ConfiguracionAsociacion
    reglas: ReglasEPP
    ventana: VentanaTemporal
    infracciones: GestorInfracciones
    puertos: PuertosCumplimiento

    def evaluar(self, fotograma: FotogramaEPP) -> list[EstadoCumplimiento]:
        """Registra y publica las infracciones del frame y devuelve el estado por persona."""
        filtrados = self.ventana.actualizar(asociar_epp(_observacion(fotograma), self.asociacion))
        exigencias = {p.track_id: self.reglas.exigencias(p.zonas) for p in fotograma.personas}
        incumplimientos = [
            Incumplimiento(persona.track_id, persona.nombre, exigencia.elemento, exigencia.zona)
            for persona in fotograma.personas
            for exigencia in exigencias[persona.track_id]
            if filtrados[persona.track_id][exigencia.elemento] is EstadoElemento.AUSENTE
        ]
        for evento in self.infracciones.actualizar(incumplimientos):
            self._registrar(evento, fotograma)
        return [
            EstadoCumplimiento(
                p.track_id, filtrados[p.track_id], _elementos(exigencias[p.track_id])
            )
            for p in fotograma.personas
        ]

    def _registrar(self, evento: EventoInfraccion, fotograma: FotogramaEPP) -> None:
        if isinstance(evento, InfraccionIniciada):
            evento = self._con_evidencia(evento, fotograma)
        self.puertos.repositorio.guardar(evento)
        self.puertos.publicador.publicar(evento)

    def _con_evidencia(
        self, iniciada: InfraccionIniciada, fotograma: FotogramaEPP
    ) -> InfraccionIniciada:
        track_id = iniciada.incumplimiento.track_id
        caja = next(p.caja for p in fotograma.personas if p.track_id == track_id)
        evidencia = self.puertos.almacen.guardar_evidencia(fotograma.imagen, caja, iniciada)
        return replace(iniciada, evidencia=evidencia)


def _observacion(fotograma: FotogramaEPP) -> ObservacionFrame:
    personas = tuple(PersonaDetectada(p.track_id, p.caja) for p in fotograma.personas)
    return ObservacionFrame(personas=personas, anclas=fotograma.anclas, epp=fotograma.epp)


def _elementos(exigencias: tuple[Exigencia, ...]) -> frozenset[ElementoEPP]:
    return frozenset(exigencia.elemento for exigencia in exigencias)
