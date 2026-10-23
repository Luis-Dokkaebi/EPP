"""Captura de frames para el dataset EPP del piloto (SPEC/9 §2.4, B-02).

Muestrea un frame cada N segundos, descarta los casi duplicados con un hash perceptual (dHash) y
nombra cada imagen según el contrato de datos (docs/ml/contrato_datos.md). El procedimiento humano
está en docs/runbooks/captura_dataset.md.
"""

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import cv2
import numpy as np

from ml.contrato_datos import NOMBRE_DE_ARCHIVO

RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[1]
ARCHIVO_DE_METADATOS = "metadatos.jsonl"
BITS_DE_HUELLA = 64
LADO_DE_HUELLA = (9, 8)  # 9 columnas para comparar 8 pares por fila: 8 x 8 = 64 bits
HORAS_DEL_DIA = 24
SECUENCIA_MAXIMA = 9999
DIMENSIONES_GRIS = 2
HORA = r"(?:[01]?\d|2[0-4])"  # 0 a 24
TURNO = re.compile(rf"(?P<nombre>[a-z0-9-]+)=(?P<inicio>{HORA})-(?P<fin>{HORA})")
CREDENCIALES_EN_URL = re.compile(r"//[^/@]+@")
# Propuesta del borrador: dHash a 5 bits o menos de 64 es la misma escena; se ajusta con las
# primeras capturas reales del piloto (docs/runbooks/captura_dataset.md).
DISTANCIA_MAXIMA_PROPUESTA = 5
CODIGO_DE_ERROR = 2


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


class CapturaDeVideo(Protocol):
    """Lo que la captura usa de cv2.VideoCapture."""

    def read(self) -> tuple[bool, Any]: ...

    def get(self, propiedad: int, /) -> float: ...

    def release(self) -> None: ...


def fotogramas_de_archivo(captura: CapturaDeVideo, inicio: datetime) -> Iterator[Fotograma]:
    """Video grabado: cada fotograma se fecha desde `inicio` según los FPS del archivo."""
    fps = captura.get(cv2.CAP_PROP_FPS)
    if not fps > 0:
        raise CapturaInvalidaError(
            f"La fuente no informa sus FPS ({fps}): conviértela a un video con FPS fijos."
        )
    for indice, imagen in enumerate(_imagenes(captura)):
        yield Fotograma(inicio + timedelta(seconds=indice / fps), imagen)


def fotogramas_en_vivo(
    captura: CapturaDeVideo, reloj: Callable[[], datetime]
) -> Iterator[Fotograma]:
    """Cámara en vivo: cada fotograma lleva la hora del reloj; termina si la cámara se corta."""
    for imagen in _imagenes(captura):
        yield Fotograma(reloj(), imagen)


def _imagenes(captura: CapturaDeVideo) -> Iterator[np.ndarray]:
    leida, imagen = captura.read()
    while leida:
        yield imagen
        leida, imagen = captura.read()


@dataclass(frozen=True)
class ConfiguracionDeCaptura:
    """Parámetros de una captura; se validan al crearla (privacidad y custodia, SPEC/9 §2.6)."""

    camara: str
    salida: Path
    autorizacion: str
    retencion_dias: int
    turnos: TablaDeTurnos
    intervalo: timedelta
    distancia_maxima: int
    maximo_de_imagenes: int | None

    def __post_init__(self) -> None:
        if not self.autorizacion.strip():
            raise CapturaInvalidaError(
                "Falta el identificador de la autorización escrita del cliente (SPEC/9 §2.3)."
            )
        if self.retencion_dias <= 0:
            raise CapturaInvalidaError(
                "El plazo de retención debe ser un número positivo de días. El valor lo fija la "
                "decisión PENDIENTE (D5); no hay uno por omisión."
            )
        if self.maximo_de_imagenes is not None and self.maximo_de_imagenes <= 0:
            raise CapturaInvalidaError("El máximo de imágenes debe ser positivo.")
        if self.salida.resolve().is_relative_to(RAIZ_DEL_REPOSITORIO):
            raise CapturaInvalidaError(
                f"{self.salida} está dentro del repositorio: las imágenes nunca van a git. Usa "
                "una carpeta en el almacenamiento cifrado (docs/runbooks/captura_dataset.md)."
            )


class ResumenDeCaptura(NamedTuple):
    guardadas: int
    duplicadas: int


def capturar(
    fotogramas: Iterable[Fotograma], configuracion: ConfiguracionDeCaptura
) -> ResumenDeCaptura:
    """Guarda las imágenes muestreadas y no duplicadas, con una línea de metadatos cada una."""
    filtro = FiltroDeDuplicados(configuracion.distancia_maxima)
    configuracion.salida.mkdir(parents=True, exist_ok=True)
    guardadas = duplicadas = 0
    ruta_metadatos = configuracion.salida / ARCHIVO_DE_METADATOS
    with ruta_metadatos.open("a", encoding="utf-8") as metadatos:
        for fotograma in muestrear(fotogramas, configuracion.intervalo):
            huella = dhash(fotograma.imagen)
            if filtro.es_duplicado(huella):
                duplicadas += 1
                continue
            filtro.registrar(huella)
            guardadas += 1
            registro = _guardar_imagen(fotograma, guardadas, configuracion)
            metadatos.write(json.dumps(registro, ensure_ascii=False) + "\n")
            metadatos.flush()
            if guardadas == configuracion.maximo_de_imagenes:
                break
    return ResumenDeCaptura(guardadas, duplicadas)


def _guardar_imagen(
    fotograma: Fotograma, secuencia: int, configuracion: ConfiguracionDeCaptura
) -> dict[str, Any]:
    momento = fotograma.momento
    nombre = nombre_de_archivo(configuracion.camara, momento, secuencia)
    contenido = _jpeg(fotograma.imagen)
    try:
        with (configuracion.salida / nombre).open("xb") as archivo:
            archivo.write(contenido)
    except FileExistsError as error:
        raise CapturaInvalidaError(
            f"{nombre} ya existe: la captura nunca sobrescribe imágenes."
        ) from error
    alto, ancho = fotograma.imagen.shape[:2]
    borrado = momento.date() + timedelta(days=configuracion.retencion_dias)
    return {
        "file_name": nombre,
        "width": ancho,
        "height": alto,
        "camara": configuracion.camara,
        "fecha": f"{momento:%Y-%m-%d}",
        "hora": f"{momento:%H:%M:%S}",
        "turno": configuracion.turnos.turno_de(momento),
        "autorizacion": configuracion.autorizacion,
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "eliminar_despues_de": borrado.isoformat(),
    }


def _jpeg(imagen: np.ndarray) -> bytes:
    codificada_bien, codificada = cv2.imencode(".jpg", imagen)
    if not codificada_bien:
        raise CapturaInvalidaError("OpenCV no pudo codificar el fotograma como JPEG.")
    return bytes(codificada.tobytes())


def ocultar_credenciales(fuente: str) -> str:
    """Quita de una URL RTSP el usuario y la clave (lo que va entre "//" y "@") para mostrarla."""
    return CREDENCIALES_EN_URL.sub("//***@", fuente)


def abrir_fuente(fuente: str) -> CapturaDeVideo:
    """Un número es el índice de una cámara USB; el resto, un archivo o una URL RTSP."""
    captura = cv2.VideoCapture(int(fuente)) if fuente.isdigit() else cv2.VideoCapture(fuente)
    if not captura.isOpened():
        raise CapturaInvalidaError(f"No se pudo abrir la fuente {ocultar_credenciales(fuente)}.")
    return captura


def _analizar(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", required=True, help="video, URL RTSP o índice de cámara")
    parser.add_argument("--camara", required=True, help="identificador corto: a-z, 0-9 y -")
    parser.add_argument("--salida", required=True, type=Path, help="carpeta cifrada, fuera de git")
    parser.add_argument("--autorizacion", required=True, help="ID de la autorización del cliente")
    parser.add_argument(
        "--retencion-dias", required=True, type=int, help="plazo de borrado (decisión D5)"
    )
    parser.add_argument("--turnos", required=True, help="por ejemplo: manana=6-14,tarde=14-22")
    parser.add_argument("--intervalo-segundos", required=True, type=float)
    parser.add_argument(
        "--distancia-maxima",
        type=int,
        default=DISTANCIA_MAXIMA_PROPUESTA,
        help="casi duplicados a esta distancia dHash o menos (por omisión: %(default)s)",
    )
    parser.add_argument("--maximo", type=int, default=None, help="tope de imágenes guardadas")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--inicio", type=datetime.fromisoformat, help="hora del primer fotograma")
    modo.add_argument("--en-vivo", action="store_true", help="fecha cada fotograma con el reloj")
    return parser.parse_args(argv)


def _configuracion(argumentos: argparse.Namespace) -> ConfiguracionDeCaptura:
    return ConfiguracionDeCaptura(
        camara=argumentos.camara,
        salida=argumentos.salida,
        autorizacion=argumentos.autorizacion,
        retencion_dias=argumentos.retencion_dias,
        turnos=TablaDeTurnos.desde_texto(argumentos.turnos),
        intervalo=timedelta(seconds=argumentos.intervalo_segundos),
        distancia_maxima=argumentos.distancia_maxima,
        maximo_de_imagenes=argumentos.maximo,
    )


def main(
    argv: Sequence[str] | None = None,
    abrir: Callable[[str], CapturaDeVideo] = abrir_fuente,
    reloj: Callable[[], datetime] = datetime.now,
) -> int:
    argumentos = _analizar(argv)
    try:
        configuracion = _configuracion(argumentos)
        captura = abrir(argumentos.fuente)
        try:
            fotogramas = (
                fotogramas_en_vivo(captura, reloj)
                if argumentos.en_vivo
                else fotogramas_de_archivo(captura, argumentos.inicio)
            )
            resumen = capturar(fotogramas, configuracion)
        finally:
            captura.release()
    except CapturaInvalidaError as error:
        sys.stderr.write(f"{error}\n")
        return CODIGO_DE_ERROR
    sys.stdout.write(
        f"Guardadas: {resumen.guardadas}; descartadas por casi duplicadas: "
        f"{resumen.duplicadas}; carpeta: {configuracion.salida}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
