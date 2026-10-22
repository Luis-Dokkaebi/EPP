"""Dobles de prueba de los puertos del módulo de EPP (CLAUDE.md §4: sin reloj real)."""

from datetime import UTC, datetime, timedelta

INICIO = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)


class RelojFalso:
    """Reloj que solo avanza (o retrocede) cuando la prueba lo pide."""

    def __init__(self, inicio: datetime = INICIO) -> None:
        self._ahora = inicio

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, intervalo: timedelta) -> None:
        self._ahora += intervalo
