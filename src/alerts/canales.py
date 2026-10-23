"""Aviso por varios canales a la vez (D1: email y webhook; SPEC/9 §7.1).

El aviso cuenta como entregado cuando lo recibieron todos los canales. Si alguno falla, se
informa una NotificacionFallidaError con cada canal que falló y el despachador lo reintenta; en
el reintento solo se usan los canales que faltan, para no duplicar el aviso en los demás. Ese
registro vive en memoria: si la aplicación se reinicia con una entrega parcial, el canal que ya
había entregado puede recibir el aviso de nuevo (el webhook lo descarta por su clave de
idempotencia; el email conserva el mismo Message-ID).
"""

from collections.abc import Mapping

from src.alerts.application.ports import NotificadorPort
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import ConfiguracionAlertasError, NotificacionFallidaError


class CanalesDeAviso:
    """Implementa NotificadorPort repartiendo el aviso entre los canales configurados."""

    def __init__(self, canales: Mapping[str, NotificadorPort]) -> None:
        if not canales:
            raise ConfiguracionAlertasError(
                "No hay ningún canal de aviso configurado (D1: email y webhook)"
            )
        self._canales = dict(canales)
        self._entregados: dict[int, frozenset[str]] = {}

    @property
    def nombres(self) -> tuple[str, ...]:
        """Los canales configurados, en el orden en que se usan."""
        return tuple(self._canales)

    @property
    def entregas_parciales(self) -> dict[int, frozenset[str]]:
        """Por aviso con entrega incompleta, los canales que ya lo recibieron."""
        return dict(self._entregados)

    def enviar(self, aviso: Aviso) -> None:
        entregados = set(self._entregados.get(aviso.id_aviso, frozenset()))
        fallas = []
        for nombre, canal in self._canales.items():
            if nombre in entregados:
                continue
            try:
                canal.enviar(aviso)
            except NotificacionFallidaError as error:
                fallas.append(f"{nombre}: {error}")
                continue
            entregados.add(nombre)
        if fallas:
            self._entregados[aviso.id_aviso] = frozenset(entregados)
            raise NotificacionFallidaError("; ".join(fallas))
        self._entregados.pop(aviso.id_aviso, None)
