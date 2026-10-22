"""Línea de comandos del acuerdo entre etiquetadores (docs/runbooks/etiquetado.md)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.coco_sintetico import ID_CABEZA, ID_CASCO, ID_CHALECO, ID_PERSONA, etiquetado
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS
from tools.acuerdo_etiquetado import main

NO_APROBADO, INVALIDO = 1, 2
UMBRAL = 0.8
PERSONA = (ID_PERSONA, [0, 0, 40, 90])
CABEZA = (ID_CABEZA, [10, 0, 20, 20])
CASCO = (ID_CASCO, [10, 0, 20, 12])
CHALECO = (ID_CHALECO, [5, 30, 30, 30])


def _guardar(carpeta: Path, nombre: str, coco: dict[str, Any]) -> str:
    ruta = carpeta / nombre
    ruta.write_text(json.dumps(coco), encoding="utf-8")
    return str(ruta)


def _rutas(carpeta: Path, coco_b: dict[str, Any] | None = None) -> list[str]:
    completo = etiquetado(PERSONA, CABEZA, CASCO, CHALECO)
    return [
        _guardar(carpeta, "a.json", completo),
        _guardar(carpeta, "b.json", coco_b or completo),
    ]


def test_main_aprueba_si_todas_las_clases_superan_el_umbral(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main([*_rutas(tmp_path), "--umbral", str(UMBRAL)])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "casco: cajas A 1, cajas B 1, coincidencias 1, acuerdo 1.00, IoU medio 1.00" in salida
    assert f"Acuerdo aprobado con el umbral {UMBRAL}." in salida


def test_main_sin_umbral_informa_la_medicion_y_no_aprueba(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main(_rutas(tmp_path))

    salida = capsys.readouterr()
    assert codigo == NO_APROBADO
    assert "kappa de Cohen: 1.00" in salida.out
    assert "Umbral de acuerdo PENDIENTE" in salida.err


def test_main_lista_las_clases_a_redefinir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sin_casco = etiquetado(PERSONA, CABEZA, CHALECO)

    codigo = main([*_rutas(tmp_path, sin_casco), "--umbral", str(UMBRAL)])

    salida = capsys.readouterr()
    assert codigo == NO_APROBADO
    assert "casco: cajas A 1, cajas B 0, coincidencias 0, acuerdo 0.00, IoU medio -" in salida.out
    assert "Redefinir en la guía y volver a etiquetar: casco." in salida.err


def test_main_rechaza_etiquetados_no_comparables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    otra_imagen = etiquetado()
    otra_imagen["images"][0]["file_name"] = "cam-09_20261021_083005_0001.jpg"

    codigo = main(_rutas(tmp_path, otra_imagen))

    assert codigo == INVALIDO
    assert "mismas imágenes" in capsys.readouterr().err


def test_main_guarda_el_reporte_en_json(tmp_path: Path) -> None:
    reporte = tmp_path / "acuerdo.json"

    main([*_rutas(tmp_path), "--umbral", str(UMBRAL), "--reporte", str(reporte)])

    contenido = json.loads(reporte.read_text(encoding="utf-8"))
    assert (contenido["kappa"], contenido["umbral"]) == (1.0, UMBRAL)
    assert contenido["clases_a_redefinir"] == []
    assert contenido["por_clase"]["casco"] == {
        "cajas_a": 1,
        "cajas_b": 1,
        "coincidencias": 1,
        "acuerdo": 1.0,
        "iou_medio": 1.0,
    }


def test_main_sin_umbral_guarda_el_reporte_con_el_umbral_pendiente(tmp_path: Path) -> None:
    reporte = tmp_path / "acuerdo.json"

    main([*_rutas(tmp_path), "--reporte", str(reporte)])

    contenido = json.loads(reporte.read_text(encoding="utf-8"))
    assert (contenido["umbral"], contenido["clases_a_redefinir"]) == (None, None)


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "tools.acuerdo_etiquetado", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "--umbral" in resultado.stdout
