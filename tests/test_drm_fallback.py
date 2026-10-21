"""DRM: si las políticas de dominio bloquean WMI, el machine_id usa el respaldo MAC/BIOS."""

import sys
from unittest.mock import MagicMock, patch

from src.security.drm import DRMValidator

LONGITUD_SHA256_HEX = 64


def test_drm_wmi_denegado_genera_machine_id_de_respaldo_sha256() -> None:
    # Arrange: un doble de wmi permite probar el respaldo también fuera de Windows.
    wmi_denegado = MagicMock()
    wmi_denegado.WMI.side_effect = PermissionError("Acceso denegado por políticas de dominio")

    # Act
    with patch.dict(sys.modules, {"wmi": wmi_denegado}):
        machine_id = DRMValidator().machine_id

    # Assert
    assert len(machine_id) == LONGITUD_SHA256_HEX
