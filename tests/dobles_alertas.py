"""Dobles de prueba de los puertos de notificaciones (CLAUDE.md §4: sin red ni base real)."""

from collections.abc import Iterable, Sequence
from datetime import datetime

from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import NotificacionFallidaError
from tests.dobles_ppe import INICIO


def aviso(id_aviso: int, intentos: int = 0, persona: str | None = "Ana") -> Aviso:
    return Aviso(
        id_aviso=id_aviso,
        persona=persona,
        elemento="casco",
        zona="Boca de pozo",
        inicio=INICIO,
        evidencia=f"epp/{id_aviso}.jpg",
        intentos=intentos,
    )


class BandejaFalsa:
    """Devuelve los avisos que le da la prueba y anota, en orden, cada cambio de estado."""

    def __init__(self, avisos: Iterable[Aviso]) -> None:
        self._avisos = tuple(avisos)
        self.consultas: list[datetime] = []
        self.cambios: list[tuple[object, ...]] = []

    def pendientes(self, ahora: datetime) -> Sequence[Aviso]:
        self.consultas.append(ahora)
        return self._avisos

    def marcar_enviada(self, id_aviso: int) -> None:
        self.cambios.append(("enviada", id_aviso))

    def reprogramar(self, id_aviso: int, intentos: int, proximo_intento: datetime) -> None:
        self.cambios.append(("reprogramada", id_aviso, intentos, proximo_intento))

    def marcar_fallida(self, id_aviso: int, intentos: int) -> None:
        self.cambios.append(("fallida", id_aviso, intentos))


class CanalFalso:
    """Canal de aviso cuyas respuestas fija la prueba: True entrega, False falla."""

    def __init__(self, respuestas: Iterable[bool]) -> None:
        self._respuestas = iter(respuestas)
        self.intentos: list[int] = []

    def enviar(self, aviso: Aviso) -> None:
        self.intentos.append(aviso.id_aviso)
        if not next(self._respuestas):
            raise NotificacionFallidaError(f"canal caído al enviar el aviso {aviso.id_aviso}")
