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
from typing import NamedTuple, Protocol

from config import config
from src.composition import clases_declaradas, entrada_del_modelo, leer_manifiesto
from src.inference.types import ClaseObjeto
from src.ppe.application.evaluar_cumplimiento import EvaluarCumplimiento, PuertosCumplimiento
from src.ppe.application.ports import PublicadorEventosPort, RelojPort
from src.ppe.domain.asociacion import ConfiguracionAsociacion
from src.ppe.domain.infracciones import EventoInfraccion, GestorInfracciones
from src.ppe.domain.reglas import ReglasEPP
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from src.tracking.evidencias_epp import AlmacenEvidenciasCv2
from src.tracking.integracion_epp import IntegracionEPP
from src.zones.formato_zonas import leer_zonas

MODULO_EPP = "epp"

# D3: casco y chaleco en la primera iteración; el casco se asocia a la cabeza de cada persona.
CLASES_NECESARIAS = frozenset({ClaseObjeto.CASCO, ClaseObjeto.CHALECO, ClaseObjeto.CABEZA})


def modelo_detecta_epp(clases_del_modelo: frozenset[ClaseObjeto]) -> bool:
    """Un modelo sin estas clases marcaría a todos como infractores: el módulo no se activa."""
    return CLASES_NECESARIAS <= clases_del_modelo


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


class LicenciaPort(Protocol):
    """Lo que el módulo necesita de la licencia DRM (D10)."""

    def incluye_modulo(self, modulo: str) -> bool: ...


def modulo_habilitado(licencia: LicenciaPort | None) -> bool:
    return licencia is not None and licencia.incluye_modulo(MODULO_EPP)


def crear_integracion_epp_de_la_app(
    publicador: PublicadorEventosPort, licencia: LicenciaPort
) -> IntegracionEPP | None:
    """El módulo de EPP de la sucursal abierta, o None si la licencia o el modelo no lo permiten.

    Las zonas se leen al crearlo: un cambio en el editor de zonas rige al reconectar la cámara.
    """
    entrada = entrada_del_modelo(config.MODEL_PATH, leer_manifiesto(config.MANIFEST_PATH))
    if not licencia.incluye_modulo(MODULO_EPP) or not modelo_detecta_epp(
        clases_declaradas(entrada)
    ):
        return None
    ruta_base = config.get_db_path()
    destino = DestinoEPP(
        lambda: sqlite3.connect(ruta_base), Path(config.get_snapshots_dir()), publicador
    )
    reglas = ReglasEPP(frozenset(), leer_zonas(Path(config.get_zonas_file())))
    evaluador = crear_evaluador_epp(destino, reglas, entrada["version"], RelojSistema())
    return IntegracionEPP(evaluador, PARAMETROS_DECIDIDOS.cada_n_frames)
