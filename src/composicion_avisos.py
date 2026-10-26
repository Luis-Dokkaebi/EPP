"""Avisos de EPP de la sucursal abierta (SPEC/9 §5.4 y §7; D1, D5 y el modo sombra).

Al abrir la sucursal se crean las tablas que falten, se purgan las evidencias vencidas (D5: 30
días) y se arma el despachador de avisos, salvo en modo sombra (`EPP_MODO_SOMBRA=1`: el módulo
detecta y registra pero no avisa). Al salir del modo sombra, `EPP_FIN_MODO_SOMBRA` (ISO 8601 con
huso horario) indica desde cuándo avisar: las pendientes anteriores se descartan (decisión del
24/10/2026). Sin canal configurado no hay despachador; un canal mal configurado falla.
"""

import logging
import os
import sqlite3
import ssl
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path

from config import config
from src.alerts.application.despachar_notificaciones import (
    DespacharNotificaciones,
    PuertosDespacho,
)
from src.alerts.configuracion import SMTP_SERVIDOR, WEBHOOK_URL, canales_desde_entorno
from src.alerts.domain.circuito import CircuitBreaker
from src.alerts.domain.errores import ConfiguracionAlertasError
from src.alerts.domain.reintentos import PoliticaReintentos
from src.alerts.evidencias import LectorEvidencias
from src.alerts.hilo_despachador import HiloDespachador
from src.composicion_epp import PARAMETROS_DECIDIDOS, RelojSistema
from src.ppe.domain.reloj import RelojPort
from src.storage.bandeja_avisos import BandejaAvisosSQLite, agregar_columna_proximo_intento
from src.storage.infracciones_epp import crear_tabla_infracciones
from src.storage.retencion_evidencias import purgar_evidencias_vencidas, retencion_de_evidencias

logger = logging.getLogger(__name__)

MODO_SOMBRA = "EPP_MODO_SOMBRA"
FIN_MODO_SOMBRA = "EPP_FIN_MODO_SOMBRA"
# Valores técnicos: reintentos a los 30 s, 1, 2, 4, 8, 16 y 30 min (unas 2 h en total); tras 3
# fallas seguidas el canal descansa 5 min; la bandeja se revisa cada 15 s.
POLITICA_DE_REINTENTOS = PoliticaReintentos(
    espera_inicial=timedelta(seconds=30),
    factor=2.0,
    espera_maxima=timedelta(minutes=30),
    intentos_maximos=8,
)
FALLAS_PARA_ABRIR_EL_CIRCUITO = 3
PAUSA_DEL_CIRCUITO = timedelta(minutes=5)
INTERVALO_DE_DESPACHO = timedelta(seconds=15)


def preparar_avisos(
    entorno: Mapping[str, str],
    conectar: Callable[[], sqlite3.Connection],
    carpeta_snapshots: Path,
    reloj: RelojPort,
) -> HiloDespachador | None:
    """Deja la sucursal lista y devuelve su despachador sin iniciar, o None si no avisa."""
    crear_tabla_infracciones(conectar)
    agregar_columna_proximo_intento(conectar)
    retencion = retencion_de_evidencias(PARAMETROS_DECIDIDOS.retencion_dias)
    purgadas = purgar_evidencias_vencidas(conectar, carpeta_snapshots, reloj, retencion)
    logger.info("Evidencias de EPP purgadas por retención: %d", purgadas)
    if entorno.get(MODO_SOMBRA, "").strip() == "1":
        logger.info("Módulo EPP en modo sombra: se registra sin avisar")
        return None
    bandeja = BandejaAvisosSQLite(conectar)
    fin_sombra = _fin_del_modo_sombra(entorno)
    if fin_sombra is not None:
        descartadas = bandeja.descartar_pendientes_anteriores(fin_sombra)
        logger.info("Avisos del modo sombra descartados: %d", descartadas)
    if not any(entorno.get(variable, "").strip() for variable in (WEBHOOK_URL, SMTP_SERVIDOR)):
        logger.warning("Sin canal de aviso configurado (D1: email y webhook): no se avisa")
        return None
    canales = canales_desde_entorno(
        entorno, LectorEvidencias(carpeta_snapshots), ssl.create_default_context()
    )
    circuito = CircuitBreaker(FALLAS_PARA_ABRIR_EL_CIRCUITO, PAUSA_DEL_CIRCUITO)
    despacho = DespacharNotificaciones(
        PuertosDespacho(bandeja, canales, reloj), POLITICA_DE_REINTENTOS, circuito
    )
    return HiloDespachador(despacho.despachar_pendientes, INTERVALO_DE_DESPACHO)


def _fin_del_modo_sombra(entorno: Mapping[str, str]) -> datetime | None:
    valor = entorno.get(FIN_MODO_SOMBRA, "").strip()
    if not valor:
        return None
    try:
        fin = datetime.fromisoformat(valor)
    except ValueError as error:
        raise ConfiguracionAlertasError(
            f"{FIN_MODO_SOMBRA} debe ser una fecha ISO 8601 con huso horario: {valor}"
        ) from error
    if fin.tzinfo is None:
        raise ConfiguracionAlertasError(f"{FIN_MODO_SOMBRA} debe llevar huso horario: {valor}")
    return fin


def conexion_de_la_sucursal() -> Callable[[], sqlite3.Connection]:
    ruta_base = config.get_db_path()

    def conectar() -> sqlite3.Connection:
        return sqlite3.connect(ruta_base)

    return conectar


def iniciar_avisos_de_la_sucursal() -> HiloDespachador | None:
    """Purga evidencias vencidas (D5) y arranca el despachador salvo en modo sombra o sin canal."""
    despachador = preparar_avisos(
        os.environ, conexion_de_la_sucursal(), Path(config.get_snapshots_dir()), RelojSistema()
    )
    if despachador is not None:
        despachador.iniciar()
    return despachador
