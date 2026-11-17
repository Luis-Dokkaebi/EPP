"""La licencia en la ventana principal (SPEC/10 T-05).

Muestra cuántos días le quedan a la prueba y revalida la licencia cada hora con la app abierta:
una app que corre 24/7 antes nunca vencía. Si la licencia deja de regir, la ventana principal
suspende cámaras y avisos (sin borrar nada) y pide una licencia; sin ella, se cierra.
"""

from collections.abc import Callable
from typing import Protocol

import customtkinter as ctk

from src.gui.aviso_licencia import LicenciaConVigencia, aviso_de_prueba
from src.gui.ventana_licencia import LicenciaActivable, pedir_licencia
from src.security.guardia_licencia import GuardiaDeLicencia, LicenciaRevalidable

INTERVALO_DE_REVALIDACION_MS = 3_600_000
COLOR_AVISO = "#F39C12"
COLOR_URGENTE = "#E74C3C"


class LicenciaDeLaApp(LicenciaConVigencia, LicenciaRevalidable, LicenciaActivable, Protocol):
    """Lo que la ventana principal usa de la licencia DRM."""


class VentanaPrincipal(Protocol):
    def after(self, ms: int, func: Callable[[], None]) -> str: ...

    def suspender_por_licencia(self) -> None: ...

    def reanudar_con_licencia(self) -> None: ...

    def on_closing(self) -> None: ...


class LicenciaEnLaApp:
    """Aviso de la prueba en la barra lateral y guardia que revalida cada hora."""

    def __init__(
        self, app: VentanaPrincipal, licencia: LicenciaDeLaApp, barra: ctk.CTkFrame
    ) -> None:
        self._app = app
        self._licencia = licencia
        self._guardia = GuardiaDeLicencia(licencia, self)
        self.aviso = ctk.CTkLabel(barra, text="", font=("Roboto", 14, "bold"))
        self._seguir()

    def revalidar(self) -> None:
        if self._guardia.revisar():
            self._seguir()

    def _seguir(self) -> None:
        self._mostrar_aviso()
        self._app.after(INTERVALO_DE_REVALIDACION_MS, self.revalidar)

    def _mostrar_aviso(self) -> None:
        aviso = aviso_de_prueba(self._licencia)
        if aviso is None:
            self.aviso.pack_forget()
            return
        color = COLOR_URGENTE if aviso.urgente else COLOR_AVISO
        self.aviso.configure(text=aviso.texto, text_color=color)
        self.aviso.pack(pady=(0, 10), padx=20, anchor="w")

    def suspender(self) -> None:
        self._app.suspender_por_licencia()

    def pedir_licencia(self) -> bool:
        return pedir_licencia(self._app, self._licencia)

    def reanudar(self) -> None:
        self._app.reanudar_con_licencia()

    def cerrar(self) -> None:
        self._app.on_closing()
