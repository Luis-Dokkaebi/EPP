"""Cupo de cámaras simultáneas que habilita la licencia (SPEC/1: de 1 a 16 según el plan)."""

from typing import Protocol


class CupoDeCamarasAgotadoError(RuntimeError):
    """Ya están conectadas todas las cámaras que permite la licencia."""


class LicenciaConCupo(Protocol):
    """Lo que el cupo necesita de la licencia DRM."""

    def get_max_cameras(self) -> int: ...


def exigir_cupo_de_camaras(conectadas: int, maximo: int) -> None:
    """Falla si conectar una cámara más superaría el máximo de la licencia."""
    if conectadas >= maximo:
        raise CupoDeCamarasAgotadoError(f"La licencia permite {maximo} cámara(s) a la vez")


def motivo_sin_cupo(licencia: LicenciaConCupo | None, conectadas: int) -> str | None:
    """Por qué no se puede conectar otra cámara, o None si se puede. Sin licencia no hay tope."""
    if licencia is None:
        return None
    try:
        exigir_cupo_de_camaras(conectadas, licencia.get_max_cameras())
    except CupoDeCamarasAgotadoError as error:
        return str(error)
    return None
