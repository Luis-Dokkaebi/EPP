"""Composición del módulo de EPP con los valores que decidió el negocio (SPEC/9 §5.4).

D4 (24/10/2026): evitar falsas alarmas, confirmar una ausencia durante 4 s y no repetir el aviso
de la misma persona, elemento y zona antes de 10 min. D5: las evidencias se guardan 30 días. El
resto son los valores técnicos propuestos en el plan: con D4 priorizando evitar falsas alarmas,
la ausencia se confirma si el 80 % de los frames verificables de esos 4 s la muestran.
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from src.ppe.application.evaluar_cumplimiento import EvaluarCumplimiento, PuertosCumplimiento
from src.ppe.application.ports import PublicadorEventosPort, RelojPort
from src.ppe.domain.asociacion import ConfiguracionAsociacion
from src.ppe.domain.infracciones import EventoInfraccion, GestorInfracciones
from src.ppe.domain.reglas import ReglasEPP
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from src.tracking.evidencias_epp import AlmacenEvidenciasCv2


@dataclass(frozen=True)
class ParametrosEPP:
    """Todo lo configurable del módulo, en un solo lugar."""

    tiempo_confirmacion: timedelta
    fraccion_ausente_minima: float
    presentes_para_recuperar: int
    tiempo_limpieza: timedelta
    enfriamiento: timedelta
    ioa_minimo_ancla: float
    ioa_minimo_epp: float
    retencion_dias: int
    cada_n_frames: int


PARAMETROS_DECIDIDOS = ParametrosEPP(
    tiempo_confirmacion=timedelta(seconds=4),
    fraccion_ausente_minima=0.8,
    presentes_para_recuperar=5,
    tiempo_limpieza=timedelta(seconds=30),
    enfriamiento=timedelta(minutes=10),
    ioa_minimo_ancla=0.5,
    ioa_minimo_epp=0.5,
    retencion_dias=30,
    cada_n_frames=1,
)


class RelojSistema:
    """Implementa RelojPort con la hora del sistema, siempre en UTC."""

    def ahora(self) -> datetime:
        return datetime.now(UTC)


class PublicadorEnMemoria:
    """Implementa PublicadorEventosPort: entrega cada evento a quien se suscribió (la UI)."""

    def __init__(self) -> None:
        self._suscriptores: list[Callable[[EventoInfraccion], None]] = []

    def suscribir(self, suscriptor: Callable[[EventoInfraccion], None]) -> None:
        self._suscriptores.append(suscriptor)

    def publicar(self, evento: EventoInfraccion) -> None:
        for suscriptor in self._suscriptores:
            suscriptor(evento)


class DestinoEPP(NamedTuple):
    """Dónde deja el módulo lo que produce: la base del tenant, sus evidencias y la UI."""

    conectar: Callable[[], sqlite3.Connection]
    carpeta_snapshots: Path
    publicador: PublicadorEventosPort


def crear_evaluador_epp(
    destino: DestinoEPP,
    reglas: ReglasEPP,
    version_modelo: str,
    reloj: RelojPort,
    parametros: ParametrosEPP = PARAMETROS_DECIDIDOS,
) -> EvaluarCumplimiento:
    """Caso de uso listo para el pipeline, con la tabla de infracciones creada si faltaba."""
    crear_tabla_infracciones(destino.conectar)
    ventana = ConfiguracionVentana(
        parametros.fraccion_ausente_minima,
        parametros.tiempo_confirmacion,
        parametros.presentes_para_recuperar,
        parametros.tiempo_limpieza,
    )
    return EvaluarCumplimiento(
        ConfiguracionAsociacion(parametros.ioa_minimo_ancla, parametros.ioa_minimo_epp),
        reglas,
        VentanaTemporal(ventana, reloj),
        GestorInfracciones(parametros.enfriamiento, version_modelo, reloj),
        PuertosCumplimiento(
            RepositorioInfraccionesSQLite(destino.conectar),
            AlmacenEvidenciasCv2(destino.carpeta_snapshots),
            destino.publicador,
        ),
    )
