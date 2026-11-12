"""Ventana de activación de la licencia (SPEC/10 F-03.4).

Se muestra al abrir la app sin una licencia vigente y cuando la licencia vence con la app
abierta. Enseña el Machine ID que el cliente envía al proveedor y recibe la llave de activación.
"""

from typing import Protocol

import customtkinter as ctk

from src.security.vigencia_licencia import MotivoDeRechazo

ESPERA_AL_ACTIVAR_MS = 1500
COLOR_ERROR = "#E74C3C"
COLOR_EXITO = "#2ECC71"
COLOR_TEXTO = "#A0A0A0"
COLOR_PANEL = "#2B2B2B"
COLOR_FONDO = "#1E1E1E"
TITULO_REQUERIDA = "Licencia requerida"
TITULO_VENCIDA = "Su licencia venció"
EXPLICACIONES: dict[MotivoDeRechazo | None, str] = {
    MotivoDeRechazo.VENCIDA: (
        "Contrate para continuar: lo aprendido se conserva (rostros, zonas e historial)."
    ),
    MotivoDeRechazo.FECHA_INCORRECTA: (
        "La fecha del equipo no es correcta. Corríjala y vuelva a abrir la aplicación."
    ),
}
EXPLICACION_POR_OMISION = "Envíe el Machine ID a su proveedor para recibir la llave de activación."
LLAVE_VACIA = "Pegue la llave de activación en el campo de texto."


class LicenciaActivable(Protocol):
    machine_id: str
    motivo_de_rechazo: MotivoDeRechazo | None

    def activate_license(self, key_input: str) -> bool: ...

    def get_tier(self) -> str: ...

    def get_max_cameras(self) -> int: ...

    def get_expiration_date(self) -> str | None: ...


class VentanaDeLicencia(ctk.CTkToplevel):
    def __init__(self, raiz: ctk.CTk, licencia: LicenciaActivable) -> None:
        super().__init__(raiz)
        self._licencia = licencia
        self.activada = False
        self.title("Activación de la licencia")
        self.geometry("620x520")
        self.configure(fg_color=COLOR_FONDO)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.grab_set()
        self.focus_force()
        self._crear_encabezado(licencia.motivo_de_rechazo)
        self.campo_machine_id = self._crear_machine_id()
        self.campo_de_llave = self._crear_campo_de_llave()
        ctk.CTkButton(
            self, text="Activar", fg_color=COLOR_EXITO, height=40, command=self.activar
        ).pack(pady=10)
        self.estado = ctk.CTkLabel(self, text="", font=("Roboto", 13), text_color=COLOR_TEXTO)
        self.estado.pack(pady=5)

    def _crear_encabezado(self, motivo: MotivoDeRechazo | None) -> None:
        titulo = TITULO_VENCIDA if motivo is MotivoDeRechazo.VENCIDA else TITULO_REQUERIDA
        explicacion = EXPLICACIONES.get(motivo, EXPLICACION_POR_OMISION)
        ctk.CTkLabel(self, text=titulo, font=("Roboto", 22, "bold"), text_color=COLOR_ERROR).pack(
            pady=(15, 5)
        )
        ctk.CTkLabel(
            self, text=explicacion, font=("Roboto", 12), text_color=COLOR_TEXTO, wraplength=560
        ).pack(pady=5)

    def _crear_machine_id(self) -> ctk.CTkEntry:
        marco = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        marco.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(marco, text="Machine ID de este equipo:", text_color=COLOR_TEXTO).pack(
            pady=(8, 2), padx=10, anchor="w"
        )
        campo = ctk.CTkEntry(marco, justify="center", font=("Consolas", 11), height=32)
        campo.insert(0, self._licencia.machine_id)
        campo.configure(state="readonly")
        campo.pack(pady=(0, 10), fill="x", padx=10)
        ctk.CTkButton(marco, text="Copiar Machine ID", command=self.copiar_machine_id).pack(
            pady=(0, 10)
        )
        return campo

    def _crear_campo_de_llave(self) -> ctk.CTkTextbox:
        marco = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        marco.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(marco, text="Pegue la llave de activación:", text_color=COLOR_TEXTO).pack(
            pady=(8, 2), padx=10, anchor="w"
        )
        campo = ctk.CTkTextbox(marco, height=80, font=("Consolas", 10), fg_color=COLOR_FONDO)
        campo.pack(fill="x", padx=10, pady=(0, 10))
        return campo

    def copiar_machine_id(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self._licencia.machine_id)

    def activar(self) -> None:
        llave = self.campo_de_llave.get("1.0", "end").strip()
        if not llave:
            self.estado.configure(text=LLAVE_VACIA, text_color=COLOR_ERROR)
            return
        if not self._licencia.activate_license(llave):
            motivo = self._licencia.motivo_de_rechazo or MotivoDeRechazo.INVALIDA
            self.estado.configure(text=motivo.value, text_color=COLOR_ERROR)
            return
        self.activada = True
        self.estado.configure(text=self._alcance(), text_color=COLOR_EXITO)
        self.after(ESPERA_AL_ACTIVAR_MS, self.destroy)

    def _alcance(self) -> str:
        vence = self._licencia.get_expiration_date() or "N/D"
        return (
            f"Licencia activada | Tipo: {self._licencia.get_tier().upper()} | "
            f"Cámaras: {self._licencia.get_max_cameras()} | Vence: {vence}"
        )

    def cerrar(self) -> None:
        """Cierra sin activar: quien abrió la ventana decide qué hacer sin licencia."""
        self.destroy()


def pedir_licencia(raiz: ctk.CTk, licencia: LicenciaActivable) -> bool:
    """Muestra la ventana y espera a que se cierre; True si quedó una licencia activada."""
    ventana = VentanaDeLicencia(raiz, licencia)
    raiz.wait_window(ventana)
    return ventana.activada
