"""Longitud de archivo ≤ 500 líneas (CLAUDE.md §3), con trinquete para el código heredado."""

from pathlib import Path

import pytest

from scripts.check_tamano import LINEAS_MAXIMAS, archivos_demasiado_largos, main
from tests.utilidades_scripts import RAIZ, ejecutar_script


def _crear(raiz: Path, nombre: str, lineas: int) -> Path:
    archivo = raiz / nombre
    archivo.write_text("x = 1\n" * lineas, encoding="utf-8")
    return archivo


def test_archivos_demasiado_largos_detecta_el_que_supera_el_limite(tmp_path: Path) -> None:
    largo = _crear(tmp_path, "largo.py", LINEAS_MAXIMAS + 1)
    justo = _crear(tmp_path, "justo.py", LINEAS_MAXIMAS)

    assert archivos_demasiado_largos([largo, justo], permitidos=[]) == [
        f"{largo.as_posix()} tiene {LINEAS_MAXIMAS + 1} líneas (máximo {LINEAS_MAXIMAS}): "
        "divídelo por responsabilidad (CLAUDE.md §3)."
    ]


def test_archivos_demasiado_largos_respeta_el_waiver_del_codigo_heredado(tmp_path: Path) -> None:
    largo = _crear(tmp_path, "heredado.py", LINEAS_MAXIMAS + 1)

    assert archivos_demasiado_largos([largo], permitidos=[largo.as_posix()]) == []


def test_main_sin_archivos_revisa_el_repositorio_contra_metricas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(RAIZ)

    assert main([]) == 0


def test_main_imprime_cada_archivo_largo_y_devuelve_uno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    largo = _crear(tmp_path, "largo.py", LINEAS_MAXIMAS + 2)
    monkeypatch.chdir(RAIZ)

    codigo = main([str(largo)])

    assert codigo == 1
    assert capsys.readouterr().out == (
        f"{largo.as_posix()} tiene {LINEAS_MAXIMAS + 2} líneas (máximo {LINEAS_MAXIMAS}): "
        "divídelo por responsabilidad (CLAUDE.md §3).\n"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("lineas", "codigo"), [(1, 0), (LINEAS_MAXIMAS + 1, 1)], ids=["ok", "largo"]
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, lineas: int, codigo: int
) -> None:
    archivo = _crear(tmp_path, "modulo.py", lineas)

    resultado = ejecutar_script("check_tamano.py", str(archivo))

    assert resultado.returncode == codigo, resultado.stdout + resultado.stderr
