"""Presentador del panel "Alertas EPP" (SPEC/9 §8.2): toda la lógica del panel, sin Tk.

La vista es delgada: muestra `filas`, `zonas` y `mensaje`, y llama a `actualizar`,
`filtrar_por_zona` y `marcar_recibido`. El acuse de recibo guarda quién lo dio (el usuario de la
sesión) y cuándo. Si otro ya lo había dado, se informa sin romper el panel.

El filtro por cámara de §8.2 queda pendiente: la tabla de infracciones todavía no registra la
cámara (llega con la composición de las cámaras, §5.4).
"""

from datetime import datetime, tzinfo
from typing import NamedTuple, Protocol

from src.alerts.domain.aviso import EstadoNotificacion
from src.alerts.domain.mensaje import SIN_IDENTIFICAR
from src.ppe.domain.reloj import RelojPort
from src.storage.alertas_panel import AlertaNoReconocibleError, AlertaRegistrada

TODAS_LAS_ZONAS = "Todas las zonas"
TEXTO_DEL_AVISO = {
    EstadoNotificacion.PENDIENTE: "Aviso pendiente",
    EstadoNotificacion.ENVIADA: "Aviso enviado",
    EstadoNotificacion.FALLIDA: "Aviso fallido",
    EstadoNotificacion.DESCARTADA: "Descartado al salir del modo sombra",
}


class RepositorioAlertasPort(Protocol):
    def listar(self, zona: str | None, limite: int) -> list[AlertaRegistrada]: ...

    def zonas(self) -> list[str]: ...

    def reconocer(self, id_infraccion: int, por: str, en: datetime) -> None: ...


class PreferenciasPanel(NamedTuple):
    """Quién usa el panel, en qué huso horario ve las horas y cuántas alertas muestra."""

    usuario: str
    zona_horaria: tzinfo
    limite: int


class FilaAlerta(NamedTuple):
    """Una fila del panel, ya en texto; `recibido` es None mientras falte el acuse."""

    id_infraccion: int
    miniatura: str | None
    persona: str
    zona: str
    elemento: str
    hora: str
    aviso: str
    recibido: str | None


class PresentadorAlertas:
    """Estado y comandos del panel de alertas."""

    filas: list[FilaAlerta]
    zonas: list[str]
    zona_filtrada: str | None
    mensaje: str | None

    def __init__(
        self, repositorio: RepositorioAlertasPort, reloj: RelojPort, preferencias: PreferenciasPanel
    ) -> None:
        if preferencias.limite < 1:
            raise ValueError(f"El panel debe mostrar al menos una alerta: {preferencias.limite}")
        self._repositorio = repositorio
        self._reloj = reloj
        self._preferencias = preferencias
        self.filas = []
        self.zonas = [TODAS_LAS_ZONAS]
        self.zona_filtrada = None
        self.mensaje = None

    def actualizar(self) -> None:
        """Vuelve a leer las alertas (la vista lo llama periódicamente: lista en vivo)."""
        self.mensaje = None
        self._leer()

    def filtrar_por_zona(self, zona: str) -> None:
        self.zona_filtrada = None if zona == TODAS_LAS_ZONAS else zona
        self.actualizar()

    def marcar_recibido(self, id_infraccion: int) -> None:
        usuario = self._preferencias.usuario
        try:
            self._repositorio.reconocer(id_infraccion, usuario, self._reloj.ahora())
        except AlertaNoReconocibleError:
            self._leer()
            self.mensaje = f"La alerta {id_infraccion} ya tenía acuse de recibo"
            return
        self.actualizar()

    def _leer(self) -> None:
        alertas = self._repositorio.listar(self.zona_filtrada, self._preferencias.limite)
        self.filas = [self._fila(alerta) for alerta in alertas]
        self.zonas = [TODAS_LAS_ZONAS, *self._repositorio.zonas()]

    def _fila(self, alerta: AlertaRegistrada) -> FilaAlerta:
        return FilaAlerta(
            id_infraccion=alerta.id_infraccion,
            miniatura=alerta.evidencia,
            persona=SIN_IDENTIFICAR if alerta.persona is None else alerta.persona,
            zona=alerta.zona,
            elemento=alerta.elemento,
            hora=self._local(alerta.inicio).strftime("%d/%m %H:%M:%S"),
            aviso=TEXTO_DEL_AVISO[alerta.estado_notificacion],
            recibido=self._recibido(alerta),
        )

    def _recibido(self, alerta: AlertaRegistrada) -> str | None:
        if alerta.reconocida_en is None:
            return None
        hora = self._local(alerta.reconocida_en).strftime("%H:%M")
        return f"Recibido por {alerta.reconocida_por} a las {hora}"

    def _local(self, instante: datetime) -> datetime:
        return instante.astimezone(self._preferencias.zona_horaria)
