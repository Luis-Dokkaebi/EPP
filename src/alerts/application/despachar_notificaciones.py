"""Caso de uso: despachar la bandeja de salida de avisos (SPEC/9 §7.1, AC-016).

Toma los avisos pendientes y los entrega por el canal. Si el canal falla, el aviso se reprograma
con backoff; agotados los intentos, queda FALLIDA. Si el canal falla de forma repetida, el
circuito se abre y el despacho espera sin intentar, para no saturarlo. Ningún aviso se descarta
en silencio (P5). Solo NotificacionFallidaError es una falla de entrega: cualquier otra
excepción es un defecto y se propaga sin tocar el aviso.

Los logs nombran el aviso por su id, nunca por la persona (§9).
"""

import logging
from datetime import datetime
from typing import NamedTuple

from src.alerts.application.ports import BandejaSalidaPort, NotificadorPort, RelojPort
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.circuito import CircuitBreaker
from src.alerts.domain.errores import NotificacionFallidaError
from src.alerts.domain.reintentos import PoliticaReintentos

logger = logging.getLogger(__name__)


class PuertosDespacho(NamedTuple):
    """Los adaptadores que necesita el despacho."""

    bandeja: BandejaSalidaPort
    notificador: NotificadorPort
    reloj: RelojPort


class DespacharNotificaciones:
    """Entrega los avisos pendientes respetando la política de reintentos y el circuito."""

    def __init__(
        self, puertos: PuertosDespacho, politica: PoliticaReintentos, circuito: CircuitBreaker
    ) -> None:
        self._bandeja, self._notificador, self._reloj = puertos
        self._politica = politica
        self._circuito = circuito

    def despachar_pendientes(self) -> None:
        ahora = self._reloj.ahora()
        for aviso in self._bandeja.pendientes(ahora):
            if not self._circuito.permite_intento(ahora):
                logger.warning(
                    "Despacho en espera (%s): quedan avisos pendientes",
                    self._circuito.estado(ahora).value,
                )
                return
            self._intentar(aviso, ahora)

    def _intentar(self, aviso: Aviso, ahora: datetime) -> None:
        try:
            self._notificador.enviar(aviso)
        except NotificacionFallidaError as error:
            self._circuito.registrar_falla(ahora)
            self._registrar_fallo(aviso, ahora, error)
            return
        self._circuito.registrar_exito()
        self._bandeja.marcar_enviada(aviso.id_aviso)

    def _registrar_fallo(
        self, aviso: Aviso, ahora: datetime, error: NotificacionFallidaError
    ) -> None:
        intentos = aviso.intentos + 1
        if self._politica.agotada(intentos):
            self._bandeja.marcar_fallida(aviso.id_aviso, intentos)
            logger.error("Aviso %d FALLIDO tras %d intentos: %s", aviso.id_aviso, intentos, error)
            return
        proximo = ahora + self._politica.espera_tras(intentos)
        self._bandeja.reprogramar(aviso.id_aviso, intentos, proximo)
        logger.warning(
            "Aviso %d no entregado (intento %d); se reintenta a las %s: %s",
            aviso.id_aviso,
            intentos,
            proximo.isoformat(),
            error,
        )
