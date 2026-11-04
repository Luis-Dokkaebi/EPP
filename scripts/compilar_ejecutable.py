"""Compila la app de escritorio con Nuitka (Apache-2.0): Python a C, sin PyInstaller ni PyArmor.

El resultado es una carpeta independiente (build/nuitka/main_ui.dist) con el ejecutable, las
DLL y los modelos en las mismas rutas relativas que usa config.path_utils.get_resource_path.
El código compilado a C no viaja como bytecode, así que no hace falta ofuscarlo aparte.

Uso: python scripts/compilar_ejecutable.py [--raiz .]
     En Windows lo llama compilar_exe.bat; Nuitka descarga su compilador de C si falta.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

NOMBRE_DEL_EJECUTABLE = "OficinaEficiencia_VMS"
PRODUCTO = "Oficina Eficiencia"
PUNTO_DE_ENTRADA = Path("src") / "main_ui.py"
CARPETA_DE_SALIDA = Path("build") / "nuitka"
VERSION_VALIDA = re.compile(r"^\d+\.\d+\.\d+$")
# Desarrollo, entrenamiento y motores retirados: si algo los importa, no entran al ejecutable.
PAQUETES_FUERA_DEL_EJECUTABLE = (
    "dlib",
    "face_recognition",
    "ml",
    "pytest",
    "tests",
    "tools",
    "torch",
    "torchvision",
    "ultralytics",
)


class VersionInvalidaError(ValueError):
    """El archivo VERSION no tiene la forma X.Y.Z que exige Windows."""


def _version(raiz: Path) -> str:
    version = (raiz / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_VALIDA.match(version):
        raise VersionInvalidaError(f"VERSION debe ser X.Y.Z; tiene '{version}'.")
    return version


def _opciones_de_windows(version: str) -> list[str]:
    return [
        # attach: sin ventana de consola, pero muestra la salida si se abre desde una terminal.
        "--windows-console-mode=attach",
        f"--windows-product-name={PRODUCTO}",
        f"--windows-file-description={PRODUCTO}",
        f"--windows-product-version={version}",
        f"--windows-file-version={version}",
        f"--output-filename={NOMBRE_DEL_EJECUTABLE}.exe",
    ]


def argumentos_de_nuitka(sistema: str, raiz: Path) -> list[str]:
    """Argumentos de `python ...` para compilar en `sistema` (valor de sys.platform)."""
    version = _version(raiz)
    plataforma = (
        _opciones_de_windows(version)
        if sistema == "win32"
        else [f"--output-filename={NOMBRE_DEL_EJECUTABLE}"]
    )
    return [
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--include-package=src",
        "--include-package=config",
        "--include-package-data=customtkinter",
        "--include-data-dir=models=models",
        "--include-data-files=VERSION=VERSION",
        *(f"--nofollow-import-to={paquete}" for paquete in PAQUETES_FUERA_DEL_EJECUTABLE),
        f"--output-dir={CARPETA_DE_SALIDA}",
        f"--report={CARPETA_DE_SALIDA / 'compilacion.xml'}",
        *plataforma,
        str(PUNTO_DE_ENTRADA),
    ]


def carpeta_del_ejecutable(raiz: Path) -> Path:
    """Donde Nuitka deja la carpeta lista para el instalador."""
    return raiz / CARPETA_DE_SALIDA / f"{PUNTO_DE_ENTRADA.stem}.dist"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path())
    raiz = parser.parse_args(argv).raiz
    comando = [sys.executable, *argumentos_de_nuitka(sys.platform, raiz)]
    # S603: el intérprete actual con argumentos fijos armados arriba.
    subprocess.run(comando, cwd=raiz, check=True)  # noqa: S603
    sys.stdout.write(f"Ejecutable en {carpeta_del_ejecutable(raiz)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
