"""Infracciones de EPP y enfriamiento de alertas (SPEC/9 §4.4, AC-013, AC-014).

Una infracción es un elemento exigido con ausencia confirmada, por (persona, elemento, zona).
La persona se identifica por su nombre reconocido si lo hay; si no, por su track_id: si el
seguimiento cambia el track_id de un empleado reconocido, la infracción sigue siendo la misma.

- InfraccionIniciada (genera la alerta): aparece un incumplimiento sin infracción abierta.
- InfraccionFinalizada, con su duración: la clave deja de incumplir porque recuperó el elemento,
  salió de la zona que lo exigía o dejó de verse.
- Enfriamiento: no se repite el inicio de una clave antes de que pase el período desde su último
  inicio. Un incumplimiento en enfriamiento no abre infracción; si sigue cuando el período vence,
  abre una nueva.

Cada evento lleva la versión del modelo que lo detectó (contrato de mle-workflow).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.reloj import RelojPort
from src.ppe.domain.validacion import exigir_duracion_positiva


class ClaveInfraccion(NamedTuple):
    """Identidad de una infracción: persona (nombre o track_id), elemento y zona."""

    persona: str | int
    elemento: ElementoEPP
    zona: str | None


@dataclass(frozen=True)
class Incumplimiento:
    """Elemento exigido y ausente (confirmado) en una persona, en el frame actual."""

    track_id: int
    nombre: str | None
    elemento: ElementoEPP
    zona: str | None

    @property
    def clave(self) -> ClaveInfraccion:
        return ClaveInfraccion(
            self.track_id if self.nombre is None else self.nombre, self.elemento, self.zona
        )


@dataclass(frozen=True)
class EventoInfraccion:
    """Lo común a todo evento de infracción."""

    incumplimiento: Incumplimiento
    inicio: datetime
    version_modelo: str


class InfraccionIniciada(EventoInfraccion):
    """Empieza una infracción: es el evento que genera la alerta.

    Sin campos propios, hereda el dataclass inmutable de EventoInfraccion.
    """


@dataclass(frozen=True)
class InfraccionFinalizada(EventoInfraccion):
    """Termina una infracción abierta."""

    fin: datetime

    @property
    def duracion(self) -> timedelta:
        return self.fin - self.inicio


class GestorInfracciones:
    """Abre y cierra infracciones frame a frame, con enfriamiento por clave."""

    def __init__(self, enfriamiento: timedelta, version_modelo: str, reloj: RelojPort) -> None:
        if not version_modelo:
            raise ConfiguracionInvalidaError("version_modelo no puede estar vacía")
        self._enfriamiento = exigir_duracion_positiva("enfriamiento", enfriamiento)
        self._version_modelo = version_modelo
        self._reloj = reloj
        self._abiertas: dict[ClaveInfraccion, InfraccionIniciada] = {}
        self._ultimos_inicios: dict[ClaveInfraccion, datetime] = {}

    def actualizar(self, incumplimientos: Iterable[Incumplimiento]) -> list[EventoInfraccion]:
        """Registra los incumplimientos de este frame y devuelve los eventos que provocan."""
        ahora = self._reloj.ahora()
        actuales = {incumplimiento.clave: incumplimiento for incumplimiento in incumplimientos}
        eventos: list[EventoInfraccion] = [
            self._finalizar(clave, ahora) for clave in list(self._abiertas) if clave not in actuales
        ]
        self._olvidar_inicios_vencidos(ahora)
        eventos += [
            self._iniciar(incumplimiento, ahora)
            for clave, incumplimiento in actuales.items()
            if clave not in self._abiertas and clave not in self._ultimos_inicios
        ]
        return eventos

    def _iniciar(self, incumplimiento: Incumplimiento, ahora: datetime) -> InfraccionIniciada:
        iniciada = InfraccionIniciada(incumplimiento, ahora, self._version_modelo)
        self._abiertas[incumplimiento.clave] = iniciada
        self._ultimos_inicios[incumplimiento.clave] = ahora
        return iniciada

    def _finalizar(self, clave: ClaveInfraccion, ahora: datetime) -> InfraccionFinalizada:
        iniciada = self._abiertas.pop(clave)
        return InfraccionFinalizada(
            iniciada.incumplimiento, iniciada.inicio, iniciada.version_modelo, fin=ahora
        )

    def _olvidar_inicios_vencidos(self, ahora: datetime) -> None:
        self._ultimos_inicios = {
            clave: instante
            for clave, instante in self._ultimos_inicios.items()
            if ahora - instante < self._enfriamiento
        }
