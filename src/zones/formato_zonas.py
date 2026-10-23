"""Archivo de zonas v1 y v2 (SPEC/9 §6.3, C-06; skill migration).

- v1 (heredado): {"Zona": [[x, y], ...]}. Se lee como "sin EPP exigido".
- v2: {"version": 2, "zonas": {"Zona": {"poligono": [[x, y]], "epp_requerido": ["casco"]}}}.

El lector acepta ambos; el escritor guarda v2 y, antes de pisar un v1, deja una copia
`<nombre>.v1.bak.json` (una sola vez: nunca pisa una copia previa). Revertir = restaurar la
copia. Un archivo corrupto falla con FormatoZonasError y nunca se sobrescribe.
"""

import json
import shutil
from collections.abc import Iterable
from pathlib import Path

from src.ppe.domain.elementos import ElementoEPP, elementos_desde_textos
from src.ppe.domain.reglas import ReglaZona

VERSION_ACTUAL = 2
COORDENADAS_POR_VERTICE = 2


class FormatoZonasError(ValueError):
    """El archivo de zonas no se puede interpretar como v1 ni como v2."""


def leer_zonas(ruta: Path) -> tuple[ReglaZona, ...]:
    """Zonas del archivo (v1 o v2); sin archivo no hay zonas."""
    if not ruta.exists():
        return ()
    datos = _cargar(ruta)
    if _es_v1(datos):
        return tuple(_zona(nombre, puntos, []) for nombre, puntos in datos.items())
    return _zonas_v2(datos)


def escribir_zonas(ruta: Path, zonas: Iterable[ReglaZona]) -> None:
    """Guarda las zonas en v2; respalda un v1 previo y no toca un archivo corrupto."""
    if ruta.exists() and _es_v1(_cargar(ruta)):
        _respaldar_v1(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(_como_json_v2(zonas), encoding="utf-8")


def _cargar(ruta: Path) -> dict[str, object]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FormatoZonasError(f"El archivo de zonas {ruta} no es JSON válido: {error}") from error
    if not isinstance(datos, dict):
        raise FormatoZonasError(f"El archivo de zonas {ruta} debe ser un objeto JSON")
    return datos


def _es_v1(datos: dict[str, object]) -> bool:
    # Un v1 puede tener una zona llamada "version": su valor es una lista de puntos.
    version = datos.get("version")
    if version is None or isinstance(version, list):
        return True
    if version != VERSION_ACTUAL:
        raise FormatoZonasError(f"Versión de zonas no soportada: {version}")
    return False


def _zonas_v2(datos: dict[str, object]) -> tuple[ReglaZona, ...]:
    zonas = datos.get("zonas")
    if not isinstance(zonas, dict):
        raise FormatoZonasError('Formato v2 sin el objeto "zonas"')
    return tuple(_zona_v2(nombre, definicion) for nombre, definicion in zonas.items())


def _zona_v2(nombre: str, definicion: object) -> ReglaZona:
    if not (isinstance(definicion, dict) and {"poligono", "epp_requerido"} <= definicion.keys()):
        raise FormatoZonasError(f'La zona "{nombre}" no tiene "poligono" y "epp_requerido"')
    epp = definicion["epp_requerido"]
    if not (isinstance(epp, list) and all(isinstance(texto, str) for texto in epp)):
        raise FormatoZonasError(
            f'La zona "{nombre}" tiene un "epp_requerido" que no es una lista de nombres'
        )
    return _zona(nombre, definicion["poligono"], epp)


def _zona(nombre: str, puntos: object, epp: Iterable[str]) -> ReglaZona:
    if not isinstance(puntos, list):
        raise FormatoZonasError(f'La zona "{nombre}" tiene un polígono que no es una lista')
    poligono = tuple(_vertice(nombre, punto) for punto in puntos)
    return ReglaZona(nombre, poligono, elementos_desde_textos(epp))


def _vertice(nombre: str, punto: object) -> tuple[float, float]:
    if not (
        isinstance(punto, list)
        and len(punto) == COORDENADAS_POR_VERTICE
        and all(isinstance(c, int | float) and not isinstance(c, bool) for c in punto)
    ):
        raise FormatoZonasError(
            f'La zona "{nombre}" tiene un vértice inválido: {json.dumps(punto)}'
        )
    return (float(punto[0]), float(punto[1]))


def _respaldar_v1(ruta: Path) -> None:
    copia = ruta.with_name(f"{ruta.stem}.v1.bak{ruta.suffix}")
    if not copia.exists():
        shutil.copy2(ruta, copia)


def _como_json_v2(zonas: Iterable[ReglaZona]) -> str:
    contenido = {
        "version": VERSION_ACTUAL,
        "zonas": {
            zona.nombre: {
                "poligono": [list(vertice) for vertice in zona.poligono],
                "epp_requerido": [e.value for e in ElementoEPP if e in zona.exigidos],
            }
            for zona in zonas
        },
    }
    return json.dumps(contenido, indent=4, ensure_ascii=False) + "\n"
