# tests/test_obfuscate_pipeline.py
# TASK-4.4: el pipeline de build ofusca src/ + config/ con PyArmor en modo
# restrictivo, y gui_app.spec consume el codigo ofuscado en dist/obfuscated/.

import os
import sys
import importlib.util

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _load_obfuscate():
    spec = importlib.util.spec_from_file_location("obfuscate", os.path.join(ROOT, "obfuscate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.xfail(
    strict=True,
    reason=(
        "WAIVER-#8 (caduca 2027-01-19): obfuscate.py copia el código sin PyArmor y no define "
        "build_pyarmor_command; corregirlo exige la autorización D8 y la licencia de PyArmor"
    ),
)
def test_obfuscate_command_is_restrictive_pyarmor():
    ob = _load_obfuscate()
    cmd = ob.build_pyarmor_command()
    assert cmd[0] == "pyarmor" and cmd[1] == "gen"
    # Salida hacia dist/obfuscated y modo restrictivo (SPEC 1.6.3 / TASK-4.4.2)
    assert "-O" in cmd and os.path.join("dist", "obfuscated") in cmd
    assert "--restrict" in cmd and "1" in cmd
    # Ofusca tanto src como config (ambos importados por main_ui).
    assert "src" in cmd and "config" in cmd


def test_obfuscate_output_dir_matches_spec_entry():
    ob = _load_obfuscate()
    assert ob.OUTPUT_DIR == os.path.join("dist", "obfuscated")
    spec_text = open(os.path.join(ROOT, "gui_app.spec"), encoding="utf-8").read()
    # El .spec debe apuntar al main_ui ofuscado en esa misma carpeta.
    assert "obfuscated" in spec_text and "main_ui.py" in spec_text


def test_compilar_bat_invokes_obfuscation_before_pyinstaller():
    bat = open(os.path.join(ROOT, "compilar_exe.bat"), encoding="utf-8", errors="replace").read()
    assert "obfuscate.py" in bat
    assert "gui_app.spec" in bat
    # La ofuscacion debe ocurrir ANTES del empaquetado.
    assert bat.index("obfuscate.py") < bat.index("pyinstaller gui_app.spec")
