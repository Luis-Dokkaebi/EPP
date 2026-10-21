"""Harness (AC-020): las dependencias quedan fijadas por versión (CLAUDE.md §14.11).

Si una prueba de este módulo falla, el mensaje indica cómo corregir el archivo de requisitos.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS_REQUISITOS = ["requirements.txt", "requirements-dev.txt", "requirements-ci.txt"]
PATRON_FIJADO = re.compile(r"^[A-Za-z0-9_.\-\[\]]+==[^=;\s]+(\s*;\s*\S.*)?$")
SEPARADOR_NOMBRE = re.compile(r"[=;\s\[]")


def _lineas_de_requisitos(nombre: str) -> list[str]:
    lineas = (RAIZ / nombre).read_text(encoding="utf-8").splitlines()
    return [linea.strip() for linea in lineas if _es_requisito(linea.strip())]


def _es_requisito(linea: str) -> bool:
    return bool(linea) and not linea.startswith(("#", "-"))


def _lineas_sin_fijar(nombre: str) -> list[str]:
    return [linea for linea in _lineas_de_requisitos(nombre) if not PATRON_FIJADO.match(linea)]


def _versiones(nombre: str) -> dict[str, str]:
    versiones = {}
    for linea in _lineas_de_requisitos(nombre):
        paquete = SEPARADOR_NOMBRE.split(linea, maxsplit=1)[0].lower()
        version = linea.partition("==")[2].split(";", 1)[0].strip()
        versiones[paquete] = version.split("+", 1)[0]
    return versiones


def _versiones_distintas(base: str, derivado: str) -> dict[str, tuple[str, str]]:
    runtime = _versiones(base)
    return {
        paquete: (runtime[paquete], version)
        for paquete, version in _versiones(derivado).items()
        if paquete in runtime and runtime[paquete] != version
    }


@pytest.mark.parametrize("nombre", ARCHIVOS_REQUISITOS)
def test_requisitos_toda_dependencia_esta_fijada_con_doble_igual(nombre: str) -> None:
    sin_fijar = _lineas_sin_fijar(nombre)

    assert sin_fijar == [], (
        f"{nombre}: fija la versión exacta con '==' (CLAUDE.md §14.11) y corre pip-audit: "
        f"{sin_fijar}"
    )


def test_requisitos_ci_usan_las_mismas_versiones_que_el_runtime() -> None:
    distintas = _versiones_distintas("requirements.txt", "requirements-ci.txt")

    assert distintas == {}, (
        "requirements-ci.txt debe repetir las versiones de requirements.txt "
        f"(runtime, ci): {distintas}"
    )


def _lineas_del_paquete(nombre: str, paquete: str) -> list[str]:
    return [linea for linea in _lineas_de_requisitos(nombre) if linea.startswith(paquete)]


def test_requisitos_wmi_solo_se_instala_en_windows() -> None:
    lineas_wmi = _lineas_del_paquete("requirements.txt", "wmi")

    assert lineas_wmi == [
        'wmi==1.5.1; sys_platform == "win32"'
    ], 'wmi solo existe en Windows: usa el marcador `; sys_platform == "win32"`'
