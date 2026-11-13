"""Qué modelo usa la app (SPEC/10 F-05).

Si en la carpeta de datos del equipo hay un modelo instalado con su `modelo.manifest` firmado por
el proveedor, rige ese (afinado para el cliente, motor ONNX). Si no, rige el que viaja dentro del
ejecutable. Un manifiesto instalado con firma inválida no cae al modelo del ejecutable: falla.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import config
from config.path_utils import ConfigManager
from src.models.manifiesto_aprobado import MODELOS_APROBADOS
from src.models.manifiesto_firmado import entrada_del_manifiesto, leer_manifiesto_firmado
from src.security.drm import LLAVE_PUBLICA_DEL_PROVEEDOR

CARPETA_DEL_MODELO = "modelo"
NOMBRE_DEL_MANIFIESTO = "modelo.manifest"
LLAVE_PUBLICA = LLAVE_PUBLICA_DEL_PROVEEDOR


@dataclass(frozen=True)
class ModeloDeLaApp:
    """Dónde está el modelo, con qué motor corre, qué hash se le exige y qué declara."""

    ruta: str
    motor: str
    aprobados: Mapping[str, str]
    leer_manifiesto: Callable[[], Mapping[str, Any]]


def _manifiesto_del_ejecutable() -> Mapping[str, Any]:
    contenido: Mapping[str, Any] = json.loads(Path(config.MANIFEST_PATH).read_text("utf-8"))
    return contenido


def resolver_modelo(carpeta: Path, llave_publica: bytes) -> ModeloDeLaApp:
    """El modelo instalado en `carpeta` si su manifiesto lleva la firma; si no hay, el embebido."""
    instalado = carpeta / NOMBRE_DEL_MANIFIESTO
    if not instalado.exists():
        return ModeloDeLaApp(
            config.MODEL_PATH,
            config.DETECTION_ENGINE,
            MODELOS_APROBADOS,
            _manifiesto_del_ejecutable,
        )
    manifiesto = leer_manifiesto_firmado(instalado, llave_publica)
    entrada = entrada_del_manifiesto(manifiesto)
    return ModeloDeLaApp(
        str(carpeta / entrada["archivo"]),
        entrada["motor"],
        {entrada["archivo"]: entrada["sha256"]},
        lambda: manifiesto,
    )


def modelo_de_la_app() -> ModeloDeLaApp:
    carpeta = Path(ConfigManager.get_appdata_path(CARPETA_DEL_MODELO))
    return resolver_modelo(carpeta, LLAVE_PUBLICA)
