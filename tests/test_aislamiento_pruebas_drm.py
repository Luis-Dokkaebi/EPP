"""Regresión: las pruebas heredadas de DRM no rompen el doble de licencia de las siguientes.

`tests/test_drm_rsa_b2b.py` borraba `src.security.drm` de `sys.modules` y el paquete
`src.security` quedaba apuntando al módulo viejo. Un `monkeypatch` posterior parchaba ese módulo
viejo, pero el código importaba uno nuevo con el `DRMValidator` real. Con el orden aleatorio de
pytest-randomly falló el gate de Windows del PR Luis-Dokkaebi/EPP#135.

Se corre en un intérprete aparte para fijar el orden que dispara el defecto.
"""

import subprocess
import sys

import pytest

from tests.utilidades_scripts import RAIZ

pytestmark = [pytest.mark.integration, pytest.mark.slow]

PRUEBA_CON_DOBLE_DE_LICENCIA = (
    "tests/test_main_headless.py::test_la_licencia_del_equipo_se_valida_antes_de_usarla"
)


@pytest.mark.parametrize(
    "prueba_heredada",
    [
        "tests/test_drm_rsa_b2b.py::TestWMIFallback::test_wmi_crash_fallback",
        "tests/test_drm_rsa_b2b.py::TestWMIFallback::test_fallback_hash_is_different_from_normal",
    ],
    ids=["fallback_wmi", "hash_fallback_distinto"],
)
def test_una_prueba_de_drm_heredada_no_rompe_el_doble_de_licencia_de_la_siguiente(
    prueba_heredada: str,
) -> None:
    # S603: el intérprete de la suite con argumentos fijos.
    resultado = subprocess.run(
        [  # noqa: S603
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            prueba_heredada,
            PRUEBA_CON_DOBLE_DE_LICENCIA,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0, resultado.stdout
