"""Las vistas del módulo de EPP en la ventana principal (SPEC/9 §8.2 y §8.4).

La ventana le pide aquí registrar las vistas del módulo (alertas y reporte de cumplimiento); así la
composición de la sucursal no engorda `main_ui.py`. La decisión de si la licencia habilita el
módulo y el arranque de los avisos viven fuera de la GUI (`composicion_epp`, `composicion_avisos`)
porque el modo sin interfaz también los usa.
"""

from pathlib import Path
from typing import Protocol

import customtkinter as ctk

from config import config
from src.composicion_avisos import conexion_de_la_sucursal
from src.gui.vistas_epp import (
    PanelReporteCumplimiento,
    crear_vista_alertas,
    preferencias_del_equipo,
)
from src.storage.infracciones_epp import crear_tabla_infracciones


class RegistroDeVistas(Protocol):
    def register_view(self, name: str, view_instance: ctk.CTkFrame) -> None: ...


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
