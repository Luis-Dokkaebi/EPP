"""Vistas del módulo de EPP en la navegación (SPEC/9 §8.2 y §8.4).

"Alertas EPP" arma el panel con su presentador sobre la base del tenant. "Cumplimiento EPP" pide
el rango de fechas, valida antes de tocar la base y genera el Excel en segundo plano; el aviso de
fin llega por el buzón, porque Tk solo admite llamadas desde su propio hilo.
"""

import getpass
import sqlite3
import time
from collections.abc import Callable
from datetime import date, timedelta, timezone, tzinfo
from pathlib import Path

import customtkinter as ctk

from src.analysis.reporte_cumplimiento_epp import GeneradorReporteCumplimiento, PedidoReporte
from src.composicion_epp import RelojSistema
from src.gui.buzon_hilo_ui import BuzonHiloUI
from src.gui.panel_alertas import PanelAlertas
from src.gui.presentador_alertas import PreferenciasPanel, PresentadorAlertas
from src.gui.selector_fecha import RangoDeFechasInvalidoError, SelectorDeFecha, leer_fecha
from src.storage.alertas_panel import RepositorioAlertasSQLite

INTERVALO_DEL_PANEL_MS = 5000
LIMITE_DE_ALERTAS = 200
INTERVALO_DEL_BUZON_MS = 100
VERDE, ROJO, AMARILLO = "#2ECC71", "#E74C3C", "#F39C12"


def preferencias_del_equipo() -> PreferenciasPanel:
    """Quien usa este equipo firma los acuses; las horas se ven en su huso horario."""
    zona_local = timezone(timedelta(seconds=time.localtime().tm_gmtoff))
    return PreferenciasPanel(getpass.getuser(), zona_local, LIMITE_DE_ALERTAS)


def crear_vista_alertas(
    workspace: ctk.CTkBaseClass,
    conectar: Callable[[], sqlite3.Connection],
    preferencias: PreferenciasPanel,
) -> PanelAlertas:
    presentador = PresentadorAlertas(
        RepositorioAlertasSQLite(conectar), RelojSistema(), preferencias
    )
    return PanelAlertas(workspace, presentador, INTERVALO_DEL_PANEL_MS)


class PanelReporteCumplimiento(ctk.CTkFrame):
    """Rango de fechas y botón para exportar el reporte de cumplimiento de EPP."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conectar: Callable[[], sqlite3.Connection],
        carpeta_export: Path,
        zona_horaria: tzinfo,
    ) -> None:
        super().__init__(master)
        self._generador = GeneradorReporteCumplimiento(conectar, RelojSistema(), zona_horaria)
        self._carpeta = carpeta_export
        hoy = date.today()
        self.desde = SelectorDeFecha(self, hoy)
        self.desde.pack(side="left", padx=5)
        self.hasta = SelectorDeFecha(self, hoy)
        self.hasta.pack(side="left", padx=5)
        ctk.CTkButton(self, text="Exportar Excel", command=self.exportar).pack(side="left")
        self._estado = ctk.CTkLabel(self, text="")
        self._estado.pack(side="left", padx=10)
        self.buzon = BuzonHiloUI(self.after, INTERVALO_DEL_BUZON_MS)
        self.buzon.vigilar()

    def exportar(self) -> None:
        try:
            desde, hasta = leer_fecha(self.desde.get()), leer_fecha(self.hasta.get())
            if desde > hasta:
                raise RangoDeFechasInvalidoError(
                    f"La fecha «Desde» ({desde}) es posterior a «Hasta» ({hasta})."
                )
        except ValueError as error:
            self._mostrar(f"❌ {error}", ROJO)
            return
        ruta = self._carpeta / f"Cumplimiento_EPP_{desde}_a_{hasta}.xlsx"
        self._mostrar("⏳ Generando el reporte...", AMARILLO)
        self._generador.generar_en_segundo_plano(
            PedidoReporte(desde, hasta, ruta), self._al_terminar, self._al_fallar
        )

    def _al_terminar(self, ruta: Path, filas: int) -> None:
        self.buzon.publicar(
            lambda: self._mostrar(f"✅ Reporte exportado: {ruta} ({filas} filas)", VERDE)
        )

    def _al_fallar(self, error: Exception) -> None:
        self.buzon.publicar(
            lambda: self._mostrar(f"❌ No se pudo generar el reporte: {error}", ROJO)
        )

    def _mostrar(self, texto: str, color: str) -> None:
        self._estado.configure(text=texto, text_color=color)
