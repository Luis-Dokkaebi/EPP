"""El módulo de EPP dentro de la ventana principal (SPEC/9 §5.4; D5 y D10).

La ventana pregunta aquí si la licencia habilita el módulo, le pide registrar sus vistas (alertas y
reporte de cumplimiento, §8.2 y §8.4) y arrancar los avisos; así la composición de la sucursal no
engorda `main_ui.py`.
"""

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import customtkinter as ctk

from config import config
from src import composicion_avisos
from src.alerts.hilo_despachador import HiloDespachador
from src.composicion_epp import MODULO_EPP, LicenciaPort, RelojSistema
from src.gui.vistas_epp import (
    PanelReporteCumplimiento,
    crear_vista_alertas,
    preferencias_del_equipo,
)
from src.storage.infracciones_epp import crear_tabla_infracciones


class RegistroDeVistas(Protocol):
    def register_view(self, name: str, view_instance: ctk.CTkFrame) -> None: ...


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


def registrar_vistas(vistas: RegistroDeVistas, espacio: ctk.CTkFrame) -> None:
    conectar = conexion_de_la_sucursal()
    crear_tabla_infracciones(conectar)
    preferencias = preferencias_del_equipo()
    vistas.register_view("AlertasEPP", crear_vista_alertas(espacio, conectar, preferencias))
    carpeta_export = Path(config.get_export_dir())
    vistas.register_view(
        "CumplimientoEPP",
        PanelReporteCumplimiento(espacio, conectar, carpeta_export, preferencias.zona_horaria),
    )
