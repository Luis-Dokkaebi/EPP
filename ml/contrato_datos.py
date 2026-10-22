"""Contrato de datos del dataset EPP verificable por código (docs/ml/contrato_datos.md).

Valida un COCO ya normalizado (taxonomía, metadatos de captura, cajas, regiones "ignorar"), la
licencia de cada fuente y que el split no filtre información entre train, valid y test.
"""

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, NamedTuple, TypeGuard

TAXONOMIA_V1 = ("persona", "cabeza", "casco", "chaleco")
TAXONOMIA_V2 = (*TAXONOMIA_V1, "manos", "guantes", "gafas", "barbijo")
TAXONOMIAS = {"v1": TAXONOMIA_V1, "v2": TAXONOMIA_V2}
METADATOS_DE_IMAGEN = ("camara", "fecha", "hora", "turno", "autorizacion")
SECCIONES_COCO = ("images", "annotations", "categories")
SPLITS = ("train", "valid", "test")
SPLIT_DE_TEST = "test"
NOMBRE_DE_ARCHIVO = re.compile(
    r"(?P<camara>[a-z0-9-]+)_(?P<fecha>\d{8})_(?P<hora>\d{6})_\d{4}\.jpg"
)
LICENCIAS_PERMITIDAS = frozenset({"propia-con-autorizacion", "CC-BY-4.0", "CC0-1.0", "MIT"})
PREFIJOS_PROHIBIDOS = ("CC-BY-NC", "AGPL", "GPL", "SSPL", "PML")
VALORES_DE_CAJA = 4


class ContratoDeDatosError(ValueError):
    """El dataset incumple el contrato; `violaciones` las lista todas."""

    def __init__(self, violaciones: list[str]) -> None:
        self.violaciones = violaciones
        super().__init__("\n".join(["El dataset no cumple el contrato de datos:", *violaciones]))


class ImagenDeSplit(NamedTuple):
    camara: str
    fecha: str
    split: str


def categorias(taxonomia: Sequence[str]) -> list[dict[str, Any]]:
    """Categorías COCO del contrato: ids desde 1 en el orden de la taxonomía."""
    return [{"id": indice, "name": nombre} for indice, nombre in enumerate(taxonomia, start=1)]


def validar_anotaciones(
    coco: Mapping[str, Any], taxonomia: Sequence[str], lado_minimo_px: float
) -> None:
    """Lanza ContratoDeDatosError con todas las violaciones; el lado mínimo depende de D6."""
    if not lado_minimo_px > 0:
        raise ValueError(f"El lado mínimo debe ser positivo; llegó {lado_minimo_px}.")
    faltantes = [
        f'Falta la sección "{nombre}" del COCO.' for nombre in SECCIONES_COCO if nombre not in coco
    ]
    if faltantes:
        raise ContratoDeDatosError(faltantes)
    violaciones = _violaciones_de_categorias(coco["categories"], taxonomia)
    imagenes = {imagen["id"]: imagen for imagen in coco["images"]}
    for imagen in imagenes.values():
        violaciones += _violaciones_de_imagen(imagen)
    for anotacion in coco["annotations"]:
        violaciones += _violaciones_de_caja(anotacion, imagenes, len(taxonomia), lado_minimo_px)
    if violaciones:
        raise ContratoDeDatosError(violaciones)


def _violaciones_de_categorias(exportadas: Any, taxonomia: Sequence[str]) -> list[str]:
    if exportadas == categorias(taxonomia):
        return []
    return [
        "Las categorías no son las de la taxonomía (ids desde 1, en orden): "
        f"{', '.join(taxonomia)}."
    ]


def _violaciones_de_imagen(imagen: Mapping[str, Any]) -> list[str]:
    nombre = imagen["file_name"]
    violaciones = [
        f'{nombre}: falta el metadato "{campo}".'
        for campo in METADATOS_DE_IMAGEN
        if not isinstance(imagen.get(campo), str) or not imagen[campo].strip()
    ]
    partes = NOMBRE_DE_ARCHIVO.fullmatch(nombre)
    if partes is None:
        return [
            *violaciones,
            f"{nombre}: el nombre no sigue <camara>_<AAAAMMDD>_<HHMMSS>_<nnnn>.jpg.",
        ]
    try:
        momento = datetime.strptime(partes["fecha"] + partes["hora"], "%Y%m%d%H%M%S")
    except ValueError:
        return [*violaciones, f"{nombre}: la fecha y hora del nombre no existen."]
    esperados = {
        "camara": partes["camara"],
        "fecha": momento.strftime("%Y-%m-%d"),
        "hora": momento.strftime("%H:%M:%S"),
    }
    return violaciones + [
        f'{nombre}: el metadato "{campo}" ({imagen[campo]}) no coincide con el nombre del archivo.'
        for campo, esperado in esperados.items()
        if campo in imagen and imagen[campo] != esperado
    ]


def _violaciones_de_caja(
    anotacion: Mapping[str, Any],
    imagenes: Mapping[Any, Mapping[str, Any]],
    categorias_validas: int,
    lado_minimo_px: float,
) -> list[str]:
    identificador = anotacion["id"]
    imagen = imagenes.get(anotacion["image_id"])
    if imagen is None:
        return [
            f"La caja {identificador} apunta a la imagen {anotacion['image_id']}, que no existe."
        ]
    prefijo = f"{imagen['file_name']}: la caja {identificador}"
    categoria = anotacion.get("category_id")
    if not isinstance(categoria, int) or not 1 <= categoria <= categorias_validas:
        return [f"{prefijo} tiene la categoría {categoria}, que no está en la taxonomía."]
    caja = anotacion.get("bbox")
    if not _es_caja(caja):
        return [f"{prefijo} no es [x, y, ancho, alto] con ancho y alto positivos."]
    ignorada = anotacion.get("iscrowd") == 1
    return _violaciones_de_geometria(prefijo, caja, imagen, lado_minimo_px, ignorada)


def _violaciones_de_geometria(
    prefijo: str,
    caja: list[float],
    imagen: Mapping[str, Any],
    lado_minimo_px: float,
    ignorada: bool,
) -> list[str]:
    x, y, ancho, alto = caja
    if x < 0 or y < 0 or x + ancho > imagen["width"] or y + alto > imagen["height"]:
        return [f"{prefijo} se sale de la imagen de {imagen['width']}x{imagen['height']}."]
    if min(ancho, alto) < lado_minimo_px and not ignorada:
        return [
            f"{prefijo} mide menos de {lado_minimo_px} px de lado: márcala como región ignorar "
            "(iscrowd = 1)."
        ]
    return []


def _es_caja(caja: Any) -> TypeGuard[list[float]]:
    return (
        isinstance(caja, list)
        and len(caja) == VALORES_DE_CAJA
        and all(isinstance(valor, int | float) and math.isfinite(valor) for valor in caja)
        and caja[2] > 0
        and caja[3] > 0
    )


def validar_licencia_de_fuente(nombre: str, licencia: str) -> None:
    """Permite solo licencias comerciales; SH17 y las no comerciales o copyleft fallan."""
    if "sh17" in nombre.lower():
        mensaje = f"{nombre}: SH17 no es apto para el producto (CC BY-NC-SA 4.0, SPEC/9 §2.3)."
    elif licencia.startswith(PREFIJOS_PROHIBIDOS):
        mensaje = f"{nombre}: la licencia {licencia} está prohibida para pesos que se distribuyen."
    elif licencia not in LICENCIAS_PERMITIDAS:
        mensaje = f'{nombre}: la licencia "{licencia}" necesita revisión humana antes de usarse.'
    else:
        return
    raise ContratoDeDatosError([mensaje])


def validar_split(imagenes: Iterable[ImagenDeSplit]) -> None:
    """Split por cámara y día, con una cámara solo en test y los tres splits con imágenes."""
    splits_por_grupo: dict[tuple[str, str], set[str]] = defaultdict(set)
    splits_por_camara: dict[str, set[str]] = defaultdict(set)
    violaciones = []
    for imagen in imagenes:
        if imagen.split not in SPLITS:
            violaciones.append(
                f'{imagen.camara} del {imagen.fecha}: split desconocido "{imagen.split}" '
                f"(válidos: {', '.join(SPLITS)})."
            )
        splits_por_grupo[imagen.camara, imagen.fecha].add(imagen.split)
        splits_por_camara[imagen.camara].add(imagen.split)
    violaciones += [
        f"{camara} del {fecha} está en más de un split ({', '.join(sorted(splits))}): "
        "fuga de información."
        for (camara, fecha), splits in splits_por_grupo.items()
        if len(splits) > 1
    ]
    if {SPLIT_DE_TEST} not in splits_por_camara.values():
        violaciones.append("Ninguna cámara está reservada solo para test (SPEC/9 §2.4).")
    usados = set().union(*splits_por_camara.values())
    violaciones += [
        f'El split "{split}" no tiene imágenes.' for split in SPLITS if split not in usados
    ]
    if violaciones:
        raise ContratoDeDatosError(violaciones)
