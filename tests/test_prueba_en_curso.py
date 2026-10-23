"""La marca de la prueba en curso para diagnosticar crashes nativos en la CI (issue #37)."""

from pathlib import Path

import pytest

from tests import prueba_en_curso


def test_anotar_escribe_la_prueba_en_la_carpeta_de_reportes(tmp_path: Path) -> None:
    prueba_en_curso.anotar("tests/test_x.py::test_y", {"GATE_REPORTES": str(tmp_path)})

    assert (tmp_path / prueba_en_curso.ARCHIVO).read_text(encoding="utf-8") == (
        "tests/test_x.py::test_y\n"
    )


def test_anotar_reemplaza_la_prueba_anterior(tmp_path: Path) -> None:
    entorno = {"GATE_REPORTES": str(tmp_path)}
    prueba_en_curso.anotar("tests/test_x.py::test_y", entorno)

    prueba_en_curso.anotar("tests/test_x.py::test_z", entorno)

    assert (tmp_path / prueba_en_curso.ARCHIVO).read_text(encoding="utf-8") == (
        "tests/test_x.py::test_z\n"
    )


def test_anotar_sin_carpeta_de_reportes_no_escribe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    prueba_en_curso.anotar("tests/test_x.py::test_y", {})

    assert list(tmp_path.iterdir()) == []
