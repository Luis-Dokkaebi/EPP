"""Trinquete de complejidad: radon contra los waivers de docs/quality/metricas.json."""

import json
from pathlib import Path

import pytest

from scripts.check_trinquete import (
    archivos_poco_mantenibles,
    bloques_complejos,
    evaluar_trinquete,
    main,
)
from tests.utilidades_scripts import RAIZ, ejecutar_script

FUNCION_SIMPLE = "def simple(x):\n    return x\n"
RAMAS_PARA_RANGO_C = 11


def _funcion_compleja(nombre: str) -> str:
    ramas = "".join(f"    if x == {i}:\n        return {i}\n" for i in range(RAMAS_PARA_RANGO_C))
    return f"def {nombre}(x):\n{ramas}    return -1\n"


def _crear_fuente(raiz: Path, nombre: str, codigo: str) -> None:
    (raiz / nombre).write_text(codigo, encoding="utf-8")


def _crear_metricas(ruta: Path, permitidos_cc: list[str]) -> Path:
    archivo = ruta / "metricas.json"
    archivo.write_text(
        json.dumps({"radon_cc_waiver": permitidos_cc, "radon_mi_waiver": []}), encoding="utf-8"
    )
    return archivo


def test_bloques_complejos_detecta_funcion_de_rango_c(tmp_path: Path) -> None:
    _crear_fuente(tmp_path, "mod.py", _funcion_compleja("enredada") + FUNCION_SIMPLE)

    encontrados = bloques_complejos(tmp_path)

    assert encontrados == [f"{(tmp_path / 'mod.py').as_posix()}:enredada"]


def test_bloques_complejos_ignora_funciones_simples(tmp_path: Path) -> None:
    _crear_fuente(tmp_path, "mod.py", FUNCION_SIMPLE)

    assert bloques_complejos(tmp_path) == []


def test_evaluar_trinquete_incumplimiento_nuevo_falla_con_instruccion() -> None:
    errores = evaluar_trinquete(encontrados=["a.py:f", "b.py:g"], permitidos=["a.py:f"])

    assert errores == [
        "b.py:g supera la complejidad permitida (rango C o peor): divídela en funciones "
        "más chicas; el código nuevo no admite waivers (CLAUDE.md §3)."
    ]


def test_evaluar_trinquete_waiver_sobrante_obliga_a_quitarlo() -> None:
    errores = evaluar_trinquete(encontrados=[], permitidos=["a.py:f"])

    assert errores == [
        "a.py:f ya cumple: quítalo de docs/quality/metricas.json (el trinquete solo baja la deuda)."
    ]


def test_evaluar_trinquete_sin_diferencias_no_reporta_errores() -> None:
    assert evaluar_trinquete(encontrados=["a.py:f"], permitidos=["a.py:f"]) == []


def test_main_devuelve_cero_si_la_deuda_coincide_con_los_waivers(tmp_path: Path) -> None:
    _crear_fuente(tmp_path, "mod.py", _funcion_compleja("vieja"))
    metricas = _crear_metricas(tmp_path, [f"{(tmp_path / 'mod.py').as_posix()}:vieja"])

    codigo = main([str(tmp_path), str(metricas)])

    assert codigo == 0


def test_main_devuelve_uno_e_imprime_si_aparece_deuda_nueva(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_fuente(tmp_path, "mod.py", _funcion_compleja("nueva"))
    metricas = _crear_metricas(tmp_path, [])

    codigo = main([str(tmp_path), str(metricas)])

    assert codigo == 1
    assert "nueva supera la complejidad permitida" in capsys.readouterr().out


PARAMETROS = 12
RAMAS_PARA_MI_BAJO = 60
RAMAS_PARA_MI_PESIMO = 80
LINEAS_DE_DOCUMENTACION = 40


def _codigo_poco_mantenible(ramas: int, lineas_documentacion: int) -> str:
    documentacion = "\n".join(f"Línea de documentación {i}." for i in range(lineas_documentacion))
    argumentos = ",".join(f"a{i}" for i in range(PARAMETROS))
    cuerpo = "".join(
        f"    if a{i % PARAMETROS} > {i}:\n"
        f"        a{(i + 1) % PARAMETROS} = a{(i + 2) % PARAMETROS} * {i} + "
        f"a{(i + 3) % PARAMETROS} - {i + 1} / (a{(i + 4) % PARAMETROS} or 1)\n"
        for i in range(ramas)
    )
    return f'"""{documentacion}\n"""\ndef f({argumentos}):\n{cuerpo}    return a0\n'


def test_archivos_poco_mantenibles_detecta_indice_c(tmp_path: Path) -> None:
    _crear_fuente(tmp_path, "pesimo.py", _codigo_poco_mantenible(RAMAS_PARA_MI_PESIMO, 0))
    _crear_fuente(tmp_path, "simple.py", FUNCION_SIMPLE)

    assert archivos_poco_mantenibles(tmp_path) == [(tmp_path / "pesimo.py").as_posix()]


def test_archivos_poco_mantenibles_cuenta_la_documentacion_como_comentario(
    tmp_path: Path,
) -> None:
    codigo = _codigo_poco_mantenible(RAMAS_PARA_MI_BAJO, LINEAS_DE_DOCUMENTACION)
    _crear_fuente(tmp_path, "documentado.py", codigo)

    assert archivos_poco_mantenibles(tmp_path) == []


def test_main_imprime_cada_error_en_su_propia_linea(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metricas = _crear_metricas(tmp_path, ["fantasma.py:f"])

    main([str(tmp_path), str(metricas)])

    assert capsys.readouterr().out == (
        "fantasma.py:f ya cumple: quítalo de docs/quality/metricas.json "
        "(el trinquete solo baja la deuda).\n"
    )


def test_main_sin_argumentos_valida_la_deuda_real_del_repositorio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(RAIZ)

    assert main([]) == 0


def test_main_con_solo_la_raiz_usa_las_metricas_del_repositorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _crear_fuente(tmp_path, "mod.py", FUNCION_SIMPLE)
    monkeypatch.chdir(RAIZ)

    assert main([str(tmp_path)]) == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("permitidos", "codigo_esperado"), [(["vieja"], 0), ([], 1)], ids=["verde", "rojo"]
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, permitidos: list[str], codigo_esperado: int
) -> None:
    _crear_fuente(tmp_path, "mod.py", _funcion_compleja("vieja"))
    ruta = (tmp_path / "mod.py").as_posix()
    metricas = _crear_metricas(tmp_path, [f"{ruta}:{nombre}" for nombre in permitidos])

    resultado = ejecutar_script("check_trinquete.py", str(tmp_path), str(metricas))

    assert resultado.returncode == codigo_esperado, resultado.stdout + resultado.stderr
