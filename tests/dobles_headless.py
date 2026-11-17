"""Dobles del modo sin interfaz (`src/main.py`): cámara, pipeline, estados, licencia y avisos."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np

from src.security.vigencia_licencia import MotivoDeRechazo

VERDE = (0, 255, 0)


class CapturaFalsa:
    def __init__(self, frames: list[np.ndarray], abierta: bool = True) -> None:
        self._frames = frames
        self._abierta = abierta
        self.liberada = False

    def isOpened(self) -> bool:  # noqa: N802 - interfaz de cv2.VideoCapture
        return self._abierta

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.liberada = True


@dataclass
class PipelineFalso:
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)

    def __init__(self, pistas: list[dict[str, Any]], **colaboradores: Any) -> None:
        self.colaboradores = colaboradores
        self.llamadas = []
        self.opciones: list[dict[str, Any]] = []
        self._pistas = pistas

    def process(self, *argumentos: Any, **opciones: Any) -> list[dict[str, Any]]:
        self.llamadas.append(argumentos)
        self.opciones.append(opciones)
        return self._pistas


class EstadosFalsos:
    """StateManager falso: todos trabajan y se pintan de verde; anota por quién se preguntó."""

    def __init__(self) -> None:
        self.consultados: list[str] = []

    def get_state(self, nombre: str) -> str:
        self.consultados.append(nombre)
        return "Trabajando"

    def get_color_for_state(self, _estado: str) -> tuple[int, int, int]:
        return VERDE


class LicenciaFalsa:
    """Doble de la licencia DRM; `vigencias` es lo que responde cada validación, en orden."""

    def __init__(self, *modulos: str, vigencias: tuple[bool, ...] = ()) -> None:
        self._modulos = modulos
        self._vigencias = list(vigencias)
        self.motivo_de_rechazo: MotivoDeRechazo | None = None

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo in self._modulos

    def validate_license(self) -> bool:
        vigente = self._vigencias.pop(0) if self._vigencias else False
        self.motivo_de_rechazo = None if vigente else MotivoDeRechazo.VENCIDA
        return vigente


class DespachadorFalso:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def iniciar(self) -> None:
        self.eventos.append("iniciar")

    def detener(self, espera_maxima: timedelta) -> None:
        self.eventos.append(f"detener {espera_maxima.total_seconds():.0f} s")


@dataclass
class Corrida:
    pipelines: list[PipelineFalso]
    capturas: list[CapturaFalsa]
    ventanas_cerradas: list[bool]
    despachador: DespachadorFalso = field(default_factory=DespachadorFalso)
    mostrados: list[Any] = field(default_factory=list)
    ventanas: list[str] = field(default_factory=list)
    esperas_ms: list[int] = field(default_factory=list)
    fuentes: list[object] = field(default_factory=list)
    estados: "EstadosFalsos" = field(default_factory=lambda: EstadosFalsos())

    def llamadas(self) -> list[tuple[Any, ...]]:
        [pipeline] = self.pipelines
        return pipeline.llamadas
