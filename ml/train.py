"""Entrenamiento reproducible del modelo EPP, separado del producto (SPEC/9 §3.1, B-04).

El producto (src/) nunca importa ml/. El entrenador real (RF-DETR) se inyecta detrás de
`EntrenadorPort`; las pruebas usan un doble y ningún test entrena ni descarga pesos. Cada corrida
verifica el dataset contra su manifiesto y deja un registro con el SHA del código, la huella de
la configuración, la versión y la huella del dataset, las métricas y el sha256 de los pesos. El
artefacto se nombra con esos hashes y nunca se sobrescribe. Procedimiento humano:
docs/runbooks/entrenamiento.md.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from ml.manifiesto_dataset import huella_del_manifiesto, sha256_de, verificar_manifiesto

# RF-DETR: solo estos tamaños son Apache-2.0; Atto, Femto, Pico, XL y 2XL son PML 1.0 (SPEC/9 §3.1).
TAMANOS_APACHE = ("nano", "small", "medium", "large")
# rfdetr 1.11.2: patch_size 16 por num_windows 2 en nano, small, medium y large.
MULTIPLO_DE_RESOLUCION = 32
SHA_DE_CODIGO = re.compile(r"[0-9a-f]{40}")
CARACTERES_DE_HUELLA = 12
ARCHIVO_DE_REGISTRO = "registro.json"


class EntrenamientoInvalidoError(ValueError):
    """La corrida no cumple las condiciones de reproducibilidad; el mensaje dice qué falta."""


@dataclass(frozen=True)
class ConfigEntrenamiento:
    dataset: Path
    manifiesto: Path
    tamano: str
    resolucion: int
    epocas: int
    lote: int
    tasa_de_aprendizaje: float
    semilla: int

    def __post_init__(self) -> None:
        if self.tamano not in TAMANOS_APACHE:
            raise EntrenamientoInvalidoError(
                f'Tamaño "{self.tamano}" no permitido: solo nano, small, medium y large tienen '
                "licencia Apache-2.0 (los demás son PML 1.0, SPEC/9 §3.1)."
            )
        if self.resolucion <= 0 or self.resolucion % MULTIPLO_DE_RESOLUCION:
            raise EntrenamientoInvalidoError(
                f"Resolución {self.resolucion} inválida: debe ser un múltiplo positivo de 32 "
                "(parche 16 por 2 ventanas en RF-DETR, SPEC/9 §3.6)."
            )
        for campo, valido in (
            ("epocas", self.epocas >= 1),
            ("lote", self.lote >= 1),
            ("tasa_de_aprendizaje", math.isfinite(self.tasa_de_aprendizaje)),
            ("tasa_de_aprendizaje", self.tasa_de_aprendizaje > 0),
            ("semilla", self.semilla >= 0),
        ):
            if not valido:
                raise EntrenamientoInvalidoError(f'"{campo}" inválido: {getattr(self, campo)}.')


class ResultadoDelEntrenador(NamedTuple):
    pesos: Path
    metricas: dict[str, float]


class EntrenadorPort(Protocol):
    def entrenar(self, config: ConfigEntrenamiento, carpeta: Path) -> ResultadoDelEntrenador: ...


def campos_de_config(config: ConfigEntrenamiento) -> dict[str, Any]:
    """Hiperparámetros que definen la corrida; las rutas no, porque cambian entre equipos."""
    return {
        "tamano": config.tamano,
        "resolucion": config.resolucion,
        "epocas": config.epocas,
        "lote": config.lote,
        "tasa_de_aprendizaje": config.tasa_de_aprendizaje,
        "semilla": config.semilla,
    }


def huella_de_config(config: ConfigEntrenamiento, version: str, huella_dataset: str) -> str:
    campos = {**campos_de_config(config), "dataset_version": version}
    campos["dataset_huella"] = huella_dataset
    canonico = json.dumps(campos, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def nombre_de_artefacto(sha_codigo: str, huella_config: str) -> str:
    if SHA_DE_CODIGO.fullmatch(sha_codigo) is None:
        raise EntrenamientoInvalidoError(
            f'SHA de código "{sha_codigo}" inválido: se esperan 40 hexadecimales.'
        )
    return f"epp-{sha_codigo[:CARACTERES_DE_HUELLA]}-{huella_config[:CARACTERES_DE_HUELLA]}"


def entrenar(
    config: ConfigEntrenamiento, entrenador: EntrenadorPort, sha_codigo: str, salidas: Path
) -> dict[str, Any]:
    """Entrena con el dataset verificado y devuelve el registro que también guarda en disco."""
    manifiesto = json.loads(config.manifiesto.read_text(encoding="utf-8"))
    diferencias = verificar_manifiesto(config.dataset, manifiesto)
    if diferencias:
        raise EntrenamientoInvalidoError(
            "\n".join(["El dataset no coincide con su manifiesto:", *diferencias])
        )
    huella_dataset = huella_del_manifiesto(manifiesto)
    huella = huella_de_config(config, manifiesto["version"], huella_dataset)
    destino = salidas / nombre_de_artefacto(sha_codigo, huella)
    if destino.exists():
        raise EntrenamientoInvalidoError(
            f"{destino} ya existe: cambia la semilla o la configuración; nunca se sobrescribe."
        )
    destino.mkdir(parents=True)
    resultado = entrenador.entrenar(config, destino)
    if resultado.pesos.parent.resolve() != destino.resolve():
        raise EntrenamientoInvalidoError(
            f"El entrenador dejó los pesos fuera de la carpeta del artefacto: {resultado.pesos}."
        )
    registro = {
        "artefacto": destino.name,
        "sha_codigo": sha_codigo,
        "huella_config": huella,
        "config": campos_de_config(config),
        "dataset_version": manifiesto["version"],
        "dataset_huella": huella_dataset,
        "metricas": dict(resultado.metricas),
        "pesos": resultado.pesos.name,
        "pesos_sha256": sha256_de(resultado.pesos),
    }
    texto = json.dumps(registro, ensure_ascii=False, indent=2)
    (destino / ARCHIVO_DE_REGISTRO).write_text(texto, encoding="utf-8")
    return registro
