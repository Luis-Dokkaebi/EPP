"""Ficha visual de una ventana de customtkinter: qué muestra y cómo lo acomoda.

Las pruebas de una ventana comparan esta ficha con la esperada; así un cambio de texto, tamaño,
color o margen se nota sin mirar la pantalla.
"""

from typing import Any

import customtkinter as ctk

OPCIONES = ("text", "font", "height", "corner_radius", "justify", "wraplength", "fg_color")
EMPAQUE = ("padx", "pady", "fill", "anchor")
CON_HIJOS_PROPIOS = "CTkFrame"
SANGRIA = "  "


def _opciones(widget: Any) -> list[str]:
    opciones = []
    for opcion in OPCIONES:
        try:
            valor = widget.cget(opcion)
        except ValueError:
            continue
        if not isinstance(valor, ctk.CTkFont):  # la fuente por omisión no se compara
            opciones.append(f"{opcion}={valor!r}")
    return opciones


def ficha_visual(contenedor: Any, nivel: int = 0) -> list[str]:
    """Una línea por widget de customtkinter: tipo, opciones visibles y empaque, con sangría."""
    lineas: list[str] = []
    for hijo in contenedor.winfo_children():
        if not isinstance(hijo, ctk.CTkBaseClass):
            continue
        empaque = hijo.pack_info()
        partes = [type(hijo).__name__, *_opciones(hijo), "|"]
        partes.extend(f"{clave}={empaque[clave]!r}" for clave in EMPAQUE)
        lineas.append(SANGRIA * nivel + " ".join(partes))
        if type(hijo).__name__ == CON_HIJOS_PROPIOS:
            lineas.extend(ficha_visual(hijo, nivel + 1))
    return lineas
