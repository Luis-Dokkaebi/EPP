"""Reporte Excel de cumplimiento de EPP (SPEC/9 §8.4).

Una fila por turno, empleado, zona y elemento con la cantidad de infracciones, la duración total
en minutos y el porcentaje del tiempo en cumplimiento. El período son días completos en el huso
horario de la sucursal; lo que cruza la medianoche final cuenta hasta ahí, y lo que sigue
abierto cuenta hasta ahora. Se genera en segundo plano, como los reportes actuales.

El porcentaje usa el tiempo que cada persona pasó en cada zona según el seguimiento; sin
presencia registrada (por ejemplo, una persona no identificada) figura como "sin datos".
"""

import sqlite3
import threading
from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import NamedTuple

from openpyxl import Workbook

from src.analysis.cumplimiento_epp import FilaCumplimiento, exposicion_por_zona, resumir
from src.ppe.domain.reloj import RelojPort
from src.storage.reporte_cumplimiento import leer_infracciones, leer_presencias, leer_turnos

ENCABEZADOS = (
    "Turno",
    "Empleado",
    "Zona",
    "Elemento",
    "Infracciones",
    "Duración total (min)",
    "% del tiempo en cumplimiento",
)
SIN_DATOS = "sin datos"
SEGUNDOS_POR_MINUTO = 60


class PedidoReporte(NamedTuple):
    desde: date
    hasta: date
    ruta: Path


def periodo(pedido: PedidoReporte, zona: tzinfo) -> tuple[datetime, datetime]:
    """[desde 00:00, día siguiente a hasta 00:00) en el huso horario de la sucursal."""
    if pedido.desde > pedido.hasta:
        raise ValueError(f"La fecha desde ({pedido.desde}) es posterior a hasta ({pedido.hasta})")
    inicio = datetime.combine(pedido.desde, time(), zona)
    fin = datetime.combine(pedido.hasta + timedelta(days=1), time(), zona)
    return inicio, fin


class GeneradorReporteCumplimiento:
    """Lee la base del tenant y escribe el reporte."""

    def __init__(
        self, conectar: Callable[[], sqlite3.Connection], reloj: RelojPort, zona: tzinfo
    ) -> None:
        self._conectar = conectar
        self._reloj = reloj
        self._zona = zona

    def generar(self, pedido: PedidoReporte) -> int:
        """Escribe el reporte y devuelve la cantidad de filas de datos."""
        inicio, fin = periodo(pedido, self._zona)
        infracciones = leer_infracciones(self._conectar, inicio, fin)
        corte = min(fin, self._reloj.ahora())
        presencias = leer_presencias(self._conectar, inicio, fin, self._zona)
        filas = resumir(
            infracciones, leer_turnos(self._conectar), exposicion_por_zona(presencias), corte
        )
        _escribir(pedido, filas)
        return len(filas)

    def generar_en_segundo_plano(
        self,
        pedido: PedidoReporte,
        al_terminar: Callable[[Path, int], object],
        al_fallar: Callable[[Exception], object],
    ) -> threading.Thread:
        """Genera el reporte en un hilo; avisa con `al_terminar` o con `al_fallar`."""

        def trabajar() -> None:
            try:
                filas = self.generar(pedido)
            # Cualquier falla se entrega a la interfaz para mostrarla (no se silencia).
            except Exception as error:
                al_fallar(error)
                return
            al_terminar(pedido.ruta, filas)

        hilo = threading.Thread(target=trabajar, name="reporte-cumplimiento-epp", daemon=True)
        hilo.start()
        return hilo


def _escribir(pedido: PedidoReporte, filas: Sequence[FilaCumplimiento]) -> None:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Cumplimiento EPP"
    hoja.append(["Reporte de cumplimiento de EPP", f"del {pedido.desde} al {pedido.hasta}"])
    hoja.append(ENCABEZADOS)
    for fila in filas:
        hoja.append(_celdas(fila))
    if not filas:
        hoja.append(["Sin infracciones en el período"])
    libro.save(pedido.ruta)


def _celdas(fila: FilaCumplimiento) -> list[object]:
    minutos = round(fila.duracion_total.total_seconds() / SEGUNDOS_POR_MINUTO, 1)
    porcentaje = SIN_DATOS if fila.porcentaje_cumplimiento is None else fila.porcentaje_cumplimiento
    return [fila.turno, fila.persona, fila.zona, fila.elemento, fila.cantidad, minutos, porcentaje]
