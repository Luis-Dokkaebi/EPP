"""Gate de licencias del runtime y de los modelos (SPEC/9 §0.5, AC-001 y AC-002).

Clasifica la licencia de cada paquete instalado (salida JSON de pip-licenses) en permitida,
prohibida o pendiente de revisión humana. Una licencia prohibida o pendiente solo pasa si
docs/legal/licencias_revisadas.json registra una decisión aprobada por un humano para esa
misma licencia declarada.

Además valida models/manifest.json: todo .onnx/.pt de models/ (o de la raíz) declarado, con
sha256 coincidente y licencias permisivas para los pesos, el código de entrenamiento y los
datasets.

Uso: python scripts/check_licenses.py [--paquetes salida.json] [--revisadas revisadas.json]
                                      [--raiz .] [--manifiesto models/manifest.json]
     Sin --paquetes, corre pip-licenses sobre el entorno actual (debe ser el de runtime).
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from enum import IntEnum
from pathlib import Path
from typing import Any

REVISADAS_POR_DEFECTO = "docs/legal/licencias_revisadas.json"
MANIFIESTO_POR_DEFECTO = "models/manifest.json"
EXTENSIONES_DE_MODELO = (".onnx", ".pt")
BLOQUE_LECTURA = 1 << 20
SEPARADOR_ALTERNATIVAS = re.compile(r"\s+OR\s+", re.IGNORECASE)
SEPARADOR_CONJUNTO = re.compile(r"\s+AND\s+|;", re.IGNORECASE)
CC_BY_SOLO_ATRIBUCION = re.compile(r"^cc[- ]by[- ]\d(\.\d)?$", re.IGNORECASE)


class Veredicto(IntEnum):
    """Ordenado por gravedad: el peor de un conjunto AND decide."""

    PERMITIDA = 0
    REVISION = 1
    PROHIBIDA = 2


# El orden importa: LGPL se revisa antes que GPL porque su nombre contiene "General Public".
# Lo que no coincide con ninguna regla (MPL, licencias desconocidas o vacías) va a revisión.
REGLAS = (
    (re.compile(r"affero|agpl", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"lgpl|lesser general|library general", re.IGNORECASE), Veredicto.REVISION),
    (re.compile(r"\bgpl|general public license", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"sspl|server side public", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"\bnc\b|non-?commercial", re.IGNORECASE), Veredicto.PROHIBIDA),
    (re.compile(r"\bpml\b|commercial|proprietary", re.IGNORECASE), Veredicto.PROHIBIDA),
    (
        re.compile(
            r"\bmit\b|\bbsd\b|bsd-|apache|\bisc\b|\bpsf|python software foundation|\bbsl\b|"
            r"boost|hpnd|historical permission|\bcc0\b|unlicense|zlib",
            re.IGNORECASE,
        ),
        Veredicto.PERMITIDA,
    ),
)


def _clasificar_termino(termino: str) -> Veredicto:
    for patron, veredicto in REGLAS:
        if patron.search(termino):
            return veredicto
    return Veredicto.REVISION


def _clasificar_conjunto(conjunto: str) -> Veredicto:
    return max(_clasificar_termino(termino) for termino in SEPARADOR_CONJUNTO.split(conjunto))


def clasificar_licencia(licencia: str) -> Veredicto:
    """Las alternativas OR eligen la mejor; los términos AND o `;` exigen todos."""
    return min(_clasificar_conjunto(opcion) for opcion in SEPARADOR_ALTERNATIVAS.split(licencia))


def _aprobada(paquete: dict[str, str], revisadas: dict[str, dict[str, str | None]]) -> bool:
    revision = revisadas.get(paquete["Name"].lower(), {})
    return bool(revision.get("aprobado_por")) and (
        revision.get("licencia_declarada") == paquete["License"]
    )


def _error(paquete: dict[str, str], veredicto: Veredicto) -> str:
    identificacion = f"{paquete['Name']} {paquete['Version']}"
    if veredicto is Veredicto.PROHIBIDA:
        return (
            f"{identificacion}: licencia prohibida en el runtime ({paquete['License']}). "
            "Reemplázalo por una alternativa Apache/MIT o registra la aprobación legal en "
            "docs/legal/."
        )
    return (
        f"{identificacion}: licencia que exige revisión humana ({paquete['License']}). "
        "Registra la decisión aprobada en docs/legal/licencias_revisadas.json."
    )


def evaluar_paquetes(
    paquetes: list[dict[str, str]], revisadas: dict[str, dict[str, str | None]]
) -> list[str]:
    """Un mensaje por paquete no permitido y sin revisión aprobada vigente."""
    return [
        _error(paquete, veredicto)
        for paquete in paquetes
        if (veredicto := clasificar_licencia(paquete["License"])) is not Veredicto.PERMITIDA
        and not _aprobada(paquete, revisadas)
    ]


def paquetes_instalados() -> list[dict[str, str]]:
    # S603: ejecuta pip-licenses del mismo intérprete; los argumentos son fijos.
    salida = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--from=mixed", "--format=json"],  # noqa: S603
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paquetes: list[dict[str, str]] = json.loads(salida)
    return paquetes


def _sha256(archivo: Path) -> str:
    resumen = hashlib.sha256()
    with archivo.open("rb") as entrada:
        for bloque in iter(lambda: entrada.read(BLOQUE_LECTURA), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _modelos_en_disco(raiz: Path) -> list[str]:
    candidatos = [*(raiz / "models").rglob("*"), *raiz.glob("*")]
    return sorted(
        ruta.relative_to(raiz).as_posix()
        for ruta in candidatos
        if ruta.is_file() and ruta.suffix in EXTENSIONES_DE_MODELO
    )


def clasificar_licencia_de_dataset(licencia: str) -> Veredicto:
    """CC BY (solo atribución) sirve para datos de entrenamiento comerciales (SPEC/9 §2.3)."""
    if CC_BY_SOLO_ATRIBUCION.match(licencia.strip()):
        return Veredicto.PERMITIDA
    return clasificar_licencia(licencia)


def _veredictos(entrada: dict[str, Any]) -> list[tuple[str, str, Veredicto]]:
    pesos, codigo = entrada["licencia_pesos"], entrada["licencia_codigo_entrenamiento"]
    return [
        ("licencia_pesos", pesos, clasificar_licencia(pesos)),
        ("licencia_codigo_entrenamiento", codigo, clasificar_licencia(codigo)),
        *(
            (f"dataset {d['nombre']}", d["licencia"], clasificar_licencia_de_dataset(d["licencia"]))
            for d in entrada["datasets"]
        ),
    ]


def _errores_de_entrada(raiz: Path, entrada: dict[str, Any]) -> list[str]:
    archivo = entrada["archivo"]
    if not (raiz / archivo).is_file():
        return [f"{archivo} figura en el manifiesto pero no existe en disco."]
    errores = [
        f"{archivo}: {campo} prohibida o sin revisar ({licencia})."
        for campo, licencia, veredicto in _veredictos(entrada)
        if veredicto is not Veredicto.PERMITIDA
    ]
    real = _sha256(raiz / archivo)
    if real != entrada["sha256"]:
        errores.append(
            f"{archivo}: sha256 {real} no coincide con el manifiesto ({entrada['sha256']}). "
            "El archivo cambió o el manifiesto está desactualizado."
        )
    return errores


def evaluar_manifiesto(raiz: Path, manifiesto: dict[str, Any]) -> list[str]:
    """Mensajes de error del manifiesto contra los modelos presentes en `raiz`."""
    declarados = {entrada["archivo"] for entrada in manifiesto["modelos"]}
    sin_declarar = [
        f"{archivo} no está en models/manifest.json: decláralo con su sha256, licencias y "
        "datasets, o bórralo."
        for archivo in _modelos_en_disco(raiz)
        if archivo not in declarados
    ]
    return sin_declarar + [
        error for entrada in manifiesto["modelos"] for error in _errores_de_entrada(raiz, entrada)
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paquetes", type=Path)
    parser.add_argument("--revisadas", type=Path, default=Path(REVISADAS_POR_DEFECTO))
    parser.add_argument("--raiz", type=Path, default=Path())
    parser.add_argument("--manifiesto", type=Path)
    argumentos = parser.parse_args(argv)
    paquetes = (
        json.loads(argumentos.paquetes.read_text(encoding="utf-8"))
        if argumentos.paquetes
        else paquetes_instalados()
    )
    revisadas = json.loads(argumentos.revisadas.read_text(encoding="utf-8"))
    errores = evaluar_paquetes(paquetes, {nombre.lower(): r for nombre, r in revisadas.items()})
    manifiesto = argumentos.manifiesto or argumentos.raiz / MANIFIESTO_POR_DEFECTO
    errores += evaluar_manifiesto(
        argumentos.raiz, json.loads(manifiesto.read_text(encoding="utf-8"))
    )
    for error in errores:
        sys.stdout.write(f"{error}\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
