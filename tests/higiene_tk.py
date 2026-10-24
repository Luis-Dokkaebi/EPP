"""Cuenta los intérpretes Tk que crean las pruebas (issue #37).

El conftest compara la cuenta antes y después de cada prueba: si la prueba creó un Tk, recolecta
la basura en el hilo principal para que ningún __del__ de Tk corra luego en un hilo de trabajo.
"""

import tkinter
from typing import Any
from unittest import mock

_estado = {"creados": 0, "instalado": False}


def interpretes_creados() -> int:
    return _estado["creados"]


def instalar() -> None:
    """Envuelve tkinter.Tk.__init__ (CTk lo hereda) una sola vez por proceso."""
    if _estado["instalado"]:
        return
    original = tkinter.Tk.__init__

    def contar_e_iniciar(self: tkinter.Tk, *argumentos: Any, **opciones: Any) -> None:
        _estado["creados"] += 1
        original(self, *argumentos, **opciones)

    # Queda instalado todo el proceso de pytest: no se detiene a propósito.
    mock.patch.object(tkinter.Tk, "__init__", contar_e_iniciar).start()
    _estado["instalado"] = True
