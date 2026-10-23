"""Simulación del caso de uso de EPP para los escenarios Gherkin (SPEC/9 §4.6).

Un fotograma por segundo con el operario sintético de tests/escenas_ppe.py: sin cámaras, modelos
ni reloj real. Los umbrales son de prueba; los reales los fija el negocio (D4).
"""

import re
from collections.abc import Iterable
from datetime import datetime, timedelta

from src.ppe.application.evaluar_cumplimiento import (
    EstadoCumplimiento,
    EvaluarCumplimiento,
    FotogramaEPP,
    PersonaEnEscena,
)
from src.ppe.domain.asociacion import ConfiguracionAsociacion
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, elementos_desde_textos
from src.ppe.domain.infracciones import GestorInfracciones, InfraccionIniciada
from src.ppe.domain.observacion import DeteccionEPP
from src.ppe.domain.reglas import ReglasEPP, ReglaZona
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from tests.dobles_ppe import INICIO, PuertosEnMemoria, RelojFalso
from tests.escenas_ppe import Operario

UN_SEGUNDO = timedelta(seconds=1)
TIEMPO_DE_CONFIRMACION = 4 * UN_SEGUNDO
SEGUNDO_DE_CONFIRMACION = 4
SEGUNDO_DE_ENTRADA = 2
TRIANGULO = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))


def elementos_de(texto: str) -> frozenset[ElementoEPP]:
    """'casco, chaleco y guantes' -> {CASCO, CHALECO, GUANTES}."""
    return elementos_desde_textos(re.split(r", | y ", texto))


class SimulacionCumplimiento:
    """Un operario frente a una cámara, con las zonas y el EPP que pide el escenario."""

    def __init__(self, puertos: PuertosEnMemoria | None = None) -> None:
        self.reloj = RelojFalso()
        self.puertos = PuertosEnMemoria() if puertos is None else puertos
        self.nombre: str | None = None
        self.estados: list[EstadoCumplimiento] = []
        self._zonas: list[ReglaZona] = []
        self._operario = Operario(track_id=1)
        self._anclas = self._operario.anclas
        self._zonas_del_operario: frozenset[str] = frozenset()
        self._epp: tuple[DeteccionEPP, ...] = ()
        self._casco_oculto = range(0)
        self._segundo = 0
        self._caso: EvaluarCumplimiento | None = None

    def agregar_zona(self, nombre: str, exigidos: frozenset[ElementoEPP]) -> None:
        self._zonas.append(ReglaZona(nombre, TRIANGULO, exigidos))

    def ubicar_operario(self, zonas: Iterable[str], epp: Iterable[ElementoEPP]) -> None:
        self._zonas_del_operario = frozenset(zonas)
        self._epp = self._operario.epp(*epp)

    def ocultar_la_cabeza(self) -> None:
        self._anclas = self._operario.manos

    def poner_el_casco_en_la_mano(self) -> None:
        self._epp = (*self._epp, self._operario.casco_en_la_mano())

    def ocultar_el_casco_durante(self, duracion: timedelta) -> None:
        self._casco_oculto = range(1, 1 + duracion // UN_SEGUNDO)

    def transcurrir_hasta(self, segundo_final: int) -> None:
        """Evalúa un fotograma por segundo hasta `segundo_final` inclusive."""
        while self._segundo <= segundo_final:
            self.estados = self._caso_de_uso().evaluar(self._fotograma())
            self.reloj.avanzar(UN_SEGUNDO)
            self._segundo += 1

    def entrar_a(self, zona: str) -> None:
        """El operario entra a `zona` y se queda hasta que se cumple el tiempo de confirmación."""
        self.transcurrir_hasta(SEGUNDO_DE_ENTRADA - 1)
        self._zonas_del_operario = frozenset({zona})
        self.transcurrir_hasta(SEGUNDO_DE_CONFIRMACION)

    @property
    def alertas(self) -> list[InfraccionIniciada]:
        return [e for e in self.puertos.publicados if isinstance(e, InfraccionIniciada)]

    def situacion(self) -> str:
        return "cumple" if all(estado.cumple for estado in self.estados) else "no cumple"

    def estado_del(self, elemento: ElementoEPP) -> EstadoElemento:
        return self.estados[0].estados[elemento]

    def imagen_en(self, instante: datetime) -> str:
        return f"frame-{(instante - INICIO) // UN_SEGUNDO}"

    def _fotograma(self) -> FotogramaEPP:
        caja = self._operario.persona.caja
        persona = PersonaEnEscena(1, caja, self._zonas_del_operario, self.nombre)
        visibles = tuple(d for d in self._epp if not self._esta_oculto(d))
        return FotogramaEPP((persona,), self._anclas, visibles, f"frame-{self._segundo}")

    def _esta_oculto(self, deteccion: DeteccionEPP) -> bool:
        return deteccion.elemento is ElementoEPP.CASCO and self._segundo in self._casco_oculto

    def _caso_de_uso(self) -> EvaluarCumplimiento:
        if self._caso is None:
            self._caso = EvaluarCumplimiento(
                ConfiguracionAsociacion(ioa_minimo_ancla=0.5, ioa_minimo_epp=0.5),
                ReglasEPP(globales=frozenset(), zonas=tuple(self._zonas)),
                VentanaTemporal(
                    ConfiguracionVentana(0.8, TIEMPO_DE_CONFIRMACION, 2, 10 * UN_SEGUNDO),
                    self.reloj,
                ),
                GestorInfracciones(timedelta(minutes=5), "epp-prueba", self.reloj),
                self.puertos.como_puertos(),
            )
        return self._caso
