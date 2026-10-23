"""Dobles de prueba de las notificaciones y del panel de alertas (CLAUDE.md §4: sin red ni base)."""

from collections.abc import Iterable, Sequence
from datetime import datetime

from src.alerts.domain.aviso import Aviso, EstadoNotificacion
from src.alerts.domain.errores import NotificacionFallidaError
from src.storage.alertas_panel import AlertaNoReconocibleError, AlertaRegistrada
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


def alerta_registrada(
    id_infraccion: int,
    persona: str | None = "Ana",
    zona: str = "Boca de pozo",
    estado: EstadoNotificacion = EstadoNotificacion.PENDIENTE,
) -> AlertaRegistrada:
    return AlertaRegistrada(
        id_infraccion, persona, zona, "casco", INICIO, f"ev/{id_infraccion}.jpg", estado, None, None
    )


class RepositorioAlertasFalso:
    """Alertas en memoria; anota cada consulta y cada acuse de recibo."""

    def __init__(self, *alertas: AlertaRegistrada) -> None:
        self.alertas = list(alertas)
        self.consultas: list[tuple[str | None, int]] = []
        self.acuses: list[tuple[int, str, datetime]] = []

    def listar(self, zona: str | None, limite: int) -> list[AlertaRegistrada]:
        self.consultas.append((zona, limite))
        return [alerta for alerta in self.alertas if zona in (None, alerta.zona)][:limite]

    def zonas(self) -> list[str]:
        return sorted({alerta.zona for alerta in self.alertas})

    def reconocer(self, id_infraccion: int, por: str, en: datetime) -> None:
        self.acuses.append((id_infraccion, por, en))
        posicion = [alerta.id_infraccion for alerta in self.alertas].index(id_infraccion)
        alerta = self.alertas[posicion]
        if alerta.reconocida_por is not None:
            raise AlertaNoReconocibleError(f"La alerta {id_infraccion} ya fue reconocida")
        self.alertas[posicion] = alerta._replace(reconocida_por=por, reconocida_en=en)
