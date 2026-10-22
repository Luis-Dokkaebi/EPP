"""Confirmación temporal de la ausencia de EPP con histéresis (SPEC/9 §4.2, AC-012).

Por (track_id, elemento), una ausencia observada se **confirma** en un frame AUSENTE cuando
se cumplen las dos condiciones:

- desde el primer AUSENTE del episodio pasó al menos T (`tiempo_confirmacion`); así, una
  ausencia más corta que T nunca confirma (AC-012), y
- al menos el P % (`fraccion_ausente_minima`) de los frames verificables de los últimos T
  segundos, bordes incluidos, fueron AUSENTE.

M frames PRESENTE seguidos (`presentes_para_recuperar`) cierran el episodio y recuperan a
PRESENTE. Los frames NO_VERIFICABLE no cuentan ni a favor ni en contra. Mientras la ausencia no
se confirma, el estado filtrado es PRESENTE (o NO_VERIFICABLE si el frame no se pudo verificar).

El estado de un track que no se observa durante más de `tiempo_limpieza` se olvida. Un reloj que
retrocede es un error (RelojRetrocedioError): no se reinicia en silencio.
"""

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.errores import RelojRetrocedioError
from src.ppe.domain.reloj import RelojPort
from src.ppe.domain.validacion import (
    exigir_al_menos_uno,
    exigir_duracion_positiva,
    exigir_fraccion,
)


@dataclass(frozen=True)
class ConfiguracionVentana:
    """Umbrales de la histéresis (P, T, M y limpieza). Sin valores por defecto (D4)."""

    fraccion_ausente_minima: float
    tiempo_confirmacion: timedelta
    presentes_para_recuperar: int
    tiempo_limpieza: timedelta

    def __post_init__(self) -> None:
        exigir_fraccion("fraccion_ausente_minima", self.fraccion_ausente_minima)
        exigir_duracion_positiva("tiempo_confirmacion", self.tiempo_confirmacion)
        exigir_al_menos_uno("presentes_para_recuperar", self.presentes_para_recuperar)
        exigir_duracion_positiva("tiempo_limpieza", self.tiempo_limpieza)


@dataclass
class _Historial:
    configuracion: ConfiguracionVentana
    ultima_observacion: datetime
    verificables: deque[tuple[datetime, EstadoElemento]] = field(default_factory=deque)
    inicio_de_la_ausencia: datetime | None = None
    presentes_seguidos: int = 0
    confirmada_en: datetime | None = None

    def observar(self, estado: EstadoElemento, ahora: datetime) -> EstadoElemento:
        self.ultima_observacion = ahora
        if estado is EstadoElemento.AUSENTE:
            self._registrar_ausente(ahora)
        elif estado is EstadoElemento.PRESENTE:
            self._registrar_presente(ahora)
        if self.confirmada_en is not None:
            return EstadoElemento.AUSENTE
        if estado is EstadoElemento.NO_VERIFICABLE:
            return EstadoElemento.NO_VERIFICABLE
        return EstadoElemento.PRESENTE

    def _registrar_ausente(self, ahora: datetime) -> None:
        self._recordar(EstadoElemento.AUSENTE, ahora)
        self.presentes_seguidos = 0
        if self.inicio_de_la_ausencia is None:
            self.inicio_de_la_ausencia = ahora
        duracion = ahora - self.inicio_de_la_ausencia
        if duracion >= self.configuracion.tiempo_confirmacion and self._fraccion_suficiente():
            self.confirmada_en = self.confirmada_en or ahora

    def _registrar_presente(self, ahora: datetime) -> None:
        self._recordar(EstadoElemento.PRESENTE, ahora)
        self.presentes_seguidos += 1
        if self.presentes_seguidos >= self.configuracion.presentes_para_recuperar:
            self.confirmada_en = None
            self.inicio_de_la_ausencia = None

    def _recordar(self, estado: EstadoElemento, ahora: datetime) -> None:
        self.verificables.append((ahora, estado))
        while self.verificables[0][0] < ahora - self.configuracion.tiempo_confirmacion:
            self.verificables.popleft()

    def _fraccion_suficiente(self) -> bool:
        ausentes = [e for _, e in self.verificables if e is EstadoElemento.AUSENTE]
        fraccion = len(ausentes) / len(self.verificables)
        return fraccion >= self.configuracion.fraccion_ausente_minima


class VentanaTemporal:
    """Filtra, frame a frame, los estados observados por la asociación."""

    _ultimo_instante: datetime | None

    def __init__(self, configuracion: ConfiguracionVentana, reloj: RelojPort) -> None:
        self._configuracion = configuracion
        self._reloj = reloj
        self._historiales: dict[tuple[int, ElementoEPP], _Historial] = {}
        self._ultimo_instante = None

    def actualizar(
        self, observados: Mapping[int, Mapping[ElementoEPP, EstadoElemento]]
    ) -> dict[int, dict[ElementoEPP, EstadoElemento]]:
        """Registra los estados observados en este frame y devuelve los filtrados."""
        ahora = self._avanzar_reloj()
        self._olvidar_inactivos(ahora)
        return {
            track_id: {
                elemento: self._historial(track_id, elemento, ahora).observar(estado, ahora)
                for elemento, estado in estados.items()
            }
            for track_id, estados in observados.items()
        }

    def _avanzar_reloj(self) -> datetime:
        ahora = self._reloj.ahora()
        if self._ultimo_instante is not None and ahora < self._ultimo_instante:
            raise RelojRetrocedioError(f"El reloj retrocedió de {self._ultimo_instante} a {ahora}")
        self._ultimo_instante = ahora
        return ahora

    def _olvidar_inactivos(self, ahora: datetime) -> None:
        limite = ahora - self._configuracion.tiempo_limpieza
        self._historiales = {
            clave: historial
            for clave, historial in self._historiales.items()
            if historial.ultima_observacion >= limite
        }

    def _historial(self, track_id: int, elemento: ElementoEPP, ahora: datetime) -> _Historial:
        return self._historiales.setdefault(
            (track_id, elemento), _Historial(self._configuracion, ahora)
        )
