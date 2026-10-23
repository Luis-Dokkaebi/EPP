"""Consultas del panel "Alertas EPP" y acuse de recibo, sobre ppe_infracciones (SPEC/9 §8.2).

El acuse ("Recibido") guarda quién lo dio y cuándo, en UTC, y no se puede pisar: el primero
queda. Toda consulta es parametrizada (§9).
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from typing import Any, NamedTuple

from src.alerts.domain.aviso import EstadoNotificacion

_LISTAR = (
    "SELECT id, employee_name, zona, elemento, inicio, evidencia_path, estado_notificacion, "
    "reconocida_por, reconocida_en FROM ppe_infracciones "
    "WHERE (? IS NULL OR zona = ?) ORDER BY id DESC LIMIT ?"
)
_ZONAS = "SELECT DISTINCT zona FROM ppe_infracciones ORDER BY zona"
_RECONOCER = (
    "UPDATE ppe_infracciones SET reconocida_por = ?, reconocida_en = ? "
    "WHERE id = ? AND reconocida_por IS NULL"
)


class AlertaNoReconocibleError(LookupError):
    """La alerta no existe o ya tiene acuse de recibo."""


class AlertaRegistrada(NamedTuple):
    id_infraccion: int
    persona: str | None
    zona: str
    elemento: str
    inicio: datetime
    evidencia: str | None
    estado_notificacion: EstadoNotificacion
    reconocida_por: str | None
    reconocida_en: datetime | None


class RepositorioAlertasSQLite:
    """Lee las alertas para el panel y guarda el acuse de recibo del responsable."""

    def __init__(self, conectar: Callable[[], sqlite3.Connection]) -> None:
        self._conectar = conectar

    def listar(self, zona: str | None, limite: int) -> list[AlertaRegistrada]:
        """Las `limite` alertas más nuevas, de `zona` o de todas si es None."""
        with closing(self._conectar()) as conexion:
            filas = conexion.execute(_LISTAR, (zona, zona, limite)).fetchall()
        return [_alerta(fila) for fila in filas]

    def zonas(self) -> list[str]:
        """Las zonas que tienen alertas, para filtrar."""
        with closing(self._conectar()) as conexion:
            return [zona for (zona,) in conexion.execute(_ZONAS)]

    def reconocer(self, id_infraccion: int, por: str, en: datetime) -> None:
        """Guarda el acuse de recibo; falla si la alerta no existe o ya fue reconocida."""
        if not por.strip():
            raise ValueError("El acuse de recibo necesita quién lo da")
        if en.tzinfo is None:
            raise ValueError(f"La hora debe tener huso horario: {en.isoformat()}")
        parametros = (por, en.astimezone(UTC).isoformat(), id_infraccion)
        with closing(self._conectar()) as conexion, conexion:
            if conexion.execute(_RECONOCER, parametros).rowcount != 1:
                raise AlertaNoReconocibleError(
                    f"La alerta {id_infraccion} no existe o ya fue reconocida"
                )


def _alerta(fila: tuple[Any, ...]) -> AlertaRegistrada:
    id_infraccion, persona, zona, elemento, inicio, evidencia, estado, por, en = fila
    return AlertaRegistrada(
        id_infraccion,
        persona,
        zona,
        elemento,
        datetime.fromisoformat(inicio),
        evidencia,
        EstadoNotificacion(estado),
        por,
        None if en is None else datetime.fromisoformat(en),
    )
