"""Resumen de cumplimiento de EPP para el reporte (SPEC/9 §8.4).

Por turno, empleado, zona y elemento: cantidad de infracciones, duración total y porcentaje del
tiempo en cumplimiento. El porcentaje necesita el tiempo que la persona pasó en la zona; si no
se conoce, el reporte dice "sin datos" (None) en vez de inventarlo.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.analysis.cumplimiento_epp import (
    SIN_TURNO,
    FilaCumplimiento,
    InfraccionRegistrada,
    Presencia,
    exposicion_por_zona,
    resumir,
)

INICIO = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
CORTE = datetime(2026, 10, 23, 0, 0, tzinfo=UTC)
MINUTO = timedelta(minutes=1)
TURNOS = {"Ana": "Matutino", "Luis": "Nocturno"}


def _infraccion(
    persona: str | None = "Ana",
    zona: str = "Boca de pozo",
    elemento: str = "casco",
    minutos: int | None = 10,
    desde: datetime = INICIO,
) -> InfraccionRegistrada:
    fin = None if minutos is None else desde + minutos * MINUTO
    return InfraccionRegistrada(persona, zona, elemento, desde, fin)


def test_resumir_agrupa_por_turno_persona_zona_y_elemento() -> None:
    infracciones = [
        _infraccion(minutos=10),
        _infraccion(minutos=5, desde=INICIO + timedelta(hours=1)),
        _infraccion(elemento="chaleco", minutos=2),
        _infraccion(persona="Luis", minutos=1),
    ]

    filas = resumir(infracciones, TURNOS, {}, CORTE)

    assert filas == [
        FilaCumplimiento("Matutino", "Ana", "Boca de pozo", "casco", 2, 15 * MINUTO, None),
        FilaCumplimiento("Matutino", "Ana", "Boca de pozo", "chaleco", 1, 2 * MINUTO, None),
        FilaCumplimiento("Nocturno", "Luis", "Boca de pozo", "casco", 1, MINUTO, None),
    ]


def test_resumir_sin_infracciones_no_tiene_filas() -> None:
    assert resumir([], TURNOS, {}, CORTE) == []


def test_resumir_nombra_a_la_persona_no_identificada_y_a_quien_no_tiene_turno() -> None:
    infracciones = [_infraccion(persona=None), _infraccion(persona="Eva")]

    filas = resumir(infracciones, TURNOS, {}, CORTE)

    assert [(fila.turno, fila.persona) for fila in filas] == [
        (SIN_TURNO, "Eva"),
        (SIN_TURNO, "persona no identificada"),
    ]
    assert SIN_TURNO == "sin turno"


def test_resumir_cuenta_una_infraccion_abierta_hasta_el_corte() -> None:
    abierta = _infraccion(minutos=None, desde=CORTE - 30 * MINUTO)

    (fila,) = resumir([abierta], TURNOS, {}, CORTE)

    assert fila.duracion_total == 30 * MINUTO


def test_resumir_no_cuenta_lo_que_pasa_despues_del_corte() -> None:
    cruza_el_corte = _infraccion(minutos=60, desde=CORTE - 15 * MINUTO)

    (fila,) = resumir([cruza_el_corte], TURNOS, {}, CORTE)

    assert fila.duracion_total == 15 * MINUTO


@pytest.mark.parametrize(
    ("exposicion", "porcentaje"),
    [
        (timedelta(hours=1), 75.0),
        (15 * MINUTO, 0.0),
        (10 * MINUTO, 0.0),
        (timedelta(hours=3), 91.7),
    ],
    ids=["un-cuarto-sin-epp", "todo-sin-epp", "exposicion-menor-que-la-infraccion", "redondeo"],
)
def test_resumir_calcula_el_porcentaje_de_tiempo_en_cumplimiento(
    exposicion: timedelta, porcentaje: float
) -> None:
    infracciones = [_infraccion(minutos=15)]

    (fila,) = resumir(infracciones, TURNOS, {("Ana", "Boca de pozo"): exposicion}, CORTE)

    assert fila.porcentaje_cumplimiento == porcentaje


def test_resumir_sin_tiempo_expuesto_no_inventa_el_porcentaje() -> None:
    exposicion = {("Ana", "Boca de pozo"): timedelta(0), ("Ana", "Otra"): timedelta(hours=1)}

    (fila,) = resumir([_infraccion()], TURNOS, exposicion, CORTE)

    assert fila.porcentaje_cumplimiento is None


# --- Tiempo de cada persona en cada zona (§5.4): base del porcentaje de cumplimiento ---

SEGUNDO = timedelta(seconds=1)
CINCO_MINUTOS = 5 * MINUTO


def _presencias(persona: str, zona: str, *pasos: tuple[int, bool]) -> list[Presencia]:
    """Un registro por (segundos desde INICIO, dentro de la zona)."""
    return [Presencia(persona, zona, INICIO + s * SEGUNDO, dentro) for s, dentro in pasos]


def test_la_exposicion_suma_el_tiempo_desde_cada_registro_dentro_hasta_el_siguiente() -> None:
    presencias = _presencias("Ana", "Anden", (0, True), (60, True), (120, False), (180, True))

    assert exposicion_por_zona(presencias) == {("Ana", "Anden"): 2 * MINUTO}


@pytest.mark.parametrize(
    ("hueco", "esperado"), [(300, CINCO_MINUTOS), (301, timedelta(0))], ids=["5_min", "5_min_y_1_s"]
)
def test_un_hueco_de_mas_de_5_minutos_sin_registros_no_cuenta(
    hueco: int, esperado: timedelta
) -> None:
    presencias = _presencias("Ana", "Anden", (0, True), (hueco, True))

    assert exposicion_por_zona(presencias) == {("Ana", "Anden"): esperado}


def test_la_exposicion_es_por_persona_y_zona_y_no_depende_del_orden() -> None:
    presencias = [
        *_presencias("Luis", "Anden", (60, True), (0, True)),
        *_presencias("Ana", "Oficina", (0, True), (30, True)),
    ]

    assert exposicion_por_zona(presencias) == {
        ("Ana", "Oficina"): 30 * SEGUNDO,
        ("Luis", "Anden"): MINUTO,
    }


def test_sin_presencias_no_hay_exposicion() -> None:
    assert exposicion_por_zona([]) == {}
