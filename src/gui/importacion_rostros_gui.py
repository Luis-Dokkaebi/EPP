"""Importar la carpeta de rostros desde la pantalla de empleados (SPEC/10 T-15).

Une la carga masiva con consentimiento (`src/recognition/importacion_rostros.py`) con el
reconocedor de rostros y la base de la sucursal abierta, y deja la bitácora en su carpeta.
"""

import getpass
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
