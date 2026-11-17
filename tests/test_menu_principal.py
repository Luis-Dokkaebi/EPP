"""Qué ofrece el menú según los módulos de la licencia (SPEC/10 T-18, decisión M-1)."""

import pytest

from src.gui.menu_principal import botones_del_menu, incluye_eficiencia

BASE = [
    ("Monitoreo en Vivo", "Dashboard"),
    ("Gestión de Empleados", "Empleados"),
    ("Configuración de Zonas", "Zonas"),
]
EPP = [("Alertas EPP", "AlertasEPP"), ("Cumplimiento EPP", "CumplimientoEPP")]
EFICIENCIA = [("Reportes Históricos", "Reportes")]
SUCURSAL = [("Cambiar Sucursal", "Tenant")]


class LicenciaFalsa:
    def __init__(self, *modulos: str) -> None:
        self._modulos = modulos

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo in self._modulos


@pytest.mark.parametrize(
    ("licencia", "botones"),
    [
        (None, BASE + SUCURSAL),
        (LicenciaFalsa(), BASE + SUCURSAL),
        (LicenciaFalsa("epp"), BASE + EPP + SUCURSAL),
        (LicenciaFalsa("eficiencia"), BASE + EFICIENCIA + SUCURSAL),
        (LicenciaFalsa("epp", "eficiencia"), BASE + EPP + EFICIENCIA + SUCURSAL),
    ],
    ids=["sin_licencia", "sin_modulos", "solo_epp", "solo_eficiencia", "epp_y_eficiencia"],
)
def test_el_menu_muestra_solo_lo_que_la_licencia_incluye(
    licencia: LicenciaFalsa | None, botones: list[tuple[str, str]]
) -> None:
    assert botones_del_menu(licencia) == botones


@pytest.mark.parametrize(
    ("licencia", "incluye"),
    [(None, False), (LicenciaFalsa("epp"), False), (LicenciaFalsa("eficiencia"), True)],
    ids=["sin_licencia", "solo_epp", "con_eficiencia"],
)
def test_la_eficiencia_se_habilita_solo_con_su_modulo(
    licencia: LicenciaFalsa | None, incluye: bool
) -> None:
    assert incluye_eficiencia(licencia) is incluye
