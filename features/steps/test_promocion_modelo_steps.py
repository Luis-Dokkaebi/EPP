"""Pasos de features/promocion_modelo.feature: traducen el texto y llaman a ml.promotion_gates."""

import dataclasses

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ml.promotion_gates import PUERTAS_DE_PROMOCION, Puerta, evaluar_promocion

pytestmark = pytest.mark.bdd

scenarios("../promocion_modelo.feature")

MEDICIONES = {
    "detección de casco": "recall_evento_casco",
    "detección de chaleco": "recall_evento_chaleco",
    "falsas alarmas por hora": "falsas_alarmas_por_hora",
    "velocidad por cámara": "fps_por_camara_hardware_objetivo",
    "detección de personas": "recall_persona_vs_baseline",
}
# Valores de ejemplo para el escenario, no son los de D2 ni D4 (siguen PENDIENTES).
UMBRALES_DE_EJEMPLO = {
    "recall_evento_casco": 0.9,
    "recall_evento_chaleco": 0.9,
    "falsas_alarmas_por_hora": 2.0,
    "fps_por_camara_hardware_objetivo": 10.0,
    "recall_persona_vs_baseline": 0.0,
}
QUE_CUMPLEN = {
    "recall_evento_casco": 0.95,
    "recall_evento_chaleco": 0.97,
    "falsas_alarmas_por_hora": 0.5,
    "fps_por_camara_hardware_objetivo": 12.0,
    "recall_persona_vs_baseline": 0.01,
}
FUERA_DEL_UMBRAL = {
    "recall_evento_casco": 0.8,
    "recall_evento_chaleco": 0.85,
    "falsas_alarmas_por_hora": 3.0,
    "fps_por_camara_hardware_objetivo": 7.5,
    "recall_persona_vs_baseline": -0.02,
}
PERFECTAS = {**QUE_CUMPLEN, "falsas_alarmas_por_hora": 0.0}


@given("que el presupuesto de errores todavía no está decidido", target_fixture="puertas")
def puertas_del_plan() -> tuple[Puerta, ...]:
    return PUERTAS_DE_PROMOCION


@given("umbrales acordados para todas las mediciones", target_fixture="puertas")
def puertas_acordadas() -> tuple[Puerta, ...]:
    return tuple(
        dataclasses.replace(puerta, umbral=UMBRALES_DE_EJEMPLO[puerta.metrica])
        for puerta in PUERTAS_DE_PROMOCION
    )


@when("evalúo un modelo con mediciones perfectas", target_fixture="motivos")
def evaluar_perfecto(puertas: tuple[Puerta, ...]) -> list[str]:
    return evaluar_promocion(PERFECTAS, puertas)


@when("evalúo un modelo que cumple cada umbral", target_fixture="motivos")
def evaluar_bueno(puertas: tuple[Puerta, ...]) -> list[str]:
    return evaluar_promocion(QUE_CUMPLEN, puertas)


@when("evalúo un modelo que queda justo en cada umbral", target_fixture="motivos")
def evaluar_en_el_borde(puertas: tuple[Puerta, ...]) -> list[str]:
    return evaluar_promocion(UMBRALES_DE_EJEMPLO, puertas)


@when(parsers.parse("evalúo un modelo con {medicion} fuera de su umbral"), target_fixture="motivos")
def evaluar_fuera(puertas: tuple[Puerta, ...], medicion: str) -> list[str]:
    metrica = MEDICIONES[medicion]
    return evaluar_promocion({**QUE_CUMPLEN, metrica: FUERA_DEL_UMBRAL[metrica]}, puertas)


@when(
    parsers.parse("evalúo un modelo al que le falta la medición de {medicion}"),
    target_fixture="motivos",
)
def evaluar_incompleto(puertas: tuple[Puerta, ...], medicion: str) -> list[str]:
    incompletas = dict(QUE_CUMPLEN)
    del incompletas[MEDICIONES[medicion]]
    return evaluar_promocion(incompletas, puertas)


@then("el modelo no se promueve")
def no_se_promueve(motivos: list[str]) -> None:
    assert motivos != []


@then("el modelo se promueve")
def se_promueve(motivos: list[str]) -> None:
    assert motivos == []


@then(parsers.parse('el motivo indica que falta la decisión "{decision}"'))
def falta_la_decision(motivos: list[str], decision: str) -> None:
    assert f"PENDIENTE ({decision})" in "\n".join(motivos)


@then(parsers.parse("el motivo nombra la medición {medicion}"))
def nombra_la_medicion(motivos: list[str], medicion: str) -> None:
    assert [motivo for motivo in motivos if MEDICIONES[medicion] in motivo] == motivos
