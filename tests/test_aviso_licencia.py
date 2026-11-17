"""Aviso de días restantes de la prueba en la interfaz (SPEC/10 F-03.5, T-05)."""

import pytest

from src.gui.aviso_licencia import AvisoDeLicencia, aviso_de_prueba


class LicenciaFalsa:
    def __init__(self, prueba: bool, dias: int | None) -> None:
        self._prueba = prueba
        self._dias = dias

    def es_prueba(self) -> bool:
        return self._prueba

    def dias_restantes(self) -> int | None:
        return self._dias


@pytest.mark.parametrize(
    ("dias", "aviso"),
    [
        (14, AvisoDeLicencia("Prueba: quedan 14 días", urgente=False)),
        (4, AvisoDeLicencia("Prueba: quedan 4 días", urgente=False)),
        (3, AvisoDeLicencia("Prueba: quedan 3 días", urgente=True)),
        (2, AvisoDeLicencia("Prueba: quedan 2 días", urgente=True)),
        (1, AvisoDeLicencia("Prueba: queda 1 día", urgente=True)),
        (0, AvisoDeLicencia("Prueba: vence hoy", urgente=True)),
    ],
)
def test_la_prueba_avisa_cuantos_dias_quedan_y_es_urgente_en_los_ultimos_tres(
    dias: int, aviso: AvisoDeLicencia
) -> None:
    assert aviso_de_prueba(LicenciaFalsa(prueba=True, dias=dias)) == aviso


def test_una_licencia_comercial_no_muestra_aviso() -> None:
    assert aviso_de_prueba(LicenciaFalsa(prueba=False, dias=200)) is None


def test_sin_licencia_activa_no_hay_aviso() -> None:
    assert aviso_de_prueba(LicenciaFalsa(prueba=True, dias=None)) is None
