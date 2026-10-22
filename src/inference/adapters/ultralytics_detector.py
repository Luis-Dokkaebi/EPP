"""Adaptador temporal de Ultralytics YOLOv8 a DetectorPort (SPEC/9 §1.3.4).

Existe solo durante la migración (fase EXPANDIR): recibe el modelo ya cargado, así este módulo no
importa `ultralytics`, y se elimina al CONTRAER (A-16, decisión D8).
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from src.inference.types import (
    Caja,
    CajaInvalidaError,
    CatalogoDeClases,
    Deteccion,
    validar_confianza,
)

_logger = logging.getLogger(__name__)


class DetectorUltralytics:
    def __init__(
        self,
        modelo: Callable[..., Sequence[Any]],
        catalogo: CatalogoDeClases,
        confianza_minima: float,
    ) -> None:
        validar_confianza(confianza_minima)
        self._modelo = modelo
        self._catalogo = catalogo
        self._confianza_minima = confianza_minima

    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        cajas = self._modelo(frame, verbose=False)[0].boxes
        filas = zip(
            cajas.xyxy.cpu().numpy().tolist(),
            cajas.conf.cpu().numpy().tolist(),
            cajas.cls.cpu().numpy().astype(int).tolist(),
            strict=True,
        )
        detecciones = (
            self._traducir(xyxy, confianza, id_clase) for xyxy, confianza, id_clase in filas
        )
        return [deteccion for deteccion in detecciones if deteccion is not None]

    def _traducir(self, xyxy: list[float], confianza: float, id_clase: int) -> Deteccion | None:
        clase = self._catalogo.clase_de(id_clase)
        if clase is None or confianza < self._confianza_minima:
            return None
        try:
            caja = Caja(*xyxy)
        except CajaInvalidaError as error:
            _logger.debug("Caja degenerada descartada: %s", error)
            return None
        return Deteccion(clase, confianza, caja)
