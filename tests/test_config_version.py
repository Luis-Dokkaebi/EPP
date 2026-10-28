"""La versión del producto tiene una sola fuente: el archivo VERSION (SPEC/9 §15, 9.3).

Antes config.py tenía un respaldo "2.0.0" que contradecía al archivo (1.3.0) y escondía con
`except Exception: pass` cualquier falla al leerlo (CLAUDE.md P5).
"""

import re
from pathlib import Path

import pytest

from config import config
from config.config import VersionNoEncontradaError, leer_version
from tests.utilidades_scripts import RAIZ

VERSION_DEL_REPOSITORIO = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()


def test_la_aplicacion_muestra_la_version_del_archivo_version() -> None:
    assert config.VERSION == VERSION_DEL_REPOSITORIO


def test_el_instalador_declara_la_misma_version_que_el_archivo_version() -> None:
    instalador = (RAIZ / "setup_oficina.iss").read_text(encoding="utf-8")

    declarada = re.search(r'#define MyAppVersion "([^"]+)"', instalador)

    assert declarada is not None
    assert declarada.group(1) == VERSION_DEL_REPOSITORIO


def test_leer_version_devuelve_el_texto_sin_espacios_ni_saltos(tmp_path: Path) -> None:
    ruta = tmp_path / "VERSION"
    ruta.write_text(" 1.3.0\n", encoding="utf-8")

    assert leer_version(ruta) == "1.3.0"


def test_leer_version_sin_archivo_falla_con_un_error_claro(tmp_path: Path) -> None:
    with pytest.raises(VersionNoEncontradaError, match="No se encontró el archivo VERSION"):
        leer_version(tmp_path / "VERSION")


@pytest.mark.parametrize("contenido", ["", "  \n"], ids=["vacio", "solo_espacios"])
def test_leer_version_vacia_falla_con_un_error_claro(tmp_path: Path, contenido: str) -> None:
    ruta = tmp_path / "VERSION"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(VersionNoEncontradaError, match="está vacío"):
        leer_version(ruta)
