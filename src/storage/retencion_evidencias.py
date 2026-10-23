"""Purga de evidencias de EPP por retención (SPEC/9 §6.2, C-08; AC-019).

La retención la decide el negocio con asesoría legal (D5, pendiente): no hay valor por omisión y
si falta la purga no corre (RetencionNoConfiguradaError). Al vencer, se borra la imagen y se
anonimiza el registro (sin nombre ni ruta de evidencia); el resto de la infracción se conserva
para las estadísticas. Solo se borran archivos dentro de la carpeta de evidencias del tenant.
Los instantes se comparan como texto ISO 8601, que ordena bien porque el reloj es siempre UTC.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from src.ppe.domain.reloj import RelojPort
from src.ppe.domain.validacion import exigir_al_menos_uno

_VENCIDAS = (
    "SELECT id, evidencia_path FROM ppe_infracciones WHERE inicio < ? "
    "AND (evidencia_path IS NOT NULL OR employee_name IS NOT NULL) ORDER BY id"
)
_ANONIMIZAR = "UPDATE ppe_infracciones SET employee_name = NULL, evidencia_path = NULL WHERE id = ?"


class RetencionNoConfiguradaError(ValueError):
    """No se configuró por cuántos días se guardan las evidencias (D5)."""


class EvidenciaFueraDeLaCarpetaError(ValueError):
    """La ruta de una evidencia apunta fuera de la carpeta del tenant: no se borra."""


def retencion_de_evidencias(dias: int | None) -> timedelta:
    """Retención configurada, en días; sin valor por omisión."""
    if dias is None:
        raise RetencionNoConfiguradaError(
            "Falta la retención de evidencias en días: la define el negocio (D5) y no tiene "
            "valor por omisión"
        )
    return timedelta(days=exigir_al_menos_uno("retencion_dias", dias))


def purgar_evidencias_vencidas(
    conectar: Callable[[], sqlite3.Connection],
    carpeta_evidencias: Path,
    reloj: RelojPort,
    retencion: timedelta,
) -> int:
    """Borra las imágenes vencidas, anonimiza sus registros y devuelve cuántos purgó."""
    limite = (reloj.ahora() - retencion).isoformat()
    with closing(conectar()) as conexion, conexion:
        vencidas = conexion.execute(_VENCIDAS, (limite,)).fetchall()
        for identificador, evidencia in vencidas:
            if evidencia is not None:
                _borrar(Path(evidencia), carpeta_evidencias)
            conexion.execute(_ANONIMIZAR, (identificador,))
    return len(vencidas)


def _borrar(evidencia: Path, carpeta: Path) -> None:
    if not evidencia.resolve().is_relative_to(carpeta.resolve()):
        raise EvidenciaFueraDeLaCarpetaError(
            f"La evidencia {evidencia} no está dentro de {carpeta}: no se borra"
        )
    evidencia.unlink(missing_ok=True)
