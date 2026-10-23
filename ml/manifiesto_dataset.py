"""Manifiesto versionado del dataset EPP: hashes, split, taxonomía y fuentes (SPEC/9 §2.6, B-03).

Las imágenes nunca van a git; el manifiesto sí (solo nombres de archivo y sha256). Se guarda como
`ml/datasets/<version>/manifest.json` y cada modelo entrenado registra su huella.
"""

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from ml.contrato_datos import (
    SPLITS,
    ContratoDeDatosError,
    ImagenDeSplit,
    validar_anotaciones,
    validar_licencia_de_fuente,
    validar_split,
)

ARCHIVO_DE_ANOTACIONES = "anotaciones.json"
VERSION = re.compile(r"v\d+\.\d+")
BLOQUE_DE_LECTURA = 1 << 20


class Fuente(NamedTuple):
    nombre: str
    licencia: str


class ReglaDeSplit(NamedTuple):
    """Las cámaras de test van enteras a test; de las demás, los días de valid van a valid."""

    camaras_de_test: frozenset[str]
    dias_de_valid: frozenset[str]

    def split_de(self, camara: str, fecha: str) -> str:
        if camara in self.camaras_de_test:
            return "test"
        return "valid" if fecha in self.dias_de_valid else "train"


def sha256_de(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(BLOQUE_DE_LECTURA), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


@dataclass(frozen=True)
class DefinicionDelDataset:
    """Lo que decide una persona al versionar: versión, taxonomía, fuentes, split y lado mínimo."""

    version: str
    taxonomia: Sequence[str]
    fuentes: Sequence[Fuente]
    regla: ReglaDeSplit
    lado_minimo_px: float

    def __post_init__(self) -> None:
        if VERSION.fullmatch(self.version) is None:
            raise ContratoDeDatosError(
                [f'Versión "{self.version}" inválida: usa vMAYOR.MENOR (v0.1).']
            )
        if not self.fuentes:
            raise ContratoDeDatosError(["El dataset debe declarar al menos una fuente."])
        for fuente in self.fuentes:
            validar_licencia_de_fuente(fuente.nombre, fuente.licencia)


def crear_manifiesto(carpeta: Path, definicion: DefinicionDelDataset) -> dict[str, Any]:
    """Valida el dataset contra el contrato y describe cada imagen con su hash y su split."""
    ruta_anotaciones = carpeta / ARCHIVO_DE_ANOTACIONES
    coco = json.loads(ruta_anotaciones.read_text(encoding="utf-8"))
    validar_anotaciones(coco, definicion.taxonomia, definicion.lado_minimo_px)
    descripciones = _describir_imagenes(carpeta, coco["images"], definicion.regla)
    conteo = Counter(descripcion["split"] for descripcion in descripciones)
    return {
        "version": definicion.version,
        "taxonomia": list(definicion.taxonomia),
        "lado_minimo_px": definicion.lado_minimo_px,
        "fuentes": [fuente._asdict() for fuente in definicion.fuentes],
        "regla_de_split": {
            "camaras_de_test": sorted(definicion.regla.camaras_de_test),
            "dias_de_valid": sorted(definicion.regla.dias_de_valid),
        },
        "anotaciones": {"archivo": ARCHIVO_DE_ANOTACIONES, "sha256": sha256_de(ruta_anotaciones)},
        "imagenes": descripciones,
        "conteo_por_split": {split: conteo[split] for split in SPLITS},
    }


def _describir_imagenes(
    carpeta: Path, imagenes: Sequence[Mapping[str, Any]], regla: ReglaDeSplit
) -> list[dict[str, str]]:
    resultados = [_describir(carpeta, imagen, regla) for imagen in imagenes]
    violaciones = [problema for _, problema in resultados if problema]
    if violaciones:
        raise ContratoDeDatosError(violaciones)
    descripciones = [descripcion for descripcion, _ in resultados]
    validar_split(
        ImagenDeSplit(imagen["camara"], imagen["fecha"], descripcion["split"])
        for imagen, descripcion in zip(imagenes, descripciones, strict=True)
    )
    return descripciones


def _describir(
    carpeta: Path, imagen: Mapping[str, Any], regla: ReglaDeSplit
) -> tuple[dict[str, str], str | None]:
    nombre = imagen["file_name"]
    ruta = carpeta / nombre
    if not ruta.is_file():
        return {}, f"{nombre}: falta el archivo de la imagen."
    resumen = sha256_de(ruta)
    if imagen.get("sha256", resumen) != resumen:
        return {}, f"{nombre}: el sha256 no coincide con el de la captura (la imagen se editó)."
    descripcion = {
        "file_name": nombre,
        "sha256": resumen,
        "split": regla.split_de(imagen["camara"], imagen["fecha"]),
    }
    return descripcion, None


def verificar_manifiesto(carpeta: Path, manifiesto: Mapping[str, Any]) -> list[str]:
    """Diferencias entre la carpeta y el manifiesto; vacía si el dataset está intacto."""
    anotaciones = manifiesto["anotaciones"]
    diferencias = []
    if sha256_de(carpeta / anotaciones["archivo"]) != anotaciones["sha256"]:
        diferencias.append(f"{anotaciones['archivo']}: el sha256 no coincide con el manifiesto.")
    esperadas = {imagen["file_name"]: imagen["sha256"] for imagen in manifiesto["imagenes"]}
    presentes = {ruta.name for ruta in carpeta.glob("*.jpg")}
    for nombre in sorted(esperadas.keys() | presentes):
        diferencias += _diferencia(carpeta / nombre, esperadas.get(nombre))
    return diferencias


def _diferencia(ruta: Path, esperado: str | None) -> list[str]:
    if esperado is None:
        return [f"{ruta.name}: está en la carpeta pero no en el manifiesto."]
    if not ruta.is_file():
        return [f"{ruta.name}: falta el archivo."]
    if sha256_de(ruta) != esperado:
        return [f"{ruta.name}: el sha256 no coincide con el manifiesto."]
    return []


def huella_del_manifiesto(manifiesto: Mapping[str, Any]) -> str:
    """sha256 del JSON canónico (claves ordenadas): identifica el dataset en el entrenamiento."""
    canonico = json.dumps(manifiesto, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
