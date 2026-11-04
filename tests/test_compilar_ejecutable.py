"""Build del ejecutable con Nuitka (reemplaza a PyInstaller + PyArmor)."""

import json
from pathlib import Path

import pytest

from scripts import compilar_ejecutable as compilar
from scripts.compilar_ejecutable import (
    PAQUETES_FUERA_DEL_EJECUTABLE,
    argumentos_de_nuitka,
    carpeta_del_ejecutable,
    main,
)
from tests.utilidades_scripts import RAIZ


def _raiz(tmp_path: Path, version: str = "2.0.0") -> Path:
    (tmp_path / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    return tmp_path


def test_compila_la_app_de_escritorio_como_carpeta_independiente(tmp_path: Path) -> None:
    argumentos = argumentos_de_nuitka("linux", _raiz(tmp_path))

    assert argumentos[:3] == ["-m", "nuitka", "--standalone"]
    assert argumentos[-1] == str(Path("src") / "main_ui.py")
    assert "--enable-plugin=tk-inter" in argumentos
    assert "--include-package=src" in argumentos
    assert "--include-package=config" in argumentos
    assert "--include-package-data=customtkinter" in argumentos


def test_empaqueta_los_modelos_y_la_version_en_la_misma_ruta_relativa(tmp_path: Path) -> None:
    """config.path_utils.get_resource_path resuelve 'models/...' y 'VERSION' junto al ejecutable."""
    argumentos = argumentos_de_nuitka("linux", _raiz(tmp_path))

    assert "--include-data-dir=models=models" in argumentos
    assert "--include-data-files=VERSION=VERSION" in argumentos


def test_no_sigue_imports_a_paquetes_de_desarrollo_ni_a_motores_retirados(tmp_path) -> None:
    argumentos = argumentos_de_nuitka("linux", _raiz(tmp_path))

    excluidos = {a.split("=", 1)[1] for a in argumentos if a.startswith("--nofollow-import-to=")}
    assert excluidos == set(PAQUETES_FUERA_DEL_EJECUTABLE)
    assert {"torch", "ultralytics", "face_recognition", "dlib", "tests", "ml", "tools"} <= excluidos


def test_en_windows_agrega_los_datos_del_producto_y_la_version(tmp_path: Path) -> None:
    argumentos = argumentos_de_nuitka("win32", _raiz(tmp_path, "2.1.0"))

    assert "--windows-console-mode=attach" in argumentos
    assert "--windows-product-version=2.1.0" in argumentos
    assert "--windows-file-version=2.1.0" in argumentos
    assert "--windows-product-name=Oficina Eficiencia" in argumentos
    assert "--output-filename=OficinaEficiencia_VMS.exe" in argumentos


def test_fuera_de_windows_no_usa_opciones_de_windows(tmp_path: Path) -> None:
    argumentos = argumentos_de_nuitka("linux", _raiz(tmp_path))

    assert not [a for a in argumentos if a.startswith("--windows-")]
    assert "--output-filename=OficinaEficiencia_VMS" in argumentos


def test_deja_el_resultado_y_el_informe_en_build_nuitka(tmp_path: Path) -> None:
    raiz = _raiz(tmp_path)

    argumentos = argumentos_de_nuitka("linux", raiz)

    assert f"--output-dir={Path('build') / 'nuitka'}" in argumentos
    assert f"--report={Path('build') / 'nuitka' / 'compilacion.xml'}" in argumentos
    assert carpeta_del_ejecutable(raiz) == raiz / "build" / "nuitka" / "main_ui.dist"


@pytest.mark.parametrize("version", ["", "2.0", "2.0.0-beta", "dos"])
def test_una_version_que_no_es_x_y_z_detiene_el_build(tmp_path: Path, version: str) -> None:
    with pytest.raises(compilar.VersionInvalidaError, match="VERSION"):
        argumentos_de_nuitka("win32", _raiz(tmp_path, version))


def test_main_corre_nuitka_con_el_mismo_interprete_desde_la_raiz(tmp_path, monkeypatch) -> None:
    raiz = _raiz(tmp_path)
    llamadas: list[tuple[list[str], Path]] = []

    def correr(comando: list[str], cwd: Path, check: bool) -> object:
        llamadas.append((comando, cwd))
        return object()

    monkeypatch.setattr(compilar.subprocess, "run", correr)

    codigo = main(["--raiz", str(raiz)])

    [(comando, carpeta)] = llamadas
    assert codigo == 0
    assert comando[0] == compilar.sys.executable
    assert comando[1:] == argumentos_de_nuitka(compilar.sys.platform, raiz)
    assert carpeta == raiz


def test_todos_los_modelos_del_manifiesto_quedan_dentro_de_lo_empaquetado() -> None:
    manifiesto = json.loads((RAIZ / "models" / "manifest.json").read_text(encoding="utf-8"))

    archivos = [Path(entrada["archivo"]) for entrada in manifiesto["modelos"]]

    assert archivos
    assert all(archivo.parts[0] == "models" and (RAIZ / archivo).is_file() for archivo in archivos)
