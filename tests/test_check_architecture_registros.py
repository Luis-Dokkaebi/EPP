"""check_architecture.py no debe apagar los loggers del proceso que lo llama.

import-linter configura su logging con `dictConfig`, que por omisión deshabilita todos los loggers
ya creados; dentro de la suite eso silenciaba los registros de otros módulos según el orden.
"""

import logging

import pytest

from scripts.check_architecture import main
from tests.utilidades_scripts import RAIZ


def test_check_architecture_conserva_habilitados_los_loggers_existentes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(RAIZ)
    registrador = logging.getLogger("tests.registrador_previo")

    main([".importlinter"])

    capsys.readouterr()
    assert registrador.disabled is False


def test_check_architecture_respeta_los_loggers_que_ya_estaban_deshabilitados(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(RAIZ)
    registrador = logging.getLogger("tests.registrador_apagado")
    monkeypatch.setattr(registrador, "disabled", True)

    main([".importlinter"])

    capsys.readouterr()
    assert registrador.disabled is True
