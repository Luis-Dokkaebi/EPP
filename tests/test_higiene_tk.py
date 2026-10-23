"""Higiene de Tk entre pruebas (issue #37).

Un objeto de Tk que queda en un ciclo de referencias lo libera el recolector de basura cuando
corre, y su __del__ llama a Tcl. Si eso pasa dentro de un hilo de trabajo (por ejemplo, el de la
exportación a Excel) mientras el hilo principal espera ese hilo, la llamada a Tcl queda esperando
al hilo principal y la prueba se cuelga: lo mostró la pila de la CI de Linux en
tkinter/font.py __del__. Por eso el conftest recolecta en el hilo principal después de cada
prueba que creó un intérprete Tk.
"""

import tkinter

import customtkinter as ctk
import pytest

from tests import higiene_tk

pytestmark = pytest.mark.integration


def test_crear_un_tk_cuenta_un_interprete() -> None:
    antes = higiene_tk.interpretes_creados()

    raiz = tkinter.Tk()
    raiz.destroy()

    assert higiene_tk.interpretes_creados() == antes + 1


def test_crear_un_ctk_tambien_cuenta_un_interprete() -> None:
    antes = higiene_tk.interpretes_creados()

    raiz = ctk.CTk()
    raiz.destroy()

    assert higiene_tk.interpretes_creados() == antes + 1


def test_instalar_dos_veces_no_cuenta_doble() -> None:
    higiene_tk.instalar()
    antes = higiene_tk.interpretes_creados()

    raiz = tkinter.Tk()
    raiz.destroy()

    assert higiene_tk.interpretes_creados() == antes + 1
