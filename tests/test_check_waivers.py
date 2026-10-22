"""Los waivers de docs/quality/waivers.md caducan (CLAUDE.md §15.4)."""

from datetime import date
from pathlib import Path

import pytest
from freezegun import freeze_time

from scripts.check_waivers import main, waivers_vencidos
from tests.utilidades_scripts import RAIZ, ejecutar_script

TABLA = (
    "| ID | Regla | Archivo | Motivo | Riesgo | Fecha límite | Issue |\n"
    "|----|-------|---------|--------|--------|--------------|-------|\n"
    "| W-001 | ruff | a.py | deuda | Bajo | 2027-01-19 | #2 |\n"
    "| W-002 | mypy | b.py | deuda | Medio | 2026-12-01 | #4 |\n"
)


def test_waivers_vencidos_lista_los_que_pasaron_su_fecha() -> None:
    vencidos = waivers_vencidos(TABLA, hoy=date(2026, 12, 2))

    assert vencidos == ["W-002 (#4) venció el 2026-12-01"]


def test_waivers_vencidos_el_dia_limite_sigue_vigente() -> None:
    assert waivers_vencidos(TABLA, hoy=date(2026, 12, 1)) == []


def test_waivers_vencidos_fila_sin_fecha_valida_falla_ruidosamente() -> None:
    tabla_rota = "| W-009 | ruff | a.py | deuda | Bajo | pronto | #9 |\n"

    with pytest.raises(ValueError, match="W-009"):
        waivers_vencidos(tabla_rota, hoy=date(2026, 12, 1))


def test_main_falla_con_waiver_vencido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archivo = tmp_path / "waivers.md"
    archivo.write_text(TABLA, encoding="utf-8")

    codigo = main([str(archivo), "2027-02-01"])

    assert codigo == 1
    assert "renueva el waiver con aprobación humana o paga la deuda" in capsys.readouterr().out


def test_main_sin_vencidos_devuelve_cero(tmp_path: Path) -> None:
    archivo = tmp_path / "waivers.md"
    archivo.write_text(TABLA, encoding="utf-8")

    assert main([str(archivo), "2026-11-01"]) == 0


def test_main_imprime_un_aviso_por_waiver_vencido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "waivers.md"
    archivo.write_text(TABLA, encoding="utf-8")

    main([str(archivo), "2026-12-02"])

    assert capsys.readouterr().out == (
        "W-002 (#4) venció el 2026-12-01: renueva el waiver con aprobación humana o paga la "
        "deuda (§15.4).\n"
    )


def test_waivers_vencidos_mensaje_de_fecha_invalida_nombra_la_fila() -> None:
    tabla_rota = "| W-009 | ruff | a.py | deuda | Bajo | pronto | #9 |\n"

    with pytest.raises(ValueError) as error:
        waivers_vencidos(tabla_rota, hoy=date(2026, 12, 1))

    assert str(error.value) == "W-009: fecha límite inválida 'pronto'"


@freeze_time("2026-11-01")
def test_main_sin_argumentos_lee_los_waivers_del_repositorio_con_la_fecha_de_hoy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(RAIZ)

    assert main([]) == 0


@freeze_time("2027-06-01")
def test_main_con_solo_el_archivo_usa_la_fecha_de_hoy(tmp_path: Path) -> None:
    archivo = tmp_path / "waivers.md"
    archivo.write_text(TABLA, encoding="utf-8")

    assert main([str(archivo)]) == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("hoy", "codigo_esperado"), [("2026-11-01", 0), ("2027-02-01", 1)], ids=["verde", "rojo"]
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, hoy: str, codigo_esperado: int
) -> None:
    archivo = tmp_path / "waivers.md"
    archivo.write_text(TABLA, encoding="utf-8")

    resultado = ejecutar_script("check_waivers.py", str(archivo), hoy)

    assert resultado.returncode == codigo_esperado, resultado.stdout + resultado.stderr
