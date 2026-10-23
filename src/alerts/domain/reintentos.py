"""Política de reintentos de un aviso: backoff exponencial con tope (SPEC/9 §7.1 punto 3).

Tras el intento fallido número n, el siguiente espera `espera_inicial * factor ** (n - 1)`, sin
pasar de `espera_maxima`. Al llegar a `intentos_maximos` fallidos, el aviso queda FALLIDA. Los
valores no tienen valores por omisión: los fija quien despliega.
"""

from dataclasses import dataclass
from datetime import timedelta

from src.alerts.domain.errores import ConfiguracionAlertasError


@dataclass(frozen=True)
class PoliticaReintentos:
    """Cuánto esperar antes de reintentar un aviso y cuándo darlo por fallido."""

    espera_inicial: timedelta
    factor: float
    espera_maxima: timedelta
    intentos_maximos: int

    def __post_init__(self) -> None:
        if self.espera_inicial <= timedelta(0):
            raise ConfiguracionAlertasError(
                f"espera_inicial debe ser positiva: {self.espera_inicial}"
            )
        if self.factor < 1:
            raise ConfiguracionAlertasError(f"factor debe ser al menos 1: {self.factor}")
        if self.espera_maxima < self.espera_inicial:
            raise ConfiguracionAlertasError(
                "espera_maxima no puede ser menor que espera_inicial: "
                f"{self.espera_maxima} < {self.espera_inicial}"
            )
        if self.intentos_maximos < 1:
            raise ConfiguracionAlertasError(
                f"intentos_maximos debe ser al menos 1: {self.intentos_maximos}"
            )

    def espera_tras(self, intentos: int) -> timedelta:
        """Espera antes del próximo intento, tras `intentos` intentos fallidos (al menos 1)."""
        if intentos < 1:
            raise ValueError(f"intentos debe ser al menos 1: {intentos}")
        espera = self.espera_inicial
        # Se acota en cada paso, no al final: así un número grande de intentos no desborda.
        for _ in range(intentos - 1):
            espera = min(espera * self.factor, self.espera_maxima)
        return espera

    def agotada(self, intentos: int) -> bool:
        """True si, tras `intentos` intentos fallidos, ya no quedan reintentos."""
        return intentos >= self.intentos_maximos
