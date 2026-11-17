"""Importar la carpeta de rostros desde la pantalla de empleados (SPEC/10 T-15).

Une la carga masiva con consentimiento (`src/recognition/importacion_rostros.py`) con el
reconocedor de rostros y la base de la sucursal abierta, y deja la bitácora en su carpeta.
"""

import getpass
import tkinter.filedialog
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from config.path_utils import ConfigManager
from src.recognition.importacion_rostros import (
    BitacoraDeImportaciones,
    ImportacionInvalidaError,
    importar_rostros,
    resumen,
)

ARCHIVO_DE_BITACORA = "importaciones_rostros.csv"
TITULO_DEL_DIALOGO = "Carpeta de rostros con consentimientos.csv"


class Rostros(Protocol):
    def register_face_burst(self, image_paths: list[str], name: str) -> int: ...


class BaseDeEmpleados(Protocol):
    def employee_exists(self, name: str) -> bool: ...

    def save_employee_profile(self, name: str, department: str, position: str) -> None: ...


class RegistroDeLaSucursal:
    """El rostro va al reconocedor y el perfil a la base, solo si se encontró un rostro."""

    def __init__(self, rostros: Rostros, base: BaseDeEmpleados) -> None:
        self._rostros = rostros
        self._base = base

    def ya_registrado(self, nombre: str) -> bool:
        return bool(self._base.employee_exists(nombre))

    def registrar(self, nombre: str, fotos: list[Path]) -> int:
        con_rostro = self._rostros.register_face_burst([str(foto) for foto in fotos], nombre)
        if con_rostro > 0:
            self._base.save_employee_profile(nombre, "", "")
        return con_rostro


def importar_carpeta_de_rostros(carpeta: Path, rostros: Rostros, base: BaseDeEmpleados) -> str:
    """Carga la carpeta y devuelve el mensaje para la pantalla de empleados."""
    bitacora = BitacoraDeImportaciones(
        Path(ConfigManager.get_tenant_path()) / ARCHIVO_DE_BITACORA,
        getpass.getuser(),
        lambda: datetime.now(UTC),
    )
    try:
        return resumen(importar_rostros(carpeta, RegistroDeLaSucursal(rostros, base), bitacora))
    except ImportacionInvalidaError as error:
        return str(error)


def elegir_e_importar(rostros: Rostros, base: BaseDeEmpleados) -> str | None:
    """Pide la carpeta al operador y la carga; None si canceló la elección."""
    carpeta = tkinter.filedialog.askdirectory(title=TITULO_DEL_DIALOGO)
    if not carpeta:
        return None
    return importar_carpeta_de_rostros(Path(carpeta), rostros, base)
