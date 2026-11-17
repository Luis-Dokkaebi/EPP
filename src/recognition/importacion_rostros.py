"""Carga masiva de rostros con constancia de consentimiento (SPEC/10 §14.5).

La carpeta trae una subcarpeta por empleado (su nombre es el que saldrá en las alertas) y un
`consentimientos.csv` con las columnas `nombre` e `id_consentimiento`. Quien no figura ahí con un
identificador de consentimiento no se carga (SPEC/10 §8: sin firma no se registra el rostro).
Cada carga queda en una bitácora con quién la hizo y cuándo.
"""

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

ARCHIVO_DE_CONSENTIMIENTOS = "consentimientos.csv"
COLUMNAS = ("nombre", "id_consentimiento")
EXTENSIONES_DE_FOTO = (".jpg", ".jpeg", ".png")
COLUMNAS_DE_LA_BITACORA = ("fecha", "operador", "nombre", "id_consentimiento", "fotos")


class ImportacionInvalidaError(ValueError):
    """La carpeta no trae una constancia de consentimientos utilizable."""


class Motivo(Enum):
    """Por qué no se cargó a una persona; el valor es lo que lee el operador."""

    SIN_CONSENTIMIENTO = "sin consentimiento registrado"
    SIN_FOTOS = "sin fotos en su carpeta"
    YA_REGISTRADO = "ya estaba registrado"
    SIN_ROSTRO = "sin rostro detectable en sus fotos"


@dataclass(frozen=True)
class ResultadoDeImportacion:
    cargados: dict[str, int]  # nombre -> fotos registradas
    omitidos: dict[str, Motivo]


class RegistroDeEmpleados(Protocol):
    def ya_registrado(self, nombre: str) -> bool: ...

    def registrar(self, nombre: str, fotos: list[Path]) -> int:
        """Registra el rostro con esas fotos; devuelve en cuántas se encontró un rostro."""


class BitacoraDeImportaciones:
    """CSV de la sucursal con una fila por persona cargada: quién, cuándo y con qué constancia."""

    def __init__(self, ruta: Path, operador: str, reloj: Callable[[], datetime]) -> None:
        self.ruta = ruta
        self._operador = operador
        self._reloj = reloj

    def anotar(self, nombre: str, id_consentimiento: str, fotos: int) -> None:
        es_nueva = not self.ruta.exists()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8", newline="") as archivo:
            escritor = csv.writer(archivo)
            if es_nueva:
                escritor.writerow(COLUMNAS_DE_LA_BITACORA)
            escritor.writerow(
                (self._reloj().isoformat(), self._operador, nombre, id_consentimiento, fotos)
            )


def leer_consentimientos(carpeta: Path) -> dict[str, str]:
    """Nombre -> identificador de consentimiento, solo para quienes tienen uno."""
    archivo = carpeta / ARCHIVO_DE_CONSENTIMIENTOS
    if not archivo.exists():
        raise ImportacionInvalidaError(
            f"Falta {ARCHIVO_DE_CONSENTIMIENTOS} en la carpeta: sin constancia no se carga a nadie."
        )
    with archivo.open(encoding="utf-8", newline="") as contenido:
        lector = csv.DictReader(contenido)
        if not set(COLUMNAS) <= set(lector.fieldnames or ()):
            raise ImportacionInvalidaError(
                f"{ARCHIVO_DE_CONSENTIMIENTOS} debe tener las columnas nombre e id_consentimiento."
            )
        filas = [(fila["nombre"].strip(), fila["id_consentimiento"].strip()) for fila in lector]
    return {nombre: constancia for nombre, constancia in filas if nombre and constancia}


def _fotos(carpeta_de_la_persona: Path) -> list[Path]:
    if not carpeta_de_la_persona.is_dir():
        return []
    return sorted(
        archivo
        for archivo in carpeta_de_la_persona.iterdir()
        if archivo.suffix.lower() in EXTENSIONES_DE_FOTO
    )


def _cargar(nombre: str, fotos: list[Path], registro: RegistroDeEmpleados) -> int | Motivo:
    if registro.ya_registrado(nombre):
        return Motivo.YA_REGISTRADO
    if not fotos:
        return Motivo.SIN_FOTOS
    return registro.registrar(nombre, fotos) or Motivo.SIN_ROSTRO


def importar_rostros(
    carpeta: Path, registro: RegistroDeEmpleados, bitacora: BitacoraDeImportaciones
) -> ResultadoDeImportacion:
    """Carga a cada persona con consentimiento y fotos; del resto dice por qué no."""
    consentimientos = leer_consentimientos(carpeta)
    carpetas = {hija.name for hija in carpeta.iterdir() if hija.is_dir()}
    cargados: dict[str, int] = {}
    omitidos = dict.fromkeys(carpetas - set(consentimientos), Motivo.SIN_CONSENTIMIENTO)
    for nombre, constancia in sorted(consentimientos.items()):
        resultado = _cargar(nombre, _fotos(carpeta / nombre), registro)
        if isinstance(resultado, Motivo):
            omitidos[nombre] = resultado
            continue
        cargados[nombre] = resultado
        bitacora.anotar(nombre, constancia, resultado)
    return ResultadoDeImportacion(cargados, dict(sorted(omitidos.items())))


def resumen(resultado: ResultadoDeImportacion) -> str:
    """Una línea para el operador: a quién se cargó y por qué se omitió al resto."""
    cargados = f" ({', '.join(resultado.cargados)})" if resultado.cargados else ""
    omitidos = ", ".join(
        f"{nombre} ({motivo.value})" for nombre, motivo in resultado.omitidos.items()
    )
    return f"Cargados: {len(resultado.cargados)}{cargados}. Omitidos: {omitidos or 'ninguno'}."
