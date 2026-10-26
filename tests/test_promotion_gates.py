"""Puertas de promoción del modelo EPP que fallan cerradas (SPEC/9 §3.4; mle-workflow)."""

import dataclasses

import pytest

from ml.promotion_gates import (
    PUERTAS_DE_PROMOCION,
    Direccion,
    PromocionRechazadaError,
    Puerta,
    evaluar_promocion,
    exigir_promocion,
)

RECALL = Puerta("recall_evento_casco", Direccion.MINIMO, 0.9, "D4", "recall de casco")
ALARMAS = Puerta("falsas_alarmas_por_hora", Direccion.MAXIMO, 2.0, "D4", "falsas alarmas")
DEFINIDAS = (RECALL, ALARMAS)
BUENAS = {"recall_evento_casco": 0.95, "falsas_alarmas_por_hora": 1.0}


def test_las_puertas_del_plan_existen() -> None:
    assert [
        (puerta.metrica, puerta.direccion, puerta.decision) for puerta in PUERTAS_DE_PROMOCION
    ] == [
        ("recall_evento_casco", Direccion.MINIMO, "D4"),
        ("recall_evento_chaleco", Direccion.MINIMO, "D4"),
        ("falsas_alarmas_por_hora", Direccion.MAXIMO, "D4"),
        ("fps_por_camara_hardware_objetivo", Direccion.MINIMO, "D2"),
        ("recall_persona_vs_baseline", Direccion.MINIMO, "D4"),
    ]


def test_los_umbrales_son_los_que_decidio_el_negocio() -> None:
    # D4 (24/10/2026): evitar falsas alarmas; 90 % de recall por evento y como mucho una falsa
    # alarma por cámara y por hora; personas no peor que el modelo actual (AC-004).
    # D2: CPU Intel con OpenVINO, 5 FPS por cámara como mínimo.
    assert {puerta.metrica: puerta.umbral for puerta in PUERTAS_DE_PROMOCION} == {
        "recall_evento_casco": 0.90,
        "recall_evento_chaleco": 0.90,
        "falsas_alarmas_por_hora": 1.0,
        "fps_por_camara_hardware_objetivo": 5.0,
        "recall_persona_vs_baseline": 0.0,
    }


def test_cada_puerta_explica_que_mide() -> None:
    assert [puerta.descripcion for puerta in PUERTAS_DE_PROMOCION] == [
        "recall de infracciones de casco a nivel evento",
        "recall de infracciones de chaleco a nivel evento",
        "falsas alarmas por cámara y por hora en los videos dorados",
        "FPS por cámara con N cámaras en el hardware del piloto",
        "recall de persona menos el del modelo de producción",
    ]


def test_la_direccion_se_escribe_como_en_el_plan() -> None:
    assert (Direccion("min"), Direccion("max")) == (Direccion.MINIMO, Direccion.MAXIMO)


def test_sin_umbrales_ningun_modelo_se_promueve_aunque_sus_metricas_sean_perfectas() -> None:
    perfectas = {puerta.metrica: 1.0 for puerta in PUERTAS_DE_PROMOCION}
    sin_umbral = [dataclasses.replace(puerta, umbral=None) for puerta in PUERTAS_DE_PROMOCION]

    motivos = evaluar_promocion(perfectas, sin_umbral)

    assert motivos[0] == (
        'Puerta "recall_evento_casco" (recall de infracciones de casco a nivel evento) sin '
        "umbral: PENDIENTE (D4). Ningún modelo se promueve sin umbrales fijados antes de entrenar."
    )
    assert len(motivos) == len(PUERTAS_DE_PROMOCION)
    assert "PENDIENTE (D2)" in motivos[3]


def test_un_modelo_que_cumple_todas_las_puertas_se_promueve() -> None:
    assert evaluar_promocion(BUENAS, DEFINIDAS) == []


def test_un_modelo_exactamente_en_el_umbral_se_promueve() -> None:
    en_el_borde = {"recall_evento_casco": 0.9, "falsas_alarmas_por_hora": 2.0}

    assert evaluar_promocion(en_el_borde, DEFINIDAS) == []


@pytest.mark.parametrize(
    ("metricas", "motivo"),
    [
        (
            {**BUENAS, "recall_evento_casco": 0.89},
            '"recall_evento_casco" = 0.89 está por debajo del mínimo 0.9.',
        ),
        (
            {**BUENAS, "falsas_alarmas_por_hora": 2.01},
            '"falsas_alarmas_por_hora" = 2.01 está por encima del máximo 2.0.',
        ),
        ({"falsas_alarmas_por_hora": 1.0}, 'Falta la métrica "recall_evento_casco".'),
        (
            {**BUENAS, "recall_evento_casco": float("nan")},
            'La métrica "recall_evento_casco" no es un número finito (nan).',
        ),
        (
            {**BUENAS, "falsas_alarmas_por_hora": float("-inf")},
            'La métrica "falsas_alarmas_por_hora" no es un número finito (-inf).',
        ),
    ],
    ids=["bajo-el-minimo", "sobre-el-maximo", "falta", "nan", "infinito"],
)
def test_cada_incumplimiento_tiene_su_motivo(metricas: dict[str, float], motivo: str) -> None:
    assert evaluar_promocion(metricas, DEFINIDAS) == [motivo]


def test_las_metricas_que_no_son_puertas_no_cuentan() -> None:
    assert evaluar_promocion({**BUENAS, "map50_casco": 0.1}, DEFINIDAS) == []


def test_exigir_promocion_falla_con_todos_los_motivos() -> None:
    malas = {"recall_evento_casco": 0.1, "falsas_alarmas_por_hora": 9.0}

    with pytest.raises(PromocionRechazadaError) as error:
        exigir_promocion(malas, DEFINIDAS)

    assert error.value.motivos == evaluar_promocion(malas, DEFINIDAS)
    assert str(error.value) == "El modelo no se promueve:\n" + "\n".join(error.value.motivos)


def test_exigir_promocion_no_falla_si_todo_se_cumple() -> None:
    exigir_promocion(BUENAS, DEFINIDAS)


def test_exigir_promocion_usa_las_puertas_del_plan_por_omision() -> None:
    lento = {puerta.metrica: 1.0 for puerta in PUERTAS_DE_PROMOCION}

    with pytest.raises(PromocionRechazadaError, match="fps_por_camara_hardware_objetivo"):
        exigir_promocion(lento)


def test_un_modelo_justo_en_los_umbrales_decididos_se_promueve() -> None:
    en_el_borde = {
        "recall_evento_casco": 0.90,
        "recall_evento_chaleco": 0.90,
        "falsas_alarmas_por_hora": 1.0,
        "fps_por_camara_hardware_objetivo": 5.0,
        "recall_persona_vs_baseline": 0.0,
    }

    assert evaluar_promocion(en_el_borde) == []


def test_una_puerta_es_inmutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        RECALL.umbral = 0.0
