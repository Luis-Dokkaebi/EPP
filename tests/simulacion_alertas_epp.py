"""Simulación de punta a punta de las alertas de EPP para features/alertas_epp.feature.

Detección simulada (tests/simulacion_cumplimiento_ppe.py) -> infracción guardada en una base
SQLite en tmp_path -> bandeja de salida -> despachador -> webhook firmado -> servidor local
falso. Sin red real ni reloj real; los umbrales y la política de reintentos son de prueba.
"""

import functools
import json
import sqlite3
import ssl
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

from src.alerts.application.despachar_notificaciones import (
    DespacharNotificaciones,
    PuertosDespacho,
)
from src.alerts.canal_webhook import CanalWebhook, ConfiguracionWebhook
from src.alerts.domain.circuito import CircuitBreaker
from src.alerts.domain.mensaje import DatosDeLaPersona
from src.alerts.domain.reintentos import PoliticaReintentos
from src.alerts.evidencias import LectorEvidencias
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import EventoInfraccion, InfraccionIniciada
from src.storage.bandeja_avisos import BandejaAvisosSQLite, agregar_columna_proximo_intento
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from tests.dobles_ppe import PuertosEnMemoria
from tests.escenas_ppe import TODO_EL_EPP
from tests.servidores_falsos import ServidorWebhookFalso
from tests.simulacion_cumplimiento_ppe import SEGUNDO_DE_CONFIRMACION, SimulacionCumplimiento

POLITICA = PoliticaReintentos(
    espera_inicial=timedelta(seconds=10),
    factor=2.0,
    espera_maxima=timedelta(minutes=1),
    intentos_maximos=5,
)
SEGUNDOS_ENTRE_DESPACHOS = 60
CANAL_CAIDO = 503
CANAL_DISPONIBLE = 200


def imagen_jpeg(fotograma: object) -> bytes:
    """La imagen sintética del fotograma: bytes con forma de JPEG."""
    return b"\xff\xd8 " + str(fotograma).encode() + b" \xff\xd9"


class PuertosPersistentes(PuertosEnMemoria):
    """Además de anotar las llamadas, guarda las infracciones en la base y la imagen en disco."""

    def __init__(self, repositorio: RepositorioInfraccionesSQLite, carpeta: Path) -> None:
        super().__init__()
        self._repositorio = repositorio
        self._carpeta = carpeta

    def guardar(self, evento: EventoInfraccion) -> None:
        self._repositorio.guardar(evento)
        super().guardar(evento)

    def guardar_evidencia(
        self, imagen: object, caja_persona: Caja, infraccion: InfraccionIniciada
    ) -> str:
        super().guardar_evidencia(imagen, caja_persona, infraccion)
        ruta = self._carpeta / f"{imagen}.jpg"
        ruta.write_bytes(imagen_jpeg(imagen))
        return str(ruta)


class SimulacionAlertas:
    """Un operario frente a la cámara y el responsable de seguridad detrás de un webhook."""

    def __init__(self, carpeta: Path) -> None:
        self._conectar = functools.partial(sqlite3.connect, carpeta / "tracking.db")
        crear_tabla_infracciones(self._conectar)
        agregar_columna_proximo_intento(self._conectar)
        evidencias = carpeta / "snapshots"
        evidencias.mkdir()
        repositorio = RepositorioInfraccionesSQLite(self._conectar)
        self.cumplimiento = SimulacionCumplimiento(PuertosPersistentes(repositorio, evidencias))
        self.servidor = ServidorWebhookFalso()
        configuracion = ConfiguracionWebhook(
            url=self.servidor.url,
            secreto=b"secreto-de-prueba",
            timeout=timedelta(seconds=2),
            contexto_tls=ssl.create_default_context(),
        )
        canal = CanalWebhook(configuracion, DatosDeLaPersona.NOMBRE, LectorEvidencias(evidencias))
        bandeja = BandejaAvisosSQLite(self._conectar)
        self._despacho = DespacharNotificaciones(
            PuertosDespacho(bandeja, canal, self.cumplimiento.reloj),
            POLITICA,
            CircuitBreaker(fallas_para_abrir=3, pausa=timedelta(minutes=5)),
        )

    def __enter__(self) -> "SimulacionAlertas":
        self.servidor.__enter__()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.servidor.__exit__(tipo, error, traza)

    def operario_sin(self, elemento: str, zona: str, nombre: str | None) -> None:
        faltante = ElementoEPP(elemento)
        self.cumplimiento.nombre = nombre
        self.cumplimiento.ubicar_operario({zona}, [e for e in TODO_EL_EPP if e is not faltante])

    def confirmar_la_infraccion(self) -> None:
        self.cumplimiento.transcurrir_hasta(SEGUNDO_DE_CONFIRMACION)

    def transcurrir_despachando(self, duracion: timedelta) -> None:
        """Pasa el tiempo con el despachador corriendo una vez por minuto, como su hilo."""
        segundos = int(duracion.total_seconds())
        for segundo in range(SEGUNDOS_ENTRE_DESPACHOS, segundos + 1, SEGUNDOS_ENTRE_DESPACHOS):
            self.cumplimiento.transcurrir_hasta(segundo)
            self.despachar()

    def despachar(self) -> None:
        self._despacho.despachar_pendientes()

    def caer_el_canal(self) -> None:
        self.servidor.estado = CANAL_CAIDO

    def restablecer_el_canal(self) -> None:
        """El canal vuelve y el despachador corre cuando vence la espera del reintento."""
        self.servidor.estado = CANAL_DISPONIBLE
        self.cumplimiento.reloj.avanzar(POLITICA.espera_maxima)
        self.despachar()

    @property
    def recibidas(self) -> list[dict[str, Any]]:
        """Las alertas que el responsable recibió (las que el webhook aceptó)."""
        return [json.loads(pedido.cuerpo) for pedido in self.servidor.aceptados]

    def infracciones(self) -> list[int]:
        return [fila[0] for fila in self._consultar("SELECT id FROM ppe_infracciones")]

    def estados_de_notificacion(self) -> list[str]:
        consulta = "SELECT estado_notificacion FROM ppe_infracciones ORDER BY id"
        return [fila[0] for fila in self._consultar(consulta)]

    def imagen_de_la_infraccion(self) -> bytes:
        (alerta,) = self.cumplimiento.alertas
        return imagen_jpeg(self.cumplimiento.imagen_en(alerta.inicio))

    def _consultar(self, sql: str) -> list[tuple[Any, ...]]:
        with closing(self._conectar()) as conexion:
            return conexion.execute(sql).fetchall()
