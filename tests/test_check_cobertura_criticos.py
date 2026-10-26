"""100 % de líneas y ramas en los módulos críticos (CLAUDE.md §6), con trinquete (W-012)."""

import json
from pathlib import Path

import pytest

from scripts.check_cobertura_criticos import MODULOS_CRITICOS, incumplimientos, main
from tests.utilidades_scripts import RAIZ, ejecutar_script

CRITICO = "src/storage/repositorio.py"


def _resumen(lineas: int = 0, ramas: int = 0) -> dict[str, dict[str, int]]:
    return {"summary": {"missing_lines": lineas, "missing_branches": ramas}}


def test_incumplimientos_archivo_critico_completo_no_reporta_nada() -> None:
    assert incumplimientos({CRITICO: _resumen()}, permitidos=[]) == []


@pytest.mark.parametrize(("lineas", "ramas"), [(3, 0), (0, 2)], ids=["lineas", "ramas"])
def test_incumplimientos_archivo_critico_incompleto_reporta_lo_que_falta(
    lineas: int, ramas: int
) -> None:
    resultado = incumplimientos({CRITICO: _resumen(lineas, ramas)}, permitidos=[])

    assert resultado == [
        f"{CRITICO}: {lineas} líneas y {ramas} ramas sin cubrir; los módulos críticos exigen "
        "100 % (CLAUDE.md §6)."
    ]


@pytest.mark.parametrize("modulo", MODULOS_CRITICOS)
def test_incumplimientos_cada_modulo_critico_se_controla(modulo: str) -> None:
    archivo = f"{modulo}uno.py"

    assert len(incumplimientos({archivo: _resumen(lineas=1)}, permitidos=[])) == 1


def test_los_modulos_criticos_son_los_de_claude_md() -> None:
    assert MODULOS_CRITICOS == ("src/security/", "src/storage/", "src/analysis/", "src/ppe/")


@pytest.mark.parametrize("archivo", ["src/gui/vista.py", "src/storage_viejo/a.py", "ml/x.py"])
def test_incumplimientos_ignora_los_archivos_no_criticos(archivo: str) -> None:
    assert incumplimientos({archivo: _resumen(lineas=5, ramas=5)}, permitidos=[]) == []


def test_incumplimientos_respeta_el_waiver_del_codigo_heredado() -> None:
    assert incumplimientos({CRITICO: _resumen(lineas=4)}, permitidos=[CRITICO]) == []


def test_incumplimientos_exige_quitar_del_waiver_el_archivo_que_ya_cumple() -> None:
    resultado = incumplimientos({CRITICO: _resumen()}, permitidos=[CRITICO])

    assert resultado == [
        f"{CRITICO} ya cubre el 100 %: quítalo de cobertura_critica_waiver (trinquete P4)."
    ]


def test_incumplimientos_exige_quitar_del_waiver_el_archivo_que_no_existe() -> None:
    resultado = incumplimientos({}, permitidos=[CRITICO])

    assert resultado == [
        f"{CRITICO} figura en cobertura_critica_waiver y no aparece en la cobertura: quítalo."
    ]


def test_incumplimientos_acepta_las_rutas_de_windows() -> None:
    resultado = incumplimientos({"src\\storage\\repositorio.py": _resumen()}, [CRITICO])

    assert resultado == [
        f"{CRITICO} ya cubre el 100 %: quítalo de cobertura_critica_waiver (trinquete P4)."
    ]


def test_el_waiver_de_metricas_solo_lista_archivos_criticos_existentes() -> None:
    metricas = json.loads((RAIZ / "docs/quality/metricas.json").read_text(encoding="utf-8"))

    permitidos = metricas["cobertura_critica_waiver"]

    assert permitidos
    assert all(archivo.startswith(MODULOS_CRITICOS) for archivo in permitidos)
    assert all((RAIZ / archivo).is_file() for archivo in permitidos)


def _preparar(carpeta: Path, archivos: dict[str, object], permitidos: list[str]) -> Path:
    (carpeta / "docs/quality").mkdir(parents=True)
    metricas = {"cobertura_critica_waiver": permitidos}
    (carpeta / "docs/quality/metricas.json").write_text(json.dumps(metricas), encoding="utf-8")
    cobertura = carpeta / "cobertura.json"
    cobertura.write_text(json.dumps({"files": archivos}), encoding="utf-8")
    return cobertura


def test_main_sin_incumplimientos_devuelve_cero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cobertura = _preparar(tmp_path, {CRITICO: _resumen()}, permitidos=[])
    monkeypatch.chdir(tmp_path)

    assert main([str(cobertura)]) == 0
    assert capsys.readouterr().out == ""


def test_main_imprime_cada_incumplimiento_y_devuelve_uno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    otro = "src/ppe/regla.py"
    archivos = {CRITICO: _resumen(lineas=1), otro: _resumen(ramas=1)}
    cobertura = _preparar(tmp_path, archivos, permitidos=[])
    monkeypatch.chdir(tmp_path)

    codigo = main([str(cobertura)])

    assert codigo == 1
    assert capsys.readouterr().out == (
        f"{CRITICO}: 1 líneas y 0 ramas sin cubrir; los módulos críticos exigen 100 % "
        "(CLAUDE.md §6).\n"
        f"{otro}: 0 líneas y 1 ramas sin cubrir; los módulos críticos exigen 100 % "
        "(CLAUDE.md §6).\n"
    )


@pytest.mark.integration
@pytest.mark.parametrize(("lineas", "codigo"), [(0, 0), (1, 1)], ids=["ok", "incompleto"])
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, lineas: int, codigo: int
) -> None:
    cobertura = _preparar(tmp_path, {CRITICO: _resumen(lineas=lineas)}, permitidos=[])

    resultado = ejecutar_script("check_cobertura_criticos.py", str(cobertura), carpeta=tmp_path)

    assert resultado.returncode == codigo, resultado.stdout + resultado.stderr
