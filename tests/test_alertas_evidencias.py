"""Lectura de la imagen que acompaña al aviso (SPEC/9 §4.6, AC-015; CLAUDE.md §9).

Solo se leen imágenes de la carpeta de evidencias del tenant. Si la imagen falta (por ejemplo,
porque la retención ya la purgó) o la referencia apunta fuera de la carpeta, el aviso sale igual
sin imagen: un aviso de seguridad no se retiene por su adjunto.
"""

import logging
from pathlib import Path

import pytest

from src.alerts.evidencias import LectorEvidencias

JPEG = b"\xff\xd8\xff\xe0 imagen \xff\xd9"


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    carpeta = tmp_path / "snapshots"
    (carpeta / "epp").mkdir(parents=True)
    (carpeta / "epp" / "1.jpg").write_bytes(JPEG)
    return carpeta


def test_lector_devuelve_la_imagen_de_la_carpeta_de_evidencias(carpeta: Path) -> None:
    lector = LectorEvidencias(carpeta)

    imagen = lector.leer(str(carpeta / "epp" / "1.jpg"))

    assert imagen == JPEG


def test_lector_sin_referencia_no_devuelve_imagen(carpeta: Path) -> None:
    assert LectorEvidencias(carpeta).leer(None) is None


def test_lector_con_la_imagen_purgada_avisa_y_no_devuelve_imagen(
    carpeta: Path, caplog: pytest.LogCaptureFixture
) -> None:
    referencia = str(carpeta / "epp" / "purgada.jpg")

    with caplog.at_level(logging.WARNING):
        imagen = LectorEvidencias(carpeta).leer(referencia)

    assert imagen is None
    assert caplog.messages == [f"La imagen del aviso ya no existe: {referencia}"]


@pytest.mark.parametrize(
    "relativa",
    ["../afuera.jpg", "epp/../../afuera.jpg"],
    ids=["hermana", "con-retroceso"],
)
def test_lector_no_lee_fuera_de_la_carpeta_y_lo_registra_como_error(
    carpeta: Path, relativa: str, caplog: pytest.LogCaptureFixture
) -> None:
    (carpeta.parent / "afuera.jpg").write_bytes(JPEG)
    referencia = str(carpeta / relativa)

    with caplog.at_level(logging.WARNING):
        imagen = LectorEvidencias(carpeta).leer(referencia)

    assert imagen is None
    assert [registro.levelno for registro in caplog.records] == [logging.ERROR]
    assert caplog.messages == [
        f"Imagen fuera de la carpeta de evidencias, no se adjunta: {referencia}"
    ]
