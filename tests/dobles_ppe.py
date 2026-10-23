"""Dobles de prueba de los puertos del módulo de EPP (CLAUDE.md §4: sin reloj real)."""

from datetime import UTC, datetime, timedelta

from src.ppe.application.evaluar_cumplimiento import PuertosCumplimiento
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import EventoInfraccion, InfraccionIniciada

INICIO = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)


class RelojFalso:
    """Reloj que solo avanza (o retrocede) cuando la prueba lo pide."""

    def __init__(self, inicio: datetime = INICIO) -> None:
        self._ahora = inicio

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, intervalo: timedelta) -> None:
        self._ahora += intervalo


class PuertosEnMemoria:
    """Repositorio, almacén de evidencias y publicador falsos que anotan, en orden, cada llamada."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, object]] = []
        self.evidencias: dict[str, object] = {}

    def guardar(self, evento: EventoInfraccion) -> None:
        self.llamadas.append(("guardar", evento))

    def guardar_evidencia(
        self, imagen: object, caja_persona: Caja, infraccion: InfraccionIniciada
    ) -> str:
        self.llamadas.append(("guardar_evidencia", (imagen, caja_persona, infraccion)))
        referencia = f"evidencia/{imagen}"
        self.evidencias[referencia] = imagen
        return referencia

    def publicar(self, evento: EventoInfraccion) -> None:
        self.llamadas.append(("publicar", evento))

    @property
    def publicados(self) -> list[object]:
        return [evento for nombre, evento in self.llamadas if nombre == "publicar"]

    def como_puertos(self) -> PuertosCumplimiento:
        return PuertosCumplimiento(repositorio=self, almacen=self, publicador=self)
