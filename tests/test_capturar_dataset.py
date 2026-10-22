"""Núcleo de la captura del dataset: muestreo, duplicados, turnos y nombres (SPEC/9 §2.4)."""

from datetime import datetime, timedelta

import numpy as np
import pytest

from ml.contrato_datos import NOMBRE_DE_ARCHIVO
from tools.capturar_dataset import (
    BITS_DE_HUELLA,
    CapturaInvalidaError,
    FiltroDeDuplicados,
    Fotograma,
    TablaDeTurnos,
    dhash,
    distancia_hamming,
    muestrear,
    nombre_de_archivo,
)

INICIO = datetime(2026, 10, 21, 8, 30, 5)
TODOS_LOS_BITS = 2**BITS_DE_HUELLA - 1
BITS_QUE_CAMBIA_EL_RUIDO = 2


def _gradiente_creciente() -> np.ndarray:
    fila = np.linspace(0, 255, 90, dtype=np.uint8)
    return np.repeat(np.tile(fila, (80, 1))[:, :, np.newaxis], 3, axis=2)


def test_dhash_de_un_gradiente_creciente_tiene_todos_los_bits_en_uno() -> None:
    assert dhash(_gradiente_creciente()) == TODOS_LOS_BITS


def test_dhash_de_un_gradiente_decreciente_o_uniforme_es_cero() -> None:
    assert dhash(_gradiente_creciente()[:, ::-1]) == 0
    assert dhash(np.full((80, 90, 3), 128, dtype=np.uint8)) == 0


def test_dhash_acepta_imagenes_en_escala_de_grises() -> None:
    assert dhash(_gradiente_creciente()[:, :, 0]) == TODOS_LOS_BITS


def test_dhash_es_estable_ante_ruido_leve() -> None:
    generador = np.random.default_rng(7)
    ruido = generador.integers(-3, 4, size=(80, 90, 3))
    ruidosa = np.clip(_gradiente_creciente().astype(int) + ruido, 0, 255).astype(np.uint8)

    assert distancia_hamming(dhash(ruidosa), TODOS_LOS_BITS) <= BITS_QUE_CAMBIA_EL_RUIDO


@pytest.mark.parametrize(
    ("a", "b", "distancia"),
    [(0, 0, 0), (0b1011, 0b0001, 2), (0, TODOS_LOS_BITS, BITS_DE_HUELLA)],
)
def test_distancia_hamming_cuenta_los_bits_distintos(a: int, b: int, distancia: int) -> None:
    assert distancia_hamming(a, b) == distancia


def test_filtro_de_duplicados_sin_registros_no_ve_duplicados() -> None:
    assert FiltroDeDuplicados(distancia_maxima=5).es_duplicado(0) is False


@pytest.mark.parametrize(("huella", "duplicada"), [(0b11111, True), (0b111111, False)])
def test_filtro_de_duplicados_compara_contra_la_distancia_maxima(
    huella: int, duplicada: bool
) -> None:
    filtro = FiltroDeDuplicados(distancia_maxima=5)
    filtro.registrar(0)

    assert filtro.es_duplicado(huella) is duplicada


def test_filtro_de_duplicados_compara_contra_todas_las_huellas_registradas() -> None:
    filtro = FiltroDeDuplicados(distancia_maxima=0)
    filtro.registrar(0)
    filtro.registrar(TODOS_LOS_BITS)

    assert filtro.es_duplicado(0) is True
    assert filtro.es_duplicado(TODOS_LOS_BITS) is True


@pytest.mark.parametrize("distancia", [-1, BITS_DE_HUELLA + 1])
def test_filtro_de_duplicados_rechaza_distancias_imposibles(distancia: int) -> None:
    with pytest.raises(CapturaInvalidaError, match="entre 0 y 64"):
        FiltroDeDuplicados(distancia_maxima=distancia)


def _fotogramas(*segundos: float) -> list[Fotograma]:
    imagen = np.zeros((2, 2, 3), dtype=np.uint8)
    return [Fotograma(INICIO + timedelta(seconds=segundo), imagen) for segundo in segundos]


def _segundos(fotogramas: list[Fotograma]) -> list[float]:
    return [(fotograma.momento - INICIO).total_seconds() for fotograma in fotogramas]


def test_muestrear_toma_un_fotograma_cada_intervalo() -> None:
    fotogramas = _fotogramas(*(indice * 0.25 for indice in range(12)))

    elegidos = list(muestrear(fotogramas, timedelta(seconds=1)))

    assert _segundos(elegidos) == [0.0, 1.0, 2.0]


def test_muestrear_mide_el_intervalo_desde_el_ultimo_elegido() -> None:
    elegidos = list(muestrear(_fotogramas(0, 0.9, 1.5, 2.4, 2.6), timedelta(seconds=1)))

    assert _segundos(elegidos) == [0.0, 1.5, 2.6]


def test_muestrear_sin_fotogramas_no_devuelve_nada() -> None:
    assert list(muestrear([], timedelta(seconds=1))) == []


@pytest.mark.parametrize("segundos", [0, -1])
def test_muestrear_exige_un_intervalo_positivo(segundos: int) -> None:
    with pytest.raises(CapturaInvalidaError, match="intervalo debe ser positivo"):
        list(muestrear(_fotogramas(0), timedelta(seconds=segundos)))


def test_muestrear_falla_si_el_reloj_va_hacia_atras() -> None:
    with pytest.raises(CapturaInvalidaError, match="reloj retrocedió"):
        list(muestrear(_fotogramas(0, 5, 4), timedelta(seconds=1)))


TURNOS = "manana=6-14,tarde=14-22,noche=22-6"


@pytest.mark.parametrize(
    ("hora", "turno"),
    [(6, "manana"), (13, "manana"), (14, "tarde"), (21, "tarde"), (22, "noche"), (0, "noche")],
    ids=["inicio-manana", "fin-manana", "inicio-tarde", "fin-tarde", "inicio-noche", "medianoche"],
)
def test_tabla_de_turnos_asigna_cada_hora_incluso_cruzando_medianoche(
    hora: int, turno: str
) -> None:
    tabla = TablaDeTurnos.desde_texto(TURNOS)

    assert tabla.turno_de(INICIO.replace(hour=hora, minute=59)) == turno


@pytest.mark.parametrize(
    ("texto", "error"),
    [
        ("manana=6-14,tarde=14-22", "sin turno: 0, 1, 2, 3, 4, 5, 22, 23"),
        ("manana=6-15,tarde=14-6", "en más de un turno: 14"),
        ("manana=6-6", "no puede empezar y terminar a la misma hora"),
        ("manana=6-25", "formato <nombre>=<hora>-<hora>"),
        ("manana=25-6", "formato <nombre>=<hora>-<hora>"),
        ("Mañana=0-24", "formato <nombre>=<hora>-<hora>"),
        ("", "formato <nombre>=<hora>-<hora>"),
    ],
    ids=["hueco", "solapado", "vacio", "fin-25", "inicio-25", "nombre-invalido", "texto-vacio"],
)
def test_tabla_de_turnos_rechaza_tablas_que_no_cubren_el_dia_una_vez(
    texto: str, error: str
) -> None:
    with pytest.raises(CapturaInvalidaError, match=error):
        TablaDeTurnos.desde_texto(texto)


def test_tabla_de_turnos_acepta_un_unico_turno_de_todo_el_dia() -> None:
    assert TablaDeTurnos.desde_texto("unico=0-24").turno_de(INICIO) == "unico"


def test_nombre_de_archivo_sigue_el_contrato_de_datos() -> None:
    nombre = nombre_de_archivo("cam-01", INICIO, 1)

    assert nombre == "cam-01_20261021_083005_0001.jpg"
    assert NOMBRE_DE_ARCHIVO.fullmatch(nombre)


@pytest.mark.parametrize("camara", ["", "Cam-01", "cam 01", "cam_01", "192.168.0.10"])
def test_nombre_de_archivo_rechaza_identificadores_de_camara_invalidos(camara: str) -> None:
    with pytest.raises(CapturaInvalidaError, match="identificador corto"):
        nombre_de_archivo(camara, INICIO, 1)


@pytest.mark.parametrize("secuencia", [0, 10_000])
def test_nombre_de_archivo_exige_una_secuencia_de_cuatro_cifras(secuencia: int) -> None:
    with pytest.raises(CapturaInvalidaError, match="entre 1 y 9999"):
        nombre_de_archivo("cam-01", INICIO, secuencia)
