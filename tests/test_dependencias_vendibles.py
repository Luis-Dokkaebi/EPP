"""El runtime que viaja en el ejecutable no trae paquetes que impidan venderlo cerrado."""

import re

import pytest

from tests.utilidades_scripts import RAIZ

# AGPL (ultralytics), GPL (tkcalendar), modelo de dlib con uso comercial restringido
# (face_recognition), ofuscador sin licencia comercial (pyarmor) y el empaquetador retirado.
PROHIBIDOS = ("ultralytics", "torch", "torchvision", "tkcalendar", "face_recognition", "dlib",
              "pyarmor", "pyinstaller")  # fmt: skip
NOMBRE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def _paquetes(archivo: str) -> set[str]:
    lineas = (RAIZ / archivo).read_text(encoding="utf-8").splitlines()
    coincidencias = (NOMBRE.match(linea) for linea in lineas if not linea.lstrip().startswith("#"))
    return {c.group(1).lower().replace("-", "_") for c in coincidencias if c}


@pytest.mark.parametrize("archivo", ["requirements.txt", "requirements-ci.txt"])
def test_el_runtime_no_trae_paquetes_que_impidan_vender(archivo: str) -> None:
    assert _paquetes(archivo).isdisjoint(PROHIBIDOS)


def test_el_build_usa_nuitka_apache_y_no_el_empaquetador_retirado() -> None:
    paquetes = _paquetes("requirements-build.txt")

    assert "nuitka" in paquetes
    assert paquetes.isdisjoint(PROHIBIDOS)
    assert "nuitka==2.8.10" in (RAIZ / "requirements-build.txt").read_text(encoding="utf-8")


def test_no_quedan_pesos_de_yolo_ni_ruedas_de_dlib_en_el_repositorio() -> None:
    sobrantes = [*RAIZ.glob("*.pt"), *RAIZ.glob("models/**/*.pt"), *RAIZ.glob("dlib-*.whl")]

    assert sobrantes == []
