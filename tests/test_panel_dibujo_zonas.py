"""Vista para dibujar zonas sobre la foto de la cámara, con Tk real (SPEC/9 §8.3, §8.5).

Integración: necesita una pantalla (el gate corre la suite bajo xvfb). La lógica se prueba en
test_presentador_dibujo_zonas.py; aquí se verifica que la vista muestre lo que dice el
presentador y le pase los clics y los botones.
"""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import customtkinter as ctk
import numpy as np
import pytest

from src.gui import panel_dibujo_zonas
from src.gui.panel_dibujo_zonas import SIN_ZONAS, PanelDibujoZonas
from src.gui.presentador_dibujo_zonas import PresentadorDibujoZonas
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import escribir_zonas, leer_zonas

pytestmark = pytest.mark.integration

CUADRADO = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
CASCO = frozenset({ElementoEPP.CASCO})
FOTO = np.zeros((900, 1600, 3), dtype=np.uint8)
ESQUINAS_DEL_TRIANGULO = 3


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


@pytest.fixture
def ruta(tmp_path: Path) -> Path:
    return tmp_path / "zonas_config.json"


class Confirmacion:
    def __init__(self, respuesta: bool) -> None:
        self.respuesta = respuesta
        self.preguntadas: list[str] = []

    def __call__(self, nombre: str) -> bool:
        self.preguntadas.append(nombre)
        return self.respuesta


def _panel(
    raiz: ctk.CTk, ruta: Path, foto: np.ndarray | None = FOTO, confirmar: bool = True
) -> PanelDibujoZonas:
    presentador = PresentadorDibujoZonas(ruta, lambda: foto, (800, 450), lambda: None)
    return PanelDibujoZonas(raiz, presentador, Confirmacion(confirmar))


def _hijos(widget: ctk.CTkBaseClass) -> list[ctk.CTkBaseClass]:
    return [h for hijo in widget.winfo_children() for h in (hijo, *_hijos(hijo))]


def _boton(panel: PanelDibujoZonas, texto: str) -> ctk.CTkButton:
    (boton,) = (
        h for h in _hijos(panel) if isinstance(h, ctk.CTkButton) and h.cget("text") == texto
    )
    return boton


def _textos(panel: PanelDibujoZonas) -> list[str]:
    return [h.cget("text") for h in _hijos(panel) if isinstance(h, ctk.CTkLabel)]


def _items(panel: PanelDibujoZonas, tipo: str) -> list[int]:
    return [item for item in panel.lienzo.find_all() if panel.lienzo.type(item) == tipo]


def _marcar_triangulo(panel: PanelDibujoZonas) -> None:
    panel.clic(SimpleNamespace(x=0, y=0))
    panel.clic(SimpleNamespace(x=100, y=0))
    panel.clic(SimpleNamespace(x=100, y=50))


def test_sin_imagen_de_la_camara_lo_explica_y_no_dibuja(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta, foto=None)

    _boton(panel, "Tomar foto de la cámara").invoke()

    assert "Todavía no hay imagen de la cámara: conéctela y espere a ver el video" in _textos(panel)
    assert panel.lienzo.find_all() == ()


def test_la_foto_se_muestra_reducida_en_el_lienzo(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)

    _boton(panel, "Tomar foto de la cámara").invoke()

    assert len(_items(panel, "image")) == 1
    assert (int(panel.lienzo.cget("width")), int(panel.lienzo.cget("height"))) == (800, 450)


def test_el_lienzo_pasa_los_clics_al_presentador(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    _boton(panel, "Tomar foto de la cámara").invoke()

    _marcar_triangulo(panel)

    assert panel.lienzo.bind("<Button-1>")
    assert len(_items(panel, "oval")) == ESQUINAS_DEL_TRIANGULO
    assert len(_items(panel, "polygon")) == 1


def test_deshacer_y_limpiar_quitan_esquinas_del_dibujo(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    _boton(panel, "Tomar foto de la cámara").invoke()
    _marcar_triangulo(panel)

    _boton(panel, "Deshacer esquina").invoke()
    tras_deshacer = len(_items(panel, "oval"))
    _boton(panel, "Limpiar").invoke()

    assert tras_deshacer == ESQUINAS_DEL_TRIANGULO - 1
    assert _items(panel, "oval") == []


def test_guardar_escribe_la_zona_la_lista_y_limpia_el_nombre(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    _boton(panel, "Tomar foto de la cámara").invoke()
    _marcar_triangulo(panel)
    panel.nombre.insert(0, "Taller")

    _boton(panel, "Guardar zona").invoke()

    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Taller"]
    assert panel.seleccion.get() == "Taller"
    assert panel.nombre.get() == ""
    assert len(_items(panel, "text")) == 1


def test_guardar_con_error_conserva_el_nombre_escrito(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    _boton(panel, "Tomar foto de la cámara").invoke()
    panel.nombre.insert(0, "Taller")

    _boton(panel, "Guardar zona").invoke()

    assert panel.nombre.get() == "Taller"
    assert "Marque al menos 3 esquinas antes de guardar" in _textos(panel)


def test_borrar_pide_confirmacion_y_quita_la_zona(raiz: ctk.CTk, ruta: Path) -> None:
    escribir_zonas(ruta, [ReglaZona("Taller", CUADRADO, CASCO)])
    panel = _panel(raiz, ruta)

    _boton(panel, "Borrar zona").invoke()

    assert leer_zonas(ruta) == ()
    assert panel.seleccion.get() == SIN_ZONAS


def test_borrar_sin_confirmar_no_toca_la_zona(raiz: ctk.CTk, ruta: Path) -> None:
    escribir_zonas(ruta, [ReglaZona("Taller", CUADRADO, CASCO)])
    panel = _panel(raiz, ruta, confirmar=False)

    _boton(panel, "Borrar zona").invoke()

    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Taller"]


def test_sin_zonas_borrar_no_pregunta_nada(raiz: ctk.CTk, ruta: Path) -> None:
    presentador = PresentadorDibujoZonas(ruta, lambda: FOTO, (800, 450), lambda: None)
    confirmacion = Confirmacion(respuesta=True)
    panel = PanelDibujoZonas(raiz, presentador, confirmacion)

    _boton(panel, "Borrar zona").invoke()

    assert confirmacion.preguntadas == []


def test_la_confirmacion_de_borrado_pregunta_por_la_zona(monkeypatch: pytest.MonkeyPatch) -> None:
    preguntas: list[tuple[str, str]] = []

    def responder(titulo: str, texto: str) -> bool:
        preguntas.append((titulo, texto))
        return False

    monkeypatch.setattr(panel_dibujo_zonas.messagebox, "askyesno", responder)

    respuesta = panel_dibujo_zonas.confirmar_borrado("Taller")

    assert respuesta is False
    assert preguntas == [
        ("Borrar zona", "¿Borrar la zona 'Taller' y el EPP que exige? No se puede deshacer.")
    ]


# --- Cómo se dibuja (posición, tamaño y color de cada trazo) -------------------------------------

RADIO = 4
MARGEN_DEL_NOMBRE = 5
GROSOR = "2.0"
AZUL_BGR = (255, 0, 0)


def test_al_abrir_muestra_titulo_mensaje_vacio_y_lista_sin_zonas(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)

    assert _textos(panel)[:2] == ["Dibujar zonas sobre la cámara", ""]
    assert panel.seleccion.get() == "(sin zonas)"
    assert panel.nombre.cget("placeholder_text") == "Nombre de la zona"
    assert panel.nombre.pack_info()["padx"] == MARGEN_DEL_NOMBRE
    assert int(panel.lienzo.cget("highlightthickness")) == 0


def test_la_foto_se_dibuja_desde_la_esquina_con_los_colores_de_la_camara(
    raiz: ctk.CTk, ruta: Path
) -> None:
    foto = np.full((90, 160, 3), AZUL_BGR, dtype=np.uint8)
    panel = _panel(raiz, ruta, foto=foto)

    panel.tomar_foto()

    (imagen,) = _items(panel, "image")
    nombre_tk = panel.lienzo.itemcget(imagen, "image")
    assert panel.lienzo.coords(imagen) == [0.0, 0.0]
    assert panel.lienzo.tk.call(nombre_tk, "get", 0, 0) == (0, 0, 255)


def test_cada_esquina_es_un_circulo_centrado_en_el_clic(raiz: ctk.CTk, ruta: Path) -> None:
    panel = _panel(raiz, ruta)
    panel.tomar_foto()

    panel.clic(SimpleNamespace(x=50, y=60))

    (esquina,) = _items(panel, "oval")
    assert panel.lienzo.coords(esquina) == [50 - RADIO, 60 - RADIO, 50 + RADIO, 60 + RADIO]


def test_la_zona_en_curso_y_las_guardadas_se_trazan_con_grosor_2_y_su_nombre(
    raiz: ctk.CTk, ruta: Path
) -> None:
    escribir_zonas(ruta, [ReglaZona("Taller", ((200.0, 100.0), *CUADRADO[1:]), CASCO)])
    panel = _panel(raiz, ruta)
    panel.tomar_foto()
    _marcar_triangulo(panel)

    guardada, en_curso = _items(panel, "polygon")
    (rotulo,) = _items(panel, "text")
    assert panel.lienzo.itemcget(guardada, "width") == GROSOR
    assert panel.lienzo.itemcget(en_curso, "width") == GROSOR
    assert panel.lienzo.coords(rotulo) == [100.0, 50.0]
