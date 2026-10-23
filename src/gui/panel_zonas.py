"""Vista del editor de EPP por zona (SPEC/9 §8.3): delgada, la lógica está en el presentador.

Una fila por zona con una casilla por elemento ofrecido, y los botones "Guardar" y "Descartar
cambios". Los polígonos se dibujan con el editor de zonas; aquí solo se elige el EPP exigido.
"""

import customtkinter as ctk

from src.gui.presentador_zonas import FilaZona, PresentadorZonas


class PanelZonas(ctk.CTkFrame):
    """Casillas de EPP exigido por zona."""

    def __init__(self, master: ctk.CTkBaseClass, presentador: PresentadorZonas) -> None:
        super().__init__(master)
        self._presentador = presentador
        ctk.CTkLabel(self, text="Zonas y EPP exigido").pack(anchor="w")
        self._mensaje = ctk.CTkLabel(self)
        self._mensaje.pack(anchor="w")
        self._lista = ctk.CTkScrollableFrame(self)
        self._lista.pack(fill="both", expand=True)
        ctk.CTkButton(self, text="Guardar", command=self.guardar).pack(side="left")
        ctk.CTkButton(self, text="Descartar cambios", command=self.descartar).pack(side="left")
        self.descartar()

    def guardar(self) -> None:
        self._presentador.guardar()
        self._mostrar()

    def descartar(self) -> None:
        self._presentador.cargar()
        self._mostrar()

    def _mostrar(self) -> None:
        self._mensaje.configure(text=self._presentador.mensaje or "")
        for widget in self._lista.winfo_children():
            widget.destroy()
        for fila in self._presentador.filas:
            self._mostrar_fila(fila)

    def _mostrar_fila(self, fila: FilaZona) -> None:
        marco = ctk.CTkFrame(self._lista)
        marco.pack(fill="x")
        ctk.CTkLabel(marco, text=fila.nombre).pack(side="left")
        for elemento, texto in self._presentador.casillas:
            casilla = ctk.CTkCheckBox(
                marco,
                text=texto,
                command=lambda e=elemento: self._presentador.alternar(fila.nombre, e),
            )
            if elemento in fila.exigidos:
                casilla.select()
            casilla.pack(side="left")
