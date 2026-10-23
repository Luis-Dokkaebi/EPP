"""Bandeja de salida de avisos sobre la tabla ppe_infracciones (SPEC/9 §7.1, §7.4; C-09).

La infracción se guarda primero como PENDIENTE (C-05); esta bandeja la entrega al despachador y
registra el resultado. Como vive en la base, los avisos sobreviven a cortes de red y reinicios.

Migración aditiva (skill migration): `agregar_columna_proximo_intento` agrega la columna con la
hora del próximo reintento y es idempotente. La reversión, `quitar_columna_proximo_intento`,
quita solo esa columna (SQLite 3.35 o posterior) y conserva las infracciones. Las horas se
guardan en UTC con formato fijo, así el orden del texto es el orden del tiempo. Toda consulta
es parametrizada (§9).
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from typing import Any

from src.alerts.domain.aviso import Aviso, EstadoNotificacion

_COLUMNA = "proximo_intento"
_AGREGAR_COLUMNA = "ALTER TABLE ppe_infracciones ADD COLUMN proximo_intento TEXT"
_QUITAR_COLUMNA = "ALTER TABLE ppe_infracciones DROP COLUMN proximo_intento"
_COLUMNAS = "SELECT name FROM pragma_table_info('ppe_infracciones')"
_PENDIENTES = (
    "SELECT id, employee_name, elemento, zona, inicio, evidencia_path, intentos_notificacion "
    "FROM ppe_infracciones WHERE estado_notificacion = ? "
    "AND (proximo_intento IS NULL OR proximo_intento <= ?) ORDER BY id"
)
_MARCAR_FALLIDA = (
    "UPDATE ppe_infracciones SET estado_notificacion = ?, intentos_notificacion = ?, "
    "proximo_intento = NULL WHERE id = ? AND estado_notificacion = ?"
)
_MARCAR_ENVIADA = (
    "UPDATE ppe_infracciones SET estado_notificacion = ?, proximo_intento = NULL "
    "WHERE id = ? AND estado_notificacion = ?"
)
_REPROGRAMAR = (
    "UPDATE ppe_infracciones SET intentos_notificacion = ?, proximo_intento = ? "
    "WHERE id = ? AND estado_notificacion = ?"
)
_FORMATO_UTC = "%Y-%m-%dT%H:%M:%S.%f+00:00"
_PENDIENTE = EstadoNotificacion.PENDIENTE.value


class AvisoNoPendienteError(LookupError):
    """Se quiso cambiar un aviso que no existe o que ya salió de PENDIENTE."""


def agregar_columna_proximo_intento(conectar: Callable[[], sqlite3.Connection]) -> None:
    """Agrega la columna si falta (paso "expandir"; idempotente)."""
    if _COLUMNA not in _columnas(conectar):
        _ejecutar(conectar, _AGREGAR_COLUMNA, ())


def quitar_columna_proximo_intento(conectar: Callable[[], sqlite3.Connection]) -> None:
    """Revierte la migración: quita la columna y conserva las infracciones (idempotente)."""
    if _COLUMNA in _columnas(conectar):
        _ejecutar(conectar, _QUITAR_COLUMNA, ())


class BandejaAvisosSQLite:
    """Implementa BandejaSalidaPort sobre la base SQLite del tenant."""

    def __init__(self, conectar: Callable[[], sqlite3.Connection]) -> None:
        self._conectar = conectar

    def pendientes(self, ahora: datetime) -> list[Aviso]:
        with closing(self._conectar()) as conexion:
            filas = conexion.execute(_PENDIENTES, (_PENDIENTE, _en_utc(ahora))).fetchall()
        return [_aviso(fila) for fila in filas]

    def marcar_enviada(self, id_aviso: int) -> None:
        enviada = EstadoNotificacion.ENVIADA.value
        self._cambiar(id_aviso, _MARCAR_ENVIADA, (enviada, id_aviso, _PENDIENTE))

    def reprogramar(self, id_aviso: int, intentos: int, proximo_intento: datetime) -> None:
        parametros = (intentos, _en_utc(proximo_intento), id_aviso, _PENDIENTE)
        self._cambiar(id_aviso, _REPROGRAMAR, parametros)

    def marcar_fallida(self, id_aviso: int, intentos: int) -> None:
        fallida = EstadoNotificacion.FALLIDA.value
        self._cambiar(id_aviso, _MARCAR_FALLIDA, (fallida, intentos, id_aviso, _PENDIENTE))

    def _cambiar(self, id_aviso: int, sql: str, parametros: tuple[object, ...]) -> None:
        if _ejecutar(self._conectar, sql, parametros) != 1:
            raise AvisoNoPendienteError(f"El aviso {id_aviso} no existe o no está pendiente")


def _aviso(fila: tuple[Any, ...]) -> Aviso:
    id_aviso, persona, elemento, zona, inicio, evidencia, intentos = fila
    return Aviso(
        id_aviso, persona, elemento, zona, datetime.fromisoformat(inicio), evidencia, intentos
    )


def _en_utc(instante: datetime) -> str:
    """Texto ordenable en UTC; una hora sin huso horario es ambigua y se rechaza."""
    if instante.tzinfo is None:
        raise ValueError(f"La hora debe tener huso horario: {instante.isoformat()}")
    return instante.astimezone(UTC).strftime(_FORMATO_UTC)


def _columnas(conectar: Callable[[], sqlite3.Connection]) -> set[str]:
    with closing(conectar()) as conexion:
        return {nombre for (nombre,) in conexion.execute(_COLUMNAS)}


def _ejecutar(
    conectar: Callable[[], sqlite3.Connection], sql: str, parametros: tuple[object, ...]
) -> int:
    """Ejecuta una sentencia en su propia transacción y devuelve las filas afectadas."""
    with closing(conectar()) as conexion, conexion:
        return conexion.execute(sql, parametros).rowcount
