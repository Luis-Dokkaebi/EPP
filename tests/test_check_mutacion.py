"""Puntaje de mutación leído de la caché de mutmut (CLAUDE.md §7)."""

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from scripts.check_mutacion import ResultadoMutacion, leer_resultados, main
from tests.utilidades_scripts import ejecutar_script

UMBRAL_CODIGO_NUEVO = 85.0


def _crear_cache(ruta: Path, estados_por_archivo: dict[str, list[str]]) -> Path:
    cache = ruta / ".mutmut-cache"
    conexion = sqlite3.connect(cache)
    conexion.executescript(
        "CREATE TABLE SourceFile (id INTEGER PRIMARY KEY, filename TEXT, hash TEXT);"
        "CREATE TABLE Line (id INTEGER PRIMARY KEY, sourcefile INTEGER, line TEXT,"
        " line_number INTEGER);"
        "CREATE TABLE Mutant (id INTEGER PRIMARY KEY, line INTEGER, 'index' INTEGER,"
        " tested_against_hash TEXT, status TEXT);"
    )
    for numero, (archivo, estados) in enumerate(estados_por_archivo.items(), start=1):
        conexion.execute("INSERT INTO SourceFile VALUES (?, ?, '')", (numero, archivo))
        conexion.execute("INSERT INTO Line VALUES (?, ?, 'x = 1', 1)", (numero, numero))
        conexion.executemany(
            "INSERT INTO Mutant (line, 'index', status) VALUES (?, 0, ?)",
            [(numero, estado) for estado in estados],
        )
    conexion.commit()
    conexion.close()
    return cache


def test_leer_resultados_cuenta_muertos_y_sobrevivientes(tmp_path: Path) -> None:
    cache = _crear_cache(
        tmp_path,
        {"src/a.py": ["ok_killed", "ok_suspicious", "bad_survived", "bad_timeout"]},
    )

    resultados = leer_resultados(cache)

    assert resultados == [
        ResultadoMutacion(archivo="src/a.py", muertos=2, sobrevivientes=2, sin_probar=0)
    ]


def test_resultado_puntaje_es_porcentaje_de_muertos() -> None:
    resultado = ResultadoMutacion(archivo="a.py", muertos=17, sobrevivientes=3, sin_probar=0)

    assert resultado.puntaje == pytest.approx(85.0)


def test_resultado_sin_mutantes_tiene_puntaje_cien() -> None:
    resultado = ResultadoMutacion(archivo="a.py", muertos=0, sobrevivientes=0, sin_probar=0)

    assert resultado.puntaje == pytest.approx(100.0)


def test_main_falla_si_un_archivo_queda_bajo_el_umbral(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": ["ok_killed", "bad_survived"]})

    codigo = main([str(cache), str(UMBRAL_CODIGO_NUEVO)])

    assert codigo == 1
    assert "src/a.py: 50.0 % < 85.0 %" in capsys.readouterr().out


def test_main_falla_si_quedan_mutantes_sin_probar(tmp_path: Path) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": ["ok_killed", "untested"]})

    assert main([str(cache), str(UMBRAL_CODIGO_NUEVO)]) == 1


def test_main_aprueba_si_todos_superan_el_umbral(tmp_path: Path) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": ["ok_killed"] * 9 + ["bad_survived"]})

    assert main([str(cache), str(UMBRAL_CODIGO_NUEVO)]) == 0


MUERTOS_EN_EL_LIMITE = 17
SOBREVIVIENTES_EN_EL_LIMITE = 3


def test_resultado_mutacion_es_inmutable() -> None:
    resultado = ResultadoMutacion(archivo="a.py", muertos=1, sobrevivientes=0, sin_probar=0)
    campo = "muertos"

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(resultado, campo, 2)


def test_main_sin_umbral_usa_85_y_aprueba_justo_en_el_limite(tmp_path: Path) -> None:
    estados = ["ok_killed"] * MUERTOS_EN_EL_LIMITE + ["bad_survived"] * SOBREVIVIENTES_EN_EL_LIMITE
    cache = _crear_cache(tmp_path, {"src/a.py": estados})

    assert main([str(cache)]) == 0


def test_main_respeta_el_umbral_recibido(tmp_path: Path) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": ["ok_killed", "bad_survived"]})

    assert main([str(cache), "50"]) == 0


def test_main_sin_argumentos_lee_la_cache_del_directorio_actual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _crear_cache(tmp_path, {"src/a.py": ["bad_survived"]})
    monkeypatch.chdir(tmp_path)

    assert main([]) == 1


def test_main_reporta_todos_los_archivos_que_fallan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": ["untested"], "src/b.py": ["bad_survived"]})

    main([str(cache), str(UMBRAL_CODIGO_NUEVO)])

    salida = capsys.readouterr().out.splitlines()
    assert salida == [
        "src/a.py: 100.0 % (ResultadoMutacion(archivo='src/a.py', muertos=0, sobrevivientes=0, "
        "sin_probar=1))",
        "src/b.py: 0.0 % (ResultadoMutacion(archivo='src/b.py', muertos=0, sobrevivientes=1, "
        "sin_probar=0))",
        "src/a.py: 1 mutantes sin probar",
        "src/b.py: 0.0 % < 85.0 %. Mata los sobrevivientes con pruebas nuevas "
        "(`mutmut results` / `mutmut show <id>`); los equivalentes van en "
        "docs/quality/mutantes_equivalentes.md.",
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("estado", "codigo_esperado"),
    [("ok_killed", 0), ("bad_survived", 1)],
    ids=["verde", "rojo"],
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, estado: str, codigo_esperado: int
) -> None:
    cache = _crear_cache(tmp_path, {"src/a.py": [estado]})

    resultado = ejecutar_script(
        "check_mutacion.py", str(cache), str(UMBRAL_CODIGO_NUEVO), carpeta=tmp_path
    )

    assert resultado.returncode == codigo_esperado, resultado.stdout + resultado.stderr
