"""El runner de mutmut traduce cualquier falla de pytest al código 1 (único que mutmut cuenta)."""

from pathlib import Path

import pytest

from scripts.ejecutar_pruebas_mutacion import codigo_para_mutmut, main
from tests.utilidades_scripts import ejecutar_script

CODIGO_COLECCION_INTERRUMPIDA = 2
CODIGO_SIN_PRUEBAS = 5


@pytest.mark.parametrize(
    ("codigo_pytest", "esperado"),
    [(0, 0), (1, 1), (CODIGO_COLECCION_INTERRUMPIDA, 1), (CODIGO_SIN_PRUEBAS, 1)],
    ids=["verde", "fallo", "error-de-coleccion", "sin-pruebas"],
)
def test_codigo_para_mutmut_solo_cero_es_exito(codigo_pytest: int, esperado: int) -> None:
    assert codigo_para_mutmut(codigo_pytest) == esperado


def test_main_con_prueba_que_no_importa_devuelve_uno(tmp_path: Path) -> None:
    prueba = tmp_path / "test_roto.py"
    prueba.write_text("import modulo_que_no_existe\n", encoding="utf-8")

    assert main(["-q", "-p", "no:randomly", "-p", "no:cacheprovider", str(prueba)]) == 1


@pytest.mark.integration
def test_script_ejecutado_como_programa_corre_solo_las_pruebas_recibidas(tmp_path: Path) -> None:
    pruebas = tmp_path / "pruebas"
    pruebas.mkdir()
    (pruebas / "test_verde.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    vacia = tmp_path / "vacia"
    vacia.mkdir()

    resultado = ejecutar_script(
        "ejecutar_pruebas_mutacion.py", str(pruebas / "test_verde.py"), carpeta=vacia
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.integration
def test_script_ejecutado_como_programa_traduce_la_falla_a_uno(tmp_path: Path) -> None:
    prueba = tmp_path / "test_rojo.py"
    prueba.write_text("def test_falla():\n    raise AssertionError\n", encoding="utf-8")

    resultado = ejecutar_script("ejecutar_pruebas_mutacion.py", str(prueba), carpeta=tmp_path)

    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
