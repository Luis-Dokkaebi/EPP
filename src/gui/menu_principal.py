"""Qué ofrece el menú de la ventana principal según los módulos de la licencia.

Decisión M-1 (SPEC/10): se vende casco y chaleco. Los reportes de eficiencia heredados solo se
muestran si la licencia incluye el módulo `eficiencia`, igual que las vistas de EPP con `epp`.
"""

from src.composicion_epp import LicenciaPort, modulo_habilitado

MODULO_EFICIENCIA = "eficiencia"

Boton = tuple[str, str]  # texto del botón y nombre de la vista que abre


def incluye_eficiencia(licencia: LicenciaPort | None) -> bool:
    return licencia is not None and licencia.incluye_modulo(MODULO_EFICIENCIA)


def botones_del_menu(licencia: LicenciaPort | None) -> list[Boton]:
    botones = [
        ("Monitoreo en Vivo", "Dashboard"),
        ("Gestión de Empleados", "Empleados"),
        ("Configuración de Zonas", "Zonas"),
    ]
    if modulo_habilitado(licencia):
        botones += [("Alertas EPP", "AlertasEPP"), ("Cumplimiento EPP", "CumplimientoEPP")]
    if incluye_eficiencia(licencia):
        botones.append(("Reportes Históricos", "Reportes"))
    return [*botones, ("Cambiar Sucursal", "Tenant")]
