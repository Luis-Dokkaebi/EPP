"""Captura de frames para el dataset EPP del piloto (SPEC/9 §2.4, B-02).

Muestrea un frame cada N segundos, descarta los casi duplicados con un hash perceptual (dHash) y
nombra cada imagen según el contrato de datos (docs/ml/contrato_datos.md). El procedimiento humano
está en docs/runbooks/captura_dataset.md.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple

import cv2
import numpy as np

from ml.contrato_datos import NOMBRE_DE_ARCHIVO

BITS_DE_HUELLA = 64
LADO_DE_HUELLA = (9, 8)  # 9 columnas para comparar 8 pares por fila: 8 x 8 = 64 bits
HORAS_DEL_DIA = 24
SECUENCIA_MAXIMA = 9999
DIMENSIONES_GRIS = 2
HORA = r"(?:[01]?\d|2[0-4])"  # 0 a 24
TURNO = re.compile(rf"(?P<nombre>[a-z0-9-]+)=(?P<inicio>{HORA})-(?P<fin>{HORA})")


class CapturaInvalidaError(ValueError):
    """Parámetro o fuente de la captura inválidos; el mensaje dice cómo corregirlo."""


class Fotograma(NamedTuple):
    momento: datetime
    imagen: np.ndarray


def dhash(imagen: np.ndarray) -> int:
    """Huella perceptual de 64 bits: cada bit dice si un píxel es más claro que el anterior."""
    en_color = imagen.ndim != DIMENSIONES_GRIS
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if en_color else imagen
    chica = cv2.resize(gris, LADO_DE_HUELLA, interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (chica[:, 1:] > chica[:, :-1]).flatten()
    return int("".join("1" if bit else "0" for bit in bits), 2)


def distancia_hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class FiltroDeDuplicados:
    """Recuerda las huellas guardadas; una huella a distancia <= máxima es un casi duplicado."""

    def __init__(self, distancia_maxima: int) -> None:
        if not 0 <= distancia_maxima <= BITS_DE_HUELLA:
            raise CapturaInvalidaError(
                f"La distancia máxima debe estar entre 0 y {BITS_DE_HUELLA}; "
                f"llegó {distancia_maxima}."
            )
        self._distancia_maxima = distancia_maxima
        self._huellas: list[int] = []

    def es_duplicado(self, huella: int) -> bool:
        return any(
            distancia_hamming(huella, guardada) <= self._distancia_maxima
            for guardada in self._huellas
        )

    def registrar(self, huella: int) -> None:
        self._huellas.append(huella)


def muestrear(fotogramas: Iterable[Fotograma], intervalo: timedelta) -> Iterator[Fotograma]:
    """El primer fotograma y luego cada uno a `intervalo` o más del último elegido."""
    if intervalo <= timedelta(0):
        raise CapturaInvalidaError(f"El intervalo debe ser positivo; llegó {intervalo}.")
    ultimo_visto: datetime | None = None
    ultimo_elegido: datetime | None = None
    for fotograma in fotogramas:
        if ultimo_visto is not None and fotograma.momento < ultimo_visto:
            raise CapturaInvalidaError(
                f"El reloj retrocedió de {ultimo_visto} a {fotograma.momento}: revisa la hora del "
                "equipo de captura."
            )
        ultimo_visto = fotograma.momento
        if ultimo_elegido is None or fotograma.momento - ultimo_elegido >= intervalo:
            ultimo_elegido = fotograma.momento
            yield fotograma


@dataclass(frozen=True)
class TablaDeTurnos:
    """Nombre del turno de cada hora del día (24 entradas, todas cubiertas una sola vez)."""

    turno_por_hora: Mapping[int, str]

    @classmethod
    def desde_texto(cls, texto: str) -> "TablaDeTurnos":
        """Lee "manana=6-14,tarde=14-22,noche=22-6": el fin no se incluye; cruza medianoche."""
        horas: dict[int, list[str]] = {hora: [] for hora in range(HORAS_DEL_DIA)}
        for parte in texto.split(","):
            nombre, inicio, fin = _turno(parte)
            for hora in _horas_entre(inicio, fin):
                horas[hora].append(nombre)
        _validar_cobertura(horas)
        return cls({hora: nombres[0] for hora, nombres in horas.items()})

    def turno_de(self, momento: datetime) -> str:
        return self.turno_por_hora[momento.hour]


def _turno(parte: str) -> tuple[str, int, int]:
    coincidencia = TURNO.fullmatch(parte.strip())
    if coincidencia is None:
        raise CapturaInvalidaError(
            f'Turno "{parte}" inválido: usa el formato <nombre>=<hora>-<hora>, con un nombre en '
            "minúsculas y horas de 0 a 24 (por ejemplo, noche=22-6)."
        )
    inicio, fin = int(coincidencia["inicio"]), int(coincidencia["fin"])
    if inicio % HORAS_DEL_DIA == fin % HORAS_DEL_DIA and (inicio, fin) != (0, HORAS_DEL_DIA):
        raise CapturaInvalidaError(
            f'El turno "{parte}" no puede empezar y terminar a la misma hora.'
        )
    return coincidencia["nombre"], inicio, fin


def _horas_entre(inicio: int, fin: int) -> list[int]:
    duracion = (fin - inicio) % HORAS_DEL_DIA or HORAS_DEL_DIA
    return [(inicio + desplazamiento) % HORAS_DEL_DIA for desplazamiento in range(duracion)]


def _validar_cobertura(horas: Mapping[int, list[str]]) -> None:
    sin_turno = [str(hora) for hora in sorted(horas) if not horas[hora]]
    repetidas = [str(hora) for hora in sorted(horas) if len(horas[hora]) > 1]
    if sin_turno:
        raise CapturaInvalidaError(f"Horas sin turno: {', '.join(sin_turno)}.")
    if repetidas:
        raise CapturaInvalidaError(f"Horas en más de un turno: {', '.join(repetidas)}.")


def nombre_de_archivo(camara: str, momento: datetime, secuencia: int) -> str:
    """<camara>_<AAAAMMDD>_<HHMMSS>_<nnnn>.jpg, validado contra el contrato de datos."""
    if not 1 <= secuencia <= SECUENCIA_MAXIMA:
        raise CapturaInvalidaError(
            f"La secuencia debe estar entre 1 y {SECUENCIA_MAXIMA}; llegó {secuencia}."
        )
    nombre = f"{camara}_{momento:%Y%m%d_%H%M%S}_{secuencia:04d}.jpg"
    if NOMBRE_DE_ARCHIVO.fullmatch(nombre) is None:
        raise CapturaInvalidaError(
            f'Cámara "{camara}" inválida: usa un identificador corto con a-z, 0-9 y guiones, sin '
            "nombres de personas ni direcciones IP."
        )
    return nombre
