"""Puertas de promoción del modelo EPP: fallan cerradas (SPEC/9 §3.4; mle-workflow).

Los umbrales se fijan ANTES de entrenar, con los valores que decide el negocio (D4: presupuesto
de errores; D2: hardware objetivo); los de esta tabla son los del 24/10/2026. Una puerta con
umbral `None` sigue sin promover ningún modelo: así nadie promueve sin umbrales acordados.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Direccion(StrEnum):
    MINIMO = "min"
    MAXIMO = "max"


@dataclass(frozen=True)
class Puerta:
    metrica: str
    direccion: Direccion
    umbral: float | None
    decision: str
    descripcion: str


PUERTAS_DE_PROMOCION = (
    Puerta(
        "recall_evento_casco",
        Direccion.MINIMO,
        0.90,
        "D4",
        "recall de infracciones de casco a nivel evento",
    ),
    Puerta(
        "recall_evento_chaleco",
        Direccion.MINIMO,
        0.90,
        "D4",
        "recall de infracciones de chaleco a nivel evento",
    ),
    Puerta(
        "falsas_alarmas_por_hora",
        Direccion.MAXIMO,
        1.0,
        "D4",
        "falsas alarmas por cámara y por hora en los videos dorados",
    ),
    Puerta(
        "fps_por_camara_hardware_objetivo",
        Direccion.MINIMO,
        5.0,
        "D2",
        "FPS por cámara con N cámaras en el hardware del piloto",
    ),
    Puerta(
        "recall_persona_vs_baseline",
        Direccion.MINIMO,
        0.0,
        "D4",
        "recall de persona menos el del modelo de producción",
    ),
)


class PromocionRechazadaError(Exception):
    """El modelo no cumple las puertas; `motivos` las explica una por una."""

    def __init__(self, motivos: list[str]) -> None:
        self.motivos = motivos
        super().__init__("\n".join(["El modelo no se promueve:", *motivos]))


def evaluar_promocion(
    metricas: Mapping[str, float], puertas: Sequence[Puerta] = PUERTAS_DE_PROMOCION
) -> list[str]:
    """Motivos por los que el modelo no se promueve; la lista vacía significa que se promueve."""
    return [motivo for puerta in puertas for motivo in _motivo(puerta, metricas)]


def exigir_promocion(
    metricas: Mapping[str, float], puertas: Sequence[Puerta] = PUERTAS_DE_PROMOCION
) -> None:
    motivos = evaluar_promocion(metricas, puertas)
    if motivos:
        raise PromocionRechazadaError(motivos)


def _motivo(puerta: Puerta, metricas: Mapping[str, float]) -> list[str]:
    if puerta.umbral is None:
        return [
            f'Puerta "{puerta.metrica}" ({puerta.descripcion}) sin umbral: PENDIENTE '
            f"({puerta.decision}). Ningún modelo se promueve sin umbrales fijados antes de "
            "entrenar."
        ]
    if puerta.metrica not in metricas:
        return [f'Falta la métrica "{puerta.metrica}".']
    valor = metricas[puerta.metrica]
    if not math.isfinite(valor):
        return [f'La métrica "{puerta.metrica}" no es un número finito ({valor}).']
    if puerta.direccion is Direccion.MINIMO and valor < puerta.umbral:
        return [f'"{puerta.metrica}" = {valor} está por debajo del mínimo {puerta.umbral}.']
    if puerta.direccion is Direccion.MAXIMO and valor > puerta.umbral:
        return [f'"{puerta.metrica}" = {valor} está por encima del máximo {puerta.umbral}.']
    return []
