"""Vista para dibujar zonas sobre una foto de la cámara (SPEC/9 §8.3): delgada.

Toda la lógica está en PresentadorDibujoZonas. La vista muestra la foto reducida en un lienzo,
pasa cada clic al presentador y dibuja las zonas guardadas (amarillo) y las esquinas que se
están marcando (verde). Borrar una zona pide confirmación.
"""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Protocol

import customtkinter as ctk
from PIL import Image, ImageTk

from src.gui.presentador_dibujo_zonas import PresentadorDibujoZonas, PuntoEnVista

SIN_ZONAS = "(sin zonas)"
AMARILLO, VERDE, NEGRO = "#F1C40F", "#2ECC71", "#000000"
RADIO_ESQUINA = 4
VERTICES_PARA_CERRAR = 3


def confirmar_borrado(nombre: str) -> bool:
    return messagebox.askyesno(
        "Borrar zona", f"¿Borrar la zona '{nombre}' y el EPP que exige? No se puede deshacer."
    )


class ClicEnLienzo(Protocol):
    """Lo que la vista necesita de un evento de clic de Tk."""

    x: int
    y: int


class PanelDibujoZonas(ctk.CTkFrame):
    """Foto de la cámara, esquinas marcadas y botones para guardar o borrar zonas."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        presentador: PresentadorDibujoZonas,
        confirmar: Callable[[str], bool] = confirmar_borrado,
    ) -> None:
        super().__init__(master)
        self._presentador = presentador
        self._confirmar = confirmar
        self._imagen: ImageTk.PhotoImage | None = None
        ctk.CTkLabel(self, text="Dibujar zonas sobre la cámara").pack(anchor="w")
        acciones = ctk.CTkFrame(self)
        acciones.pack(fill="x")
        ctk.CTkButton(acciones, text="Tomar foto de la cámara", command=self.tomar_foto).pack(
            side="left"
        )
        self.nombre = ctk.CTkEntry(acciones, placeholder_text="Nombre de la zona")
        self.nombre.pack(side="left", padx=5)
        ctk.CTkButton(acciones, text="Guardar zona", command=self.guardar).pack(side="left")
        ctk.CTkButton(acciones, text="Deshacer esquina", command=self.deshacer).pack(side="left")
        ctk.CTkButton(acciones, text="Limpiar", command=self.limpiar).pack(side="left")
        existentes = ctk.CTkFrame(self)
        existentes.pack(fill="x")
        self.seleccion = ctk.CTkOptionMenu(existentes, values=[SIN_ZONAS])
        self.seleccion.pack(side="left")
        ctk.CTkButton(existentes, text="Borrar zona", command=self.borrar).pack(side="left")
        self._mensaje = ctk.CTkLabel(self, text="")
        self._mensaje.pack(anchor="w")
        self.lienzo = tk.Canvas(self, bg=NEGRO, highlightthickness=0)
        self.lienzo.pack(anchor="w")
        self.lienzo.bind("<Button-1>", self.clic)
        presentador.cargar()
        self._mostrar()

    def tomar_foto(self) -> None:
        self._presentador.tomar_foto()
        self._mostrar()

    def clic(self, evento: ClicEnLienzo) -> None:
        self._presentador.agregar_punto(evento.x, evento.y)
        self._mostrar()

    def guardar(self) -> None:
        self._presentador.guardar(self.nombre.get())
        if self._presentador.zona_guardada is not None:
            self.nombre.delete(0, "end")
        self._mostrar()

    def deshacer(self) -> None:
        self._presentador.deshacer()
        self._mostrar()

    def limpiar(self) -> None:
        self._presentador.limpiar()
        self._mostrar()

    def borrar(self) -> None:
        nombre = self.seleccion.get()
        if nombre == SIN_ZONAS or not self._confirmar(nombre):
            return
        self._presentador.borrar(nombre)
        self._mostrar()

    def _mostrar(self) -> None:
        self._mensaje.configure(text=self._presentador.mensaje or "")
        zonas = self._presentador.zonas or [SIN_ZONAS]
        self.seleccion.configure(values=zonas)
        if self.seleccion.get() not in zonas:
            self.seleccion.set(zonas[0])
        self._dibujar()

    def _dibujar(self) -> None:
        ancho, alto = self._presentador.tamano_vista
        self.lienzo.configure(width=ancho, height=alto)
        self.lienzo.delete("all")
        foto = self._presentador.foto
        if foto is None:
            return
        # Las cámaras entregan BGR; la imagen de Tk espera RGB.
        imagen = Image.fromarray(foto[:, :, ::-1]).resize((ancho, alto))
        self._imagen = ImageTk.PhotoImage(imagen, master=self.lienzo)
        self.lienzo.create_image(0, 0, image=self._imagen, anchor="nw")
        for nombre, poligono in self._presentador.poligonos_en_vista.items():
            self.lienzo.create_polygon(_plano(poligono), outline=AMARILLO, fill="", width=2)
            self.lienzo.create_text(*poligono[0], text=nombre, fill=AMARILLO, anchor="nw")
        self._dibujar_esquinas(self._presentador.puntos_en_vista)

    def _dibujar_esquinas(self, puntos: list[PuntoEnVista]) -> None:
        for x, y in puntos:
            self.lienzo.create_oval(
                x - RADIO_ESQUINA,
                y - RADIO_ESQUINA,
                x + RADIO_ESQUINA,
                y + RADIO_ESQUINA,
                fill=VERDE,
                outline=VERDE,
            )
        if len(puntos) >= VERTICES_PARA_CERRAR:
            self.lienzo.create_polygon(_plano(puntos), outline=VERDE, fill="", width=2)


def _plano(puntos: list[PuntoEnVista]) -> list[float]:
    return [coordenada for punto in puntos for coordenada in punto]
