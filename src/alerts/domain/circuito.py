"""Circuit breaker del canal de aviso (SPEC/9 §7.1 punto 5; skill error-handling).

- CERRADO: se intenta normalmente; cuenta las fallas consecutivas.
- ABIERTO: tras `fallas_para_abrir` fallas seguidas, no se intenta durante `pausa`, para no
  saturar un canal caído.
- SEMIABIERTO: vencida la pausa, se permite un intento de prueba. Si sale bien, se cierra; si
  falla, vuelve a abrirse por otra pausa completa.

El instante lo pasa quien llama (el despachador lo toma de su reloj): el circuito no lee la hora.
"""

from datetime import datetime, timedelta
from enum import Enum

from src.alerts.domain.errores import ConfiguracionAlertasError


class EstadoCircuito(Enum):
    """Estado del canal de aviso; el valor es el texto para el usuario y los logs."""

    CERRADO = "canal disponible"
    ABIERTO = "canal en pausa"
    SEMIABIERTO = "canal en prueba"


class CircuitBreaker:
    """Decide si conviene intentar el canal según sus fallas recientes."""

    _abierto_hasta: datetime | None

    def __init__(self, fallas_para_abrir: int, pausa: timedelta) -> None:
        if fallas_para_abrir < 1:
            raise ConfiguracionAlertasError(
                f"fallas_para_abrir debe ser al menos 1: {fallas_para_abrir}"
            )
        if pausa <= timedelta(0):
            raise ConfiguracionAlertasError(f"pausa debe ser positiva: {pausa}")
        self._fallas_para_abrir = fallas_para_abrir
        self._pausa = pausa
        self._fallas_consecutivas = 0
        self._abierto_hasta = None

    def estado(self, ahora: datetime) -> EstadoCircuito:
        if self._abierto_hasta is None:
            return EstadoCircuito.CERRADO
        if ahora < self._abierto_hasta:
            return EstadoCircuito.ABIERTO
        return EstadoCircuito.SEMIABIERTO

    def permite_intento(self, ahora: datetime) -> bool:
        return self.estado(ahora) is not EstadoCircuito.ABIERTO

    def registrar_exito(self) -> None:
        self._fallas_consecutivas = 0
        self._abierto_hasta = None

    def registrar_falla(self, ahora: datetime) -> None:
        # Semiabierto, la cuenta ya alcanzó el umbral (solo un éxito la reinicia): la falla del
        # intento de prueba reabre el circuito por otra pausa completa.
        self._fallas_consecutivas += 1
        if self._fallas_consecutivas >= self._fallas_para_abrir:
            self._abierto_hasta = ahora + self._pausa
