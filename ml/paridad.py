"""Paridad entre el modelo entrenado (PyTorch) y su ONNX exportado (SPEC/9 §3.6, B-06).

Sobre un conjunto fijo de imágenes ya preprocesadas (NCHW float32), cada salida del ONNX debe
cumplir |onnx - referencia| <= TOLERANCIA_ABSOLUTA + TOLERANCIA_RELATIVA · |referencia|, elemento
a elemento (la regla de numpy.allclose con la referencia como base).

La tolerancia se fija aquí ANTES de la primera corrida y no se amplía para que una exportación
pase (§14.3 de CLAUDE.md). Los valores son los del tutorial oficial de PyTorch para verificar una
exportación a ONNX Runtime (rtol 1e-3, atol 1e-5): cubren las diferencias de redondeo de float32
entre dos runtimes y detectan un grafo mal exportado. Cambiarlos exige un PR propio con la causa.
"""

from collections.abc import Sequence
from typing import Any, NamedTuple, Protocol

import numpy as np

TOLERANCIA_RELATIVA = 1e-3
TOLERANCIA_ABSOLUTA = 1e-5


class ParidadInvalidaError(ValueError):
    """El ONNX no reproduce al modelo entrenado, o la comparación no se puede hacer."""


class ReferenciaPort(Protocol):
    """El modelo entrenado: salidas crudas (cajas y logits) para un tensor de entrada."""

    def salidas(self, entrada: np.ndarray) -> Sequence[np.ndarray]: ...


class ComparacionDeSalida(NamedTuple):
    imagen: int
    salida: str
    diferencia_maxima: float
    dentro: bool


def comparar_paridad(
    referencia: ReferenciaPort, sesion: Any, entradas: Sequence[np.ndarray]
) -> list[ComparacionDeSalida]:
    """Una comparación por imagen y por salida; `sesion` es una InferenceSession."""
    if not entradas:
        raise ParidadInvalidaError("La paridad necesita al menos una imagen fija.")
    nombre_entrada = sesion.get_inputs()[0].name
    nombres = [salida.name for salida in sesion.get_outputs()]
    comparaciones = []
    for indice, entrada in enumerate(entradas):
        esperadas = list(referencia.salidas(entrada))
        obtenidas = sesion.run(None, {nombre_entrada: entrada})
        if len(esperadas) != len(obtenidas):
            raise ParidadInvalidaError(
                f"Imagen {indice}: el modelo entrenado devolvió {len(esperadas)} salidas y el "
                f"ONNX {len(obtenidas)}."
            )
        for nombre, esperada, obtenida in zip(nombres, esperadas, obtenidas, strict=True):
            comparaciones.append(_comparar(indice, nombre, esperada, obtenida))
    return comparaciones


def _comparar(
    indice: int, nombre: str, esperada: np.ndarray, obtenida: np.ndarray
) -> ComparacionDeSalida:
    if esperada.shape != obtenida.shape:
        raise ParidadInvalidaError(
            f'Imagen {indice}, salida "{nombre}": forma {esperada.shape} en el modelo entrenado '
            f"y {obtenida.shape} en el ONNX."
        )
    diferencia = np.abs(obtenida.astype(np.float64) - esperada.astype(np.float64))
    limite = TOLERANCIA_ABSOLUTA + TOLERANCIA_RELATIVA * np.abs(esperada.astype(np.float64))
    dentro = bool(np.all(diferencia <= limite))
    return ComparacionDeSalida(indice, nombre, float(np.max(diferencia)), dentro)


def exigir_paridad(referencia: ReferenciaPort, sesion: Any, entradas: Sequence[np.ndarray]) -> None:
    fuera = [
        f'Imagen {comparacion.imagen}, salida "{comparacion.salida}": diferencia máxima '
        f"{comparacion.diferencia_maxima:.6g}."
        for comparacion in comparar_paridad(referencia, sesion, entradas)
        if not comparacion.dentro
    ]
    if fuera:
        raise ParidadInvalidaError(
            "\n".join(
                [
                    f"El ONNX no reproduce al modelo entrenado (tolerancia relativa "
                    f"{TOLERANCIA_RELATIVA}, absoluta {TOLERANCIA_ABSOLUTA}; no se amplía para "
                    "que pase, SPEC/9 §3.6):",
                    *fuera,
                ]
            )
        )
