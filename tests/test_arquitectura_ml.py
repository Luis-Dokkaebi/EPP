"""El producto no importa el código de entrenamiento ni las herramientas (SPEC/9 §3.1)."""

import configparser

from tests.utilidades_scripts import RAIZ


def test_import_linter_prohibe_que_src_importe_ml_o_tools() -> None:
    configuracion = configparser.ConfigParser()
    configuracion.read(RAIZ / ".importlinter", encoding="utf-8")

    contrato = configuracion["importlinter:contract:producto-sin-entrenamiento"]

    assert contrato["type"] == "forbidden"
    assert contrato["source_modules"].split() == ["src"]
    assert contrato["forbidden_modules"].split() == ["ml", "tools"]
