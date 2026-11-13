"""Vigencia de una licencia ya verificada (SPEC/10 §4.2): vencimiento, reloj atrasado y días.

La firma RSA y el equipo los revisa `drm.py`; aquí solo se decide con fechas. Atrasar el reloj
del equipo no extiende una prueba: se rechaza una hora anterior a la emisión de la licencia o a
la última hora en que la app funcionó, que se guarda firmada para este equipo.
"""

import hashlib
import hmac
import math
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any

SEGUNDOS_POR_DIA = 86_400
# Un reloj que se corrige solo (horario de verano, sincronización) no debe bloquear la app.
TOLERANCIA_DE_RELOJ_S = 3_600
TIER_DE_PRUEBA = "prueba"
SAL_DEL_REGISTRO = b"_oe_reloj_licencia_v1"
SEPARADOR = b":"


class MotivoDeRechazo(Enum):
    """Por qué no rige una licencia; el valor es el texto que ve el usuario."""

    SIN_LICENCIA = "No hay una licencia activada en este equipo."
    INVALIDA = "La llave no es válida, está dañada o no corresponde a este equipo."
    VENCIDA = "La licencia venció. Contrate para continuar: lo aprendido se conserva."
    FECHA_INCORRECTA = "La fecha del equipo no es correcta."


class RegistroDeRelojAlteradoError(ValueError):
    """El registro de la última hora vista no lleva la firma de este equipo."""


def motivo_de_rechazo_por_fecha(
    datos: Mapping[str, Any], ahora: float, ultima_vista: float | None
) -> MotivoDeRechazo | None:
    """None si la licencia rige en `ahora`; si no, por qué no."""
    if ahora > datos.get("exp", 0):
        return MotivoDeRechazo.VENCIDA
    piso = max(datos.get("emitida", 0), ultima_vista or 0)
    if ahora < piso - TOLERANCIA_DE_RELOJ_S:
        return MotivoDeRechazo.FECHA_INCORRECTA
    return None


def dias_restantes(datos: Mapping[str, Any], ahora: float) -> int:
    """Días que le quedan a la licencia, contando el día empezado; 0 si ya venció."""
    return max(0, math.ceil((datos.get("exp", 0) - ahora) / SEGUNDOS_POR_DIA))


def es_de_prueba(datos: Mapping[str, Any]) -> bool:
    return datos.get("tier") == TIER_DE_PRUEBA


class UltimaHoraVista:
    """La hora más reciente en que la licencia rigió, guardada con un HMAC de este equipo."""

    def __init__(self, ruta: Path, machine_id: str) -> None:
        self._ruta = ruta
        self._clave = hashlib.sha256(machine_id.encode("utf-8") + SAL_DEL_REGISTRO).digest()

    def leer(self) -> float | None:
        """None si nunca se anotó; RegistroDeRelojAlteradoError si la firma no es de este equipo."""
        if not self._ruta.exists():
            return None
        hora, _, firma = self._ruta.read_bytes().partition(SEPARADOR)
        if not hmac.compare_digest(firma, self._firma(hora)):
            raise RegistroDeRelojAlteradoError(f"{self._ruta} no lleva la firma de este equipo.")
        return float(hora)

    def anotar(self, instante: float) -> None:
        """Avanza el registro a `instante`; una hora anterior a la guardada no lo retrocede."""
        hora = repr(max(float(instante), self.leer() or 0.0)).encode("ascii")
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_bytes(hora + SEPARADOR + self._firma(hora))

    def _firma(self, hora: bytes) -> bytes:
        return hmac.new(self._clave, hora, hashlib.sha256).hexdigest().encode("ascii")
