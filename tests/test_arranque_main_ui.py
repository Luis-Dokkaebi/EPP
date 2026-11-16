"""Arranque de la app (`python src/main_ui.py`): sin licencia activada no se abre nada más.

CR-06 y SPEC/10 T-05: el bloque de arranque pide la licencia y, si la ventana se cierra sin
activarla, termina antes de elegir sucursal.
"""

import runpy
from collections.abc import Iterator
from typing import Any

import customtkinter as ctk
import pytest

# Crea ventanas de Tk: necesita pantalla, fuera del hook rápido (como tests/test_vistas_epp.py).
pytestmark = pytest.mark.integration


class LlegoALaSucursalError(Exception):
    """El arranque pasó la licencia y abrió la ventana de selección de sucursal."""


class ValidadorSinLicencia:
    def validate_license(self) -> bool:
        return False


@pytest.fixture
def arranque(
    monkeypatch: pytest.MonkeyPatch, importacion_sin_efectos: None
) -> Iterator[dict[str, Any]]:
    """Arranque con licencia ausente; `activa` es si el usuario pega una licencia válida."""
    estado: dict[str, Any] = {"activa": False, "raices": []}

    def pedir(raiz: ctk.CTk, licencia: object) -> bool:
        estado["raices"].append(raiz)
        return bool(estado["activa"])

    def esperar(_raiz: ctk.CTk, _ventana: object) -> None:
        raise LlegoALaSucursalError

    monkeypatch.setattr("src.security.drm.DRMValidator", ValidadorSinLicencia)
    monkeypatch.setattr("src.gui.ventana_licencia.pedir_licencia", pedir)
    monkeypatch.setattr("src.security.crash_logger.install_global_excepthook", lambda: None)
    monkeypatch.setattr(ctk.CTk, "wait_window", esperar)
    yield estado
    for raiz in estado["raices"]:
        raiz.destroy()


def test_sin_activar_la_licencia_el_arranque_termina_antes_de_elegir_sucursal(
    arranque: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as salida:
        runpy.run_module("src.main_ui", run_name="__main__")

    assert salida.value.code == 0
    assert len(arranque["raices"]) == 1
    assert capsys.readouterr().out.endswith("[VMS] Activación no completada. Cerrando.\n")


def test_con_la_licencia_activada_el_arranque_sigue_a_la_seleccion_de_sucursal(
    arranque: dict[str, Any],
) -> None:
    arranque["activa"] = True

    with pytest.raises(LlegoALaSucursalError):
        runpy.run_module("src.main_ui", run_name="__main__")

    assert len(arranque["raices"]) == 1
