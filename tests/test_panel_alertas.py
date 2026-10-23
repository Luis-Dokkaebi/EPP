"""Vista delgada del panel "Alertas EPP" con Tk real (SPEC/9 §8.2, §8.5).

Integración: necesita una pantalla (el gate corre la suite bajo xvfb). La lógica se prueba en
test_presentador_alertas.py; aquí solo se verifica que la vista muestre lo que dice el
presentador y le pase los clics.
"""

from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import customtkinter as ctk
import pytest
from PIL import Image

from src.gui.panel_alertas import PanelAlertas
from src.gui.presentador_alertas import PreferenciasPanel, PresentadorAlertas
from tests.dobles_alertas import RepositorioAlertasFalso, alerta_registrada
from tests.dobles_ppe import RelojFalso

pytestmark = pytest.mark.integration

PREFERENCIAS = PreferenciasPanel(usuario="Supervisora", zona_horaria=UTC, limite=10)
UNA_HORA_EN_MS = 3_600_000


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


def _textos(widget: ctk.CTkBaseClass) -> list[str]:
    """Textos de todas las etiquetas y botones dentro de `widget`, en orden."""
    textos = []
    for hijo in widget.winfo_children():
        if isinstance(hijo, ctk.CTkLabel | ctk.CTkButton):
            textos.append(hijo.cget("text"))
        textos.extend(_textos(hijo))
    return textos


def _botones(widget: ctk.CTkBaseClass) -> list[ctk.CTkButton]:
    botones = [hijo for hijo in widget.winfo_children() if isinstance(hijo, ctk.CTkButton)]
    for hijo in widget.winfo_children():
        botones.extend(_botones(hijo))
    return botones


def _botones_recibido(panel: PanelAlertas) -> list[str]:
    return [boton.cget("text") for boton in _botones(panel) if boton.cget("text") == "Recibido"]


def _panel(raiz: ctk.CTk, repositorio: RepositorioAlertasFalso) -> PanelAlertas:
    presentador = PresentadorAlertas(repositorio, RelojFalso(), PREFERENCIAS)
    panel = PanelAlertas(raiz, presentador, intervalo_ms=UNA_HORA_EN_MS)
    raiz.update_idletasks()
    return panel


def test_panel_muestra_una_fila_por_alerta_con_su_boton_de_recibido(raiz: ctk.CTk) -> None:
    repositorio = RepositorioAlertasFalso(alerta_registrada(1), alerta_registrada(2, persona=None))

    panel = _panel(raiz, repositorio)

    textos = _textos(panel)
    assert "22/10 08:00:00 · Ana · Boca de pozo · sin casco · Aviso pendiente" in textos
    assert (
        "22/10 08:00:00 · persona no identificada · Boca de pozo · sin casco · Aviso pendiente"
        in textos
    )
    assert _botones_recibido(panel) == ["Recibido"] * 2


def test_panel_el_boton_recibido_acusa_recibo_y_lo_muestra(raiz: ctk.CTk) -> None:
    repositorio = RepositorioAlertasFalso(alerta_registrada(1))
    panel = _panel(raiz, repositorio)
    (boton,) = (boton for boton in _botones(panel) if boton.cget("text") == "Recibido")

    boton.invoke()

    assert [acuse[:2] for acuse in repositorio.acuses] == [(1, "Supervisora")]
    assert "Recibido por Supervisora a las 08:00" in _textos(panel)
    assert "Recibido" not in _textos(panel)


def test_panel_muestra_la_miniatura_si_la_imagen_existe(raiz: ctk.CTk, tmp_path: Path) -> None:
    imagen = tmp_path / "1.jpg"
    Image.new("RGB", (64, 48), "red").save(imagen)
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1)._replace(evidencia=str(imagen)), alerta_registrada(2)
    )

    panel = _panel(raiz, repositorio)

    # El primer texto es el aviso (vacío), el segundo la miniatura que sí existe y el último el
    # rótulo vacío de la lista desplazable.
    assert _textos(panel) == [
        "",
        "",
        "22/10 08:00:00 · Ana · Boca de pozo · sin casco · Aviso pendiente",
        "Recibido",
        "sin imagen",
        "22/10 08:00:00 · Ana · Boca de pozo · sin casco · Aviso pendiente",
        "Recibido",
        "",
    ]


def _tamanos_de_miniatura(widget: ctk.CTkBaseClass) -> list[tuple[int, int]]:
    tamanos = []
    for hijo in widget.winfo_children():
        imagen = hijo.cget("image") if isinstance(hijo, ctk.CTkLabel) else None
        if isinstance(imagen, ctk.CTkImage):
            tamanos.append(imagen.cget("size"))
        tamanos.extend(_tamanos_de_miniatura(hijo))
    return tamanos


def test_panel_achica_la_miniatura_sin_deformarla(raiz: ctk.CTk, tmp_path: Path) -> None:
    apaisada, vertical = tmp_path / "apaisada.jpg", tmp_path / "vertical.jpg"
    Image.new("RGB", (200, 100), "red").save(apaisada)
    Image.new("RGB", (100, 200), "red").save(vertical)
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1)._replace(evidencia=str(apaisada)),
        alerta_registrada(2)._replace(evidencia=str(vertical)),
    )

    panel = _panel(raiz, repositorio)

    assert _tamanos_de_miniatura(panel) == [(96, 48), (36, 72)]


def test_panel_filtra_por_la_zona_elegida(raiz: ctk.CTk) -> None:
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1), alerta_registrada(2, zona="Playa de tanques")
    )
    panel = _panel(raiz, repositorio)

    panel.filtrar("Playa de tanques")

    assert repositorio.consultas[-1] == ("Playa de tanques", 10)
    assert _botones_recibido(panel) == ["Recibido"]


def _pendientes(raiz: ctk.CTk) -> tuple[str, ...]:
    return tuple(raiz.tk.splitlist(raiz.tk.call("after", "info")))


def test_panel_programa_su_proxima_actualizacion(raiz: ctk.CTk) -> None:
    panel = _panel(raiz, RepositorioAlertasFalso())

    assert panel.actualizacion_pendiente in _pendientes(raiz)


def test_panel_al_destruirse_cancela_la_actualizacion_periodica(raiz: ctk.CTk) -> None:
    panel = _panel(raiz, RepositorioAlertasFalso())
    programada = panel.actualizacion_pendiente

    panel.destroy()

    assert programada not in _pendientes(raiz)
    assert panel.actualizacion_pendiente is None


def test_panel_muestra_el_aviso_del_presentador(raiz: ctk.CTk) -> None:
    ya_reconocida = alerta_registrada(1)._replace(reconocida_por="Jefe", reconocida_en=None)
    repositorio = RepositorioAlertasFalso(ya_reconocida)
    panel = _panel(raiz, repositorio)
    (boton,) = (boton for boton in _botones(panel) if boton.cget("text") == "Recibido")

    boton.invoke()

    assert _textos(panel)[0] == "La alerta 1 ya tenía acuse de recibo"
