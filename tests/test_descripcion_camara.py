"""Cómo se nombra la cámara activa en la barra lateral.

Regresión (ensayo de la demo, SPEC/10): con una cámara IP el estado mostraba la URL RTSP entera,
con usuario y contraseña a la vista, y ensanchaba la barra lateral al doble.
"""

import pytest

from src.gui.descripcion_camara import LARGO_MAXIMO, describir_camara


@pytest.mark.parametrize(
    ("camara", "descripcion"),
    [
        (0, "índice 0"),
        (3, "índice 3"),
        ("rtsp://admin:Clave123@192.168.1.64:554/Streaming/Channels/101", "cámara IP 192.168.1.64"),
        ("rtsp://192.168.1.64/stream", "cámara IP 192.168.1.64"),
        ("http://camara-patio.local:8080/video", "cámara IP camara-patio.local"),
        ("C:\\videos\\patio.mp4", "archivo patio.mp4"),
        ("/datos/videos/patio.mp4", "archivo patio.mp4"),
        ("patio.mp4", "archivo patio.mp4"),
    ],
)
def test_la_camara_se_describe_sin_credenciales_ni_rutas(
    camara: int | str, descripcion: str
) -> None:
    assert describir_camara(camara) == descripcion


def test_la_descripcion_nunca_muestra_el_usuario_ni_la_contrasena() -> None:
    descripcion = describir_camara("rtsp://admin:Clave123@192.168.1.64:554/canal")

    assert "admin" not in descripcion
    assert "Clave123" not in descripcion


def test_un_nombre_largo_se_recorta_para_no_ensanchar_la_barra() -> None:
    larga = describir_camara("rtsp://" + "camara-del-patio-de-carga-norte" * 3 + ".empresa.local/x")
    en_el_limite = describir_camara("a" * (LARGO_MAXIMO - len("archivo ")))

    assert len(larga) == LARGO_MAXIMO
    assert larga.endswith("…")
    assert en_el_limite == "archivo " + "a" * (LARGO_MAXIMO - len("archivo "))


def test_una_url_sin_equipo_se_trata_como_archivo() -> None:
    assert describir_camara("rtsp:///canal") == "archivo canal"


def test_el_recorte_deja_treinta_y_cuatro_caracteres_con_puntos_suspensivos() -> None:
    descripcion = describir_camara("rtsp://camara-del-patio-de-carga-norte.empresa.local/x")

    assert descripcion == "cámara IP camara-del-patio-de-car…"
