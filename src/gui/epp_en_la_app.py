"""El módulo de EPP dentro de la ventana principal (SPEC/9 §5.4; D5 y D10).

La ventana pregunta aquí si la licencia habilita el módulo y le pide arrancar los avisos; así la
composición de la sucursal no engorda `main_ui.py`.
"""

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

from config import config
from src import composicion_avisos
from src.alerts.hilo_despachador import HiloDespachador
from src.composicion_epp import MODULO_EPP, LicenciaPort, RelojSistema


def modulo_habilitado(licencia: LicenciaPort | None) -> bool:
    return licencia is not None and licencia.incluye_modulo(MODULO_EPP)


def conexion_de_la_sucursal() -> Callable[[], sqlite3.Connection]:
    ruta_base = config.get_db_path()

    def conectar() -> sqlite3.Connection:
        return sqlite3.connect(ruta_base)

    return conectar


def iniciar_avisos() -> HiloDespachador | None:
    """Purga evidencias vencidas (D5) y arranca el despachador salvo en modo sombra o sin canal."""
    despachador = composicion_avisos.preparar_avisos(
        os.environ, conexion_de_la_sucursal(), Path(config.get_snapshots_dir()), RelojSistema()
    )
    if despachador is not None:
        despachador.iniciar()
    return despachador
