"""Acuerdo entre dos etiquetadores sobre el doble etiquetado del dataset EPP (SPEC/9 §2.5, B-03).

Las cajas de las dos personas se emparejan sin mirar la clase (IoU >= 0.5, mayor IoU primero).
Por clase se informa el acuerdo 2·coincidencias / (cajas de A + cajas de B) y el IoU medio; para
todo el conjunto, el kappa de Cohen con "fondo" para las cajas sin pareja. Las regiones "ignorar"
(iscrowd = 1) no cuentan. El umbral mínimo lo aprueba un humano con la guía de etiquetado: sin él,
la medición se informa pero no aprueba nada (falla cerrada).
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

IOU_MINIMO = 0.5
FONDO = "fondo"
CODIGO_NO_APROBADO = 1
CODIGO_INVALIDO = 2


class AcuerdoInvalidoError(ValueError):
    """Los dos etiquetados no son comparables."""


class UmbralDeAcuerdoPendienteError(ValueError):
    """No hay umbral de acuerdo aprobado: nada se aprueba."""


class Caja(NamedTuple):
    clase: str
    x: float
    y: float
    ancho: float
    alto: float


class AcuerdoDeClase(NamedTuple):
    clase: str
    cajas_a: int
    cajas_b: int
    coincidencias: int
    iou_medio: float | None

    @property
    def acuerdo(self) -> float | None:
        total = self.cajas_a + self.cajas_b
        return 2 * self.coincidencias / total if total else None


@dataclass(frozen=True)
class InformeDeAcuerdo:
    por_clase: Mapping[str, AcuerdoDeClase]
    kappa: float | None


def iou(a: Caja, b: Caja) -> float:
    ancho = max(0.0, min(a.x + a.ancho, b.x + b.ancho) - max(a.x, b.x))
    alto = max(0.0, min(a.y + a.alto, b.y + b.alto) - max(a.y, b.y))
    interseccion = ancho * alto
    return interseccion / (a.ancho * a.alto + b.ancho * b.alto - interseccion)


def emparejar(a: Sequence[Caja], b: Sequence[Caja]) -> list[tuple[int | None, int | None]]:
    """Pares (índice en A, índice en B); una caja sin pareja lleva None del otro lado."""
    pares: list[tuple[int | None, int | None]] = list(_emparejadas(a, b))
    usadas_a = {i for i, _ in pares}
    usadas_b = {j for _, j in pares}
    pares += [(i, None) for i in range(len(a)) if i not in usadas_a]
    pares += [(None, j) for j in range(len(b)) if j not in usadas_b]
    return pares


def _emparejadas(a: Sequence[Caja], b: Sequence[Caja]) -> list[tuple[int, int]]:
    candidatos = sorted(
        ((iou(caja_a, caja_b), i, j) for i, caja_a in enumerate(a) for j, caja_b in enumerate(b)),
        reverse=True,
    )
    pares: list[tuple[int, int]] = []
    for valor, i, j in candidatos:
        libres = all(i != usada_a and j != usada_b for usada_a, usada_b in pares)
        if valor >= IOU_MINIMO and libres:
            pares.append((i, j))
    return pares


def kappa_de_cohen(pares: Sequence[tuple[str, str]]) -> float | None:
    """Kappa de Cohen; None si no hay pares o si el acuerdo por azar es total."""
    if not pares:
        return None
    total = len(pares)
    observado = sum(clase_a == clase_b for clase_a, clase_b in pares) / total
    frecuencias_a = Counter(clase_a for clase_a, _ in pares)
    frecuencias_b = Counter(clase_b for _, clase_b in pares)
    azar = sum(frecuencias_a[clase] * frecuencias_b[clase] for clase in frecuencias_a) / total**2
    if azar == 1:
        return None
    return (observado - azar) / (1 - azar)


def medir_acuerdo(coco_a: Mapping[str, Any], coco_b: Mapping[str, Any]) -> InformeDeAcuerdo:
    if coco_a["categories"] != coco_b["categories"]:
        raise AcuerdoInvalidoError("Los dos etiquetados deben usar las mismas categorías.")
    cajas_a, cajas_b = _cajas_por_imagen(coco_a), _cajas_por_imagen(coco_b)
    if cajas_a.keys() != cajas_b.keys():
        raise AcuerdoInvalidoError(
            "Los dos etiquetados deben cubrir las mismas imágenes; difieren en: "
            f"{', '.join(sorted(cajas_a.keys() ^ cajas_b.keys()))}."
        )
    pares = [par for imagen, de_a in cajas_a.items() for par in _pares(de_a, cajas_b[imagen])]
    clases = [categoria["name"] for categoria in coco_a["categories"]]
    return InformeDeAcuerdo(
        {clase: _acuerdo_de_clase(clase, pares) for clase in clases},
        kappa_de_cohen([(clase_a, clase_b) for clase_a, clase_b, _ in pares]),
    )


def _pares(de_a: Sequence[Caja], de_b: Sequence[Caja]) -> list[tuple[str, str, float]]:
    """(clase en A, clase en B, IoU) por par; "fondo" e IoU 0 del lado sin pareja."""
    return [
        (
            FONDO if i is None else de_a[i].clase,
            FONDO if j is None else de_b[j].clase,
            0.0 if i is None or j is None else iou(de_a[i], de_b[j]),
        )
        for i, j in emparejar(de_a, de_b)
    ]


def _acuerdo_de_clase(clase: str, pares: Sequence[tuple[str, str, float]]) -> AcuerdoDeClase:
    ious = [valor for clase_a, clase_b, valor in pares if clase_a == clase_b == clase]
    return AcuerdoDeClase(
        clase,
        sum(clase_a == clase for clase_a, _, _ in pares),
        sum(clase_b == clase for _, clase_b, _ in pares),
        len(ious),
        sum(ious) / len(ious) if ious else None,
    )


def _cajas_por_imagen(coco: Mapping[str, Any]) -> dict[str, list[Caja]]:
    nombres = {categoria["id"]: categoria["name"] for categoria in coco["categories"]}
    archivos = {imagen["id"]: imagen["file_name"] for imagen in coco["images"]}
    cajas: dict[str, list[Caja]] = {archivo: [] for archivo in archivos.values()}
    for anotacion in coco["annotations"]:
        if anotacion.get("iscrowd") != 1:
            clase = nombres[anotacion["category_id"]]
            cajas[archivos[anotacion["image_id"]]].append(Caja(clase, *anotacion["bbox"]))
    return cajas


def clases_bajo_el_umbral(informe: InformeDeAcuerdo, umbral: float | None) -> list[str]:
    """Clases a redefinir: acuerdo por debajo del umbral o sin cajas para medirlo."""
    if umbral is None:
        raise UmbralDeAcuerdoPendienteError(
            "Umbral de acuerdo PENDIENTE: lo aprueba el responsable de producto junto con la guía "
            "de etiquetado (docs/ml/guia_etiquetado.md §6). Sin él, nada se aprueba."
        )
    return [
        clase
        for clase, resultado in informe.por_clase.items()
        if resultado.acuerdo is None or resultado.acuerdo < umbral
    ]


def _cifra(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:.2f}"


def _texto(informe: InformeDeAcuerdo) -> str:
    lineas = [
        f"{clase}: cajas A {resultado.cajas_a}, cajas B {resultado.cajas_b}, coincidencias "
        f"{resultado.coincidencias}, acuerdo {_cifra(resultado.acuerdo)}, "
        f"IoU medio {_cifra(resultado.iou_medio)}"
        for clase, resultado in informe.por_clase.items()
    ]
    return "\n".join([*lineas, f"kappa de Cohen: {_cifra(informe.kappa)}", ""])


def _guardar_reporte(
    ruta: Path, informe: InformeDeAcuerdo, umbral: float | None, a_redefinir: list[str] | None
) -> None:
    contenido = {
        "umbral": umbral,
        "kappa": informe.kappa,
        "clases_a_redefinir": a_redefinir,
        "por_clase": {
            clase: {
                "cajas_a": resultado.cajas_a,
                "cajas_b": resultado.cajas_b,
                "coincidencias": resultado.coincidencias,
                "acuerdo": resultado.acuerdo,
                "iou_medio": resultado.iou_medio,
            }
            for clase, resultado in informe.por_clase.items()
        },
    }
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def _analizar(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("etiquetado_a", type=Path, help="COCO exportado por la primera persona")
    parser.add_argument("etiquetado_b", type=Path, help="COCO exportado por la segunda persona")
    parser.add_argument("--umbral", type=float, default=None, help="acuerdo mínimo aprobado")
    parser.add_argument("--reporte", type=Path, default=None, help="JSON con la medición")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = _analizar(argv)
    try:
        informe = medir_acuerdo(
            json.loads(argumentos.etiquetado_a.read_text(encoding="utf-8")),
            json.loads(argumentos.etiquetado_b.read_text(encoding="utf-8")),
        )
    except AcuerdoInvalidoError as error:
        sys.stderr.write(f"{error}\n")
        return CODIGO_INVALIDO
    sys.stdout.write(_texto(informe))
    try:
        a_redefinir: list[str] | None = clases_bajo_el_umbral(informe, argumentos.umbral)
    except UmbralDeAcuerdoPendienteError as error:
        a_redefinir = None
        sys.stderr.write(f"{error}\n")
    if argumentos.reporte is not None:
        _guardar_reporte(argumentos.reporte, informe, argumentos.umbral, a_redefinir)
    if a_redefinir:
        sys.stderr.write(f"Redefinir en la guía y volver a etiquetar: {', '.join(a_redefinir)}.\n")
    if a_redefinir is None or a_redefinir:
        return CODIGO_NO_APROBADO
    sys.stdout.write(f"Acuerdo aprobado con el umbral {argumentos.umbral}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
