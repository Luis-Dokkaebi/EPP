"""Replay de regresión sin cámara ni modelo (SPEC/9 §0.10 y §5.5, C-07).

Corre el TrackingPipeline (ByteTrack + zonas) y el caso de uso de EPP sobre detecciones
pregrabadas y escribe cada evento de infracción en JSON Lines, para compararlo con eventos dorados
(*.expected.jsonl revisados por una persona). No usa video: la "evidencia" es el número de frame.
Los clips reales dependen del modelo EPP (B-06).

Entradas:
  detecciones.jsonl  un frame por línea: {"t": segundos, "detecciones": [{"clase", "confianza",
                     "caja": [x1, y1, x2, y2]}]}
  zonas.json         archivo de zonas v1 o v2 (SPEC/9 §6.3)
  configuracion.json los umbrales de CLAVES, sin valores por omisión (los fija el negocio, D4)

Uso: python -m tools.replay detecciones.jsonl zonas.json configuracion.json eventos.jsonl
"""

import json
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.analysis.state_manager import StateManager
from src.inference.types import Caja, ClaseObjeto, Deteccion
from src.ppe.application.evaluar_cumplimiento import EvaluarCumplimiento, PuertosCumplimiento
from src.ppe.domain.asociacion import ConfiguracionAsociacion
from src.ppe.domain.elementos import elementos_desde_textos
from src.ppe.domain.geometria import Caja as CajaDominio
from src.ppe.domain.infracciones import (
    EventoInfraccion,
    GestorInfracciones,
    InfraccionFinalizada,
    InfraccionIniciada,
)
from src.ppe.domain.reglas import ReglasEPP, ReglaZona
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from src.storage.database_manager import DatabaseManager
from src.tracking.integracion_epp import IntegracionEPP, personas_en_escena
from src.tracking.person_tracker import PersonTracker, separar_personas_y_celulares
from src.tracking.tracking_pipeline import TrackingPipeline
from src.zones.formato_zonas import leer_zonas
from src.zones.zone_checker import ZoneChecker

CLAVES = (
    "ioa_minimo_ancla",
    "ioa_minimo_epp",
    "fraccion_ausente_minima",
    "tiempo_confirmacion_s",
    "presentes_para_recuperar",
    "tiempo_limpieza_s",
    "enfriamiento_s",
    "version_modelo",
    "epp_global",
    "cada_n_frames",
)
# Instante del t=0 del clip; los eventos se emiten en segundos relativos a él.
ORIGEN = datetime.fromtimestamp(0, UTC)


class ConfiguracionReplayError(ValueError):
    """Falta un umbral en la configuración del replay."""


class RelojDeReplay:
    """Reloj que sigue el tiempo del clip (t=0 es ORIGEN); se fija antes de cada frame."""

    _ahora: datetime

    def ahora(self) -> datetime:
        return self._ahora

    def fijar(self, segundos: float) -> None:
        self._ahora = ORIGEN + timedelta(seconds=segundos)


class RegistroDeEventos:
    """Repositorio, almacén y publicador del replay: no persiste y anota cada evento publicado.

    ByteTrack (supervision) numera los tracks con un contador global del proceso; para que los
    eventos dorados no dependan de lo que corrió antes, el track_id se renumera por orden de
    aparición en el clip (1, 2, ...).
    """

    def __init__(self) -> None:
        self.lineas: list[str] = []
        self._tracks: dict[int, int] = {}

    def guardar(self, evento: EventoInfraccion) -> None:
        """El replay no persiste: solo compara los eventos publicados."""

    def guardar_evidencia(
        self, imagen: object, caja_persona: CajaDominio, infraccion: InfraccionIniciada
    ) -> str:
        return str(imagen)

    def publicar(self, evento: EventoInfraccion) -> None:
        original = evento.incumplimiento.track_id
        track = self._tracks.setdefault(original, len(self._tracks) + 1)
        self.lineas.append(json.dumps(_como_dict(evento, track), ensure_ascii=False))


def main(argv: list[str]) -> int:
    detecciones, zonas, ruta_configuracion, salida = (Path(argumento) for argumento in argv)
    configuracion = _leer_configuracion(ruta_configuracion)
    reloj, registro = RelojDeReplay(), RegistroDeEventos()
    evaluador = _evaluador(configuracion, leer_zonas(zonas), reloj, registro)
    integracion = IntegracionEPP(evaluador, configuracion["cada_n_frames"])
    with tempfile.TemporaryDirectory() as carpeta:
        pipeline = _pipeline(Path(carpeta), zonas)
        for numero, (segundos, frame) in enumerate(_frames(detecciones)):
            reloj.fijar(segundos)
            imagen = f"frame-{numero}"
            personas, celulares = separar_personas_y_celulares(frame)
            track_data = pipeline.process(imagen, personas, celulares, current_time=segundos)
            integracion.evaluar(imagen, personas_en_escena(track_data), frame)
    salida.write_text("".join(f"{linea}\n" for linea in registro.lineas), encoding="utf-8")
    return 0


def _leer_configuracion(ruta: Path) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    for clave in CLAVES:
        if clave not in datos:
            raise ConfiguracionReplayError(
                f"Falta {clave} en la configuración: los umbrales no tienen valor por omisión (D4)"
            )
    return datos


def _evaluador(
    configuracion: dict[str, Any],
    zonas: tuple[ReglaZona, ...],
    reloj: RelojDeReplay,
    registro: RegistroDeEventos,
) -> EvaluarCumplimiento:
    ventana = ConfiguracionVentana(
        configuracion["fraccion_ausente_minima"],
        timedelta(seconds=configuracion["tiempo_confirmacion_s"]),
        configuracion["presentes_para_recuperar"],
        timedelta(seconds=configuracion["tiempo_limpieza_s"]),
    )
    enfriamiento = timedelta(seconds=configuracion["enfriamiento_s"])
    return EvaluarCumplimiento(
        ConfiguracionAsociacion(configuracion["ioa_minimo_ancla"], configuracion["ioa_minimo_epp"]),
        ReglasEPP(elementos_desde_textos(configuracion["epp_global"]), zonas),
        VentanaTemporal(ventana, reloj),
        GestorInfracciones(enfriamiento, configuracion["version_modelo"], reloj),
        PuertosCumplimiento(registro, registro, registro),
    )


def _pipeline(carpeta: Path, zonas: Path) -> TrackingPipeline:
    """Pipeline real con una base temporal: el replay no toca los datos del tenant."""
    base = DatabaseManager(db_path=str(carpeta / "replay.db"))
    return TrackingPipeline(
        db=base,
        zone_checker=ZoneChecker(zones_path=str(zonas)),
        tracker=PersonTracker(),
        state_manager=StateManager(base),
    )


def _frames(ruta: Path) -> Iterator[tuple[float, list[Deteccion]]]:
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        frame = json.loads(linea)
        yield float(frame["t"]), [_deteccion(dato) for dato in frame["detecciones"]]


def _deteccion(dato: dict[str, Any]) -> Deteccion:
    return Deteccion(ClaseObjeto(dato["clase"]), dato["confianza"], Caja(*dato["caja"]))


def _como_dict(evento: EventoInfraccion, track: int) -> dict[str, object]:
    incumplimiento = evento.incumplimiento
    comun = {
        "track_id": track,
        "nombre": incumplimiento.nombre,
        "elemento": incumplimiento.elemento.value,
        "zona": incumplimiento.zona,
        "version_modelo": evento.version_modelo,
    }
    if isinstance(evento, InfraccionFinalizada):
        fin = {"inicio": _segundos(evento.inicio), "duracion_s": evento.duracion.total_seconds()}
        return {"evento": "fin", "t": _segundos(evento.fin), **comun, **fin}
    evidencia = evento.evidencia if isinstance(evento, InfraccionIniciada) else None
    return {"evento": "inicio", "t": _segundos(evento.inicio), **comun, "evidencia": evidencia}


def _segundos(instante: datetime) -> float:
    return (instante - ORIGEN).total_seconds()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
