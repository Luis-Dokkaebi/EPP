"""Hilo del despachador de avisos, separado de las cámaras (SPEC/9 §7.1 punto 2).

Despacha apenas arranca y luego una vez por intervalo, hasta que se lo detiene. Un ciclo que
falla (por ejemplo, la base bloqueada) se registra con su traza y el despacho sigue en el
próximo ciclo: los avisos siguen en la bandeja, así que no se pierde ninguno. El hilo es de
segundo plano para no impedir que la aplicación cierre, pero `detener` debe llamarse siempre y
falla en voz alta si el hilo no termina a tiempo.
"""

import logging
import threading
from collections.abc import Callable
from datetime import timedelta

from src.alerts.domain.errores import ConfiguracionAlertasError

logger = logging.getLogger(__name__)

_NOMBRE_DEL_HILO = "despachador-avisos"


class HiloDespachador:
    """Corre `despachar` en un hilo propio cada `intervalo`."""

    _hilo: threading.Thread | None

    def __init__(self, despachar: Callable[[], None], intervalo: timedelta) -> None:
        if intervalo <= timedelta(0):
            raise ConfiguracionAlertasError(f"intervalo debe ser positivo: {intervalo}")
        self._despachar = despachar
        self._intervalo = intervalo
        self._detener = threading.Event()
        self._hilo = None

    @property
    def en_marcha(self) -> bool:
        return self._hilo is not None

    def iniciar(self) -> None:
        if self._hilo is not None:
            raise RuntimeError("El despachador de avisos ya está en marcha")
        self._detener.clear()
        self._hilo = threading.Thread(target=self._correr, name=_NOMBRE_DEL_HILO, daemon=True)
        self._hilo.start()

    def detener(self, espera_maxima: timedelta) -> None:
        """Pide al hilo que termine y lo espera; sin hilo en marcha, no hace nada."""
        if self._hilo is None:
            return
        self._detener.set()
        self._hilo.join(espera_maxima.total_seconds())
        if self._hilo.is_alive():
            raise RuntimeError(f"El despachador de avisos no se detuvo en {espera_maxima}")
        self._hilo = None

    def _correr(self) -> None:
        self._ciclo()
        while not self._detener.wait(self._intervalo.total_seconds()):
            self._ciclo()

    def _ciclo(self) -> None:
        try:
            self._despachar()
        except Exception:
            # Registrar y seguir es la acción: el hilo no debe morir por un ciclo fallido.
            logger.exception(
                "Falló un ciclo del despacho de avisos; se reintenta en el próximo ciclo"
            )
