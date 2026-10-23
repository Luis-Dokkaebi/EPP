"""Vista del panel "Alertas EPP" (SPEC/9 §8.2): delgada, toda la lógica está en el presentador.

Muestra cada alerta con su miniatura, el filtro por zona y el botón "Recibido", y se refresca
cada `intervalo_ms` milisegundos (lista en vivo). Al destruirse cancela el refresco pendiente.
"""

from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.gui.presentador_alertas import FilaAlerta, PresentadorAlertas

TAMANO_MINIATURA = (96, 72)


class PanelAlertas(ctk.CTkFrame):
    """Lista de alertas de EPP con acuse de recibo."""

    actualizacion_pendiente: str | None

    def __init__(
        self, master: ctk.CTkBaseClass, presentador: PresentadorAlertas, intervalo_ms: int
    ) -> None:
        super().__init__(master)
        self._presentador = presentador
        self._intervalo_ms = intervalo_ms
        self._filtro = ctk.CTkOptionMenu(self, values=presentador.zonas, command=self.filtrar)
        self._filtro.pack(anchor="w")
        self._mensaje = ctk.CTkLabel(self)
        self._mensaje.pack(anchor="w")
        self.lista = ctk.CTkScrollableFrame(self)
        self.lista.pack(fill="both", expand=True)
        self.refrescar()

    def refrescar(self) -> None:
        self._presentador.actualizar()
        self._mostrar()
        self.actualizacion_pendiente = self.after(self._intervalo_ms, self.refrescar)

    def filtrar(self, zona: str) -> None:
        self._presentador.filtrar_por_zona(zona)
        self._mostrar()

    def destroy(self) -> None:
        if self.actualizacion_pendiente is not None:
            self.after_cancel(self.actualizacion_pendiente)
            self.actualizacion_pendiente = None
        super().destroy()

    def _recibir(self, id_infraccion: int) -> None:
        self._presentador.marcar_recibido(id_infraccion)
        self._mostrar()

    def _mostrar(self) -> None:
        self._filtro.configure(values=self._presentador.zonas)
        self._mensaje.configure(text=self._presentador.mensaje or "")
        for widget in self.lista.winfo_children():
            widget.destroy()
        for fila in self._presentador.filas:
            self._mostrar_fila(fila)

    def _mostrar_fila(self, fila: FilaAlerta) -> None:
        marco = ctk.CTkFrame(self.lista)
        marco.pack(fill="x")
        miniatura = _miniatura(fila.miniatura)
        texto_miniatura = "" if miniatura else "sin imagen"
        ctk.CTkLabel(marco, image=miniatura, text=texto_miniatura).pack(side="left")
        datos = f"{fila.hora} · {fila.persona} · {fila.zona} · sin {fila.elemento} · {fila.aviso}"
        ctk.CTkLabel(marco, text=datos).pack(side="left")
        if fila.recibido is not None:
            ctk.CTkLabel(marco, text=fila.recibido).pack(side="right")
            return
        boton = ctk.CTkButton(
            marco, text="Recibido", command=lambda: self._recibir(fila.id_infraccion)
        )
        boton.pack(side="right")


def _miniatura(ruta: str | None) -> ctk.CTkImage | None:
    if ruta is None or not Path(ruta).is_file():
        return None
    with Image.open(ruta) as imagen:
        imagen.thumbnail(TAMANO_MINIATURA)
        return ctk.CTkImage(light_image=imagen.copy(), size=imagen.size)
