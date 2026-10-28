"""Cupo de cámaras simultáneas que habilita la licencia (SPEC/1: de 1 a 16 según el plan)."""


class CupoDeCamarasAgotadoError(RuntimeError):
    """Ya están conectadas todas las cámaras que permite la licencia."""


def exigir_cupo_de_camaras(conectadas: int, maximo: int) -> None:
    """Falla si conectar una cámara más superaría el máximo de la licencia."""
    if conectadas >= maximo:
        raise CupoDeCamarasAgotadoError(f"La licencia permite {maximo} cámara(s) a la vez")
