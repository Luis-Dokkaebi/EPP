"""Puertos de salida del módulo de EPP (SPEC/9 §4.0; skill hexagonal-architecture).

La aplicación depende de estas interfaces; los adaptadores (base de datos, disco, canales de
aviso, reloj del sistema) las implementan fuera del dominio.
"""

from typing import Protocol

from src.ppe.domain import reloj
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import EventoInfraccion, InfraccionIniciada


class RelojPort(reloj.RelojPort, Protocol):
    """Reloj del caso de uso: el mismo contrato que usan la ventana y las infracciones."""


class RepositorioInfraccionesPort(Protocol):
    """Persiste cada evento antes de avisar, para no perder alertas (outbox, SPEC/9 §7.1)."""

    def guardar(self, evento: EventoInfraccion) -> None:
        """Guarda el evento; si falla, lanza y el evento no se publica."""


class AlmacenEvidenciasPort(Protocol):
    """Guarda la imagen del evento con la persona marcada (SPEC/9 §6.2)."""

    def guardar_evidencia(
        self, imagen: object, caja_persona: Caja, infraccion: InfraccionIniciada
    ) -> str:
        """Guarda la evidencia de `infraccion` y devuelve su referencia (ruta o id)."""


class PublicadorEventosPort(Protocol):
    """Entrega los eventos a la UI y a las notificaciones."""

    def publicar(self, evento: EventoInfraccion) -> None:
        """Publica el evento ya guardado."""
