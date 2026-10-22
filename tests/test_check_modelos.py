"""Manifiesto de modelos (SPEC/9 §0.5, AC-002): todo modelo distribuido está declarado."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.check_licenses import (
    Veredicto,
    clasificar_licencia_de_dataset,
    evaluar_manifiesto,
    main,
)
from tests.utilidades_scripts import ejecutar_script

CONTENIDO_MODELO = b"pesos-de-prueba"
SHA_MODELO = hashlib.sha256(CONTENIDO_MODELO).hexdigest()


def _entrada(archivo: str, sha256: str = SHA_MODELO, licencia: str = "Apache-2.0") -> dict:
    return {
        "nombre": "detector",
        "version": "1.0.0",
        "archivo": archivo,
        "sha256": sha256,
        "licencia_pesos": licencia,
        "licencia_codigo_entrenamiento": "Apache-2.0",
        "datasets": [{"nombre": "propio", "licencia": "CC-BY-4.0"}],
        "clases": {"0": "persona"},
        "tamano_entrada": [640, 640],
    }


@pytest.mark.parametrize(
    ("licencia", "esperado"),
    [
        ("CC-BY-4.0", Veredicto.PERMITIDA),
        ("CC BY 4.0", Veredicto.PERMITIDA),
        ("CC0-1.0", Veredicto.PERMITIDA),
        ("CC-BY-SA-4.0", Veredicto.REVISION),
        ("CC-BY-NC-SA-4.0", Veredicto.PROHIBIDA),
    ],
)
def test_clasificar_licencia_de_dataset_solo_atribucion_es_permitida(
    licencia: str, esperado: Veredicto
) -> None:
    assert clasificar_licencia_de_dataset(licencia) is esperado


def _crear_modelo(raiz: Path, relativa: str) -> None:
    ruta = raiz / relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(CONTENIDO_MODELO)


def test_evaluar_manifiesto_modelo_declarado_y_permisivo_no_reporta_errores(
    tmp_path: Path,
) -> None:
    _crear_modelo(tmp_path, "models/detector.onnx")

    errores = evaluar_manifiesto(tmp_path, {"modelos": [_entrada("models/detector.onnx")]})

    assert errores == []


def test_evaluar_manifiesto_modelo_sin_declarar_falla(tmp_path: Path) -> None:
    _crear_modelo(tmp_path, "models/sub/intruso.pt")

    errores = evaluar_manifiesto(tmp_path, {"modelos": []})

    assert errores == [
        "models/sub/intruso.pt no está en models/manifest.json: decláralo con su sha256, "
        "licencias y datasets, o bórralo."
    ]


def test_evaluar_manifiesto_modelo_sin_declarar_en_la_raiz_falla(tmp_path: Path) -> None:
    _crear_modelo(tmp_path, "intruso.onnx")

    errores = evaluar_manifiesto(tmp_path, {"modelos": []})

    assert errores == [
        "intruso.onnx no está en models/manifest.json: decláralo con su sha256, licencias y "
        "datasets, o bórralo."
    ]


def test_evaluar_manifiesto_hash_distinto_falla(tmp_path: Path) -> None:
    _crear_modelo(tmp_path, "models/detector.onnx")

    errores = evaluar_manifiesto(
        tmp_path, {"modelos": [_entrada("models/detector.onnx", sha256="0" * 64)]}
    )

    assert errores == [
        f"models/detector.onnx: sha256 {SHA_MODELO} no coincide con el manifiesto "
        f"({'0' * 64}). El archivo cambió o el manifiesto está desactualizado."
    ]


@pytest.mark.parametrize("campo", ["licencia_pesos", "licencia_codigo_entrenamiento"])
def test_evaluar_manifiesto_licencia_prohibida_falla(tmp_path: Path, campo: str) -> None:
    _crear_modelo(tmp_path, "yolov8n.pt")
    entrada = {**_entrada("yolov8n.pt"), campo: "AGPL-3.0"}

    errores = evaluar_manifiesto(tmp_path, {"modelos": [entrada]})

    assert errores == [f"yolov8n.pt: {campo} prohibida o sin revisar (AGPL-3.0)."]


def test_evaluar_manifiesto_dataset_no_comercial_falla(tmp_path: Path) -> None:
    _crear_modelo(tmp_path, "models/epp.onnx")
    entrada = {
        **_entrada("models/epp.onnx"),
        "datasets": [{"nombre": "SH17", "licencia": "CC-BY-NC-SA-4.0"}],
    }

    errores = evaluar_manifiesto(tmp_path, {"modelos": [entrada]})

    assert errores == ["models/epp.onnx: dataset SH17 prohibida o sin revisar (CC-BY-NC-SA-4.0)."]


def test_evaluar_manifiesto_entrada_sin_archivo_en_disco_falla(tmp_path: Path) -> None:
    errores = evaluar_manifiesto(tmp_path, {"modelos": [_entrada("models/fantasma.onnx")]})

    assert errores == ["models/fantasma.onnx figura en el manifiesto pero no existe en disco."]


def _argumentos(raiz: Path, modelos: list[dict]) -> list[str]:
    sin_paquetes = raiz / "paquetes.json"
    sin_paquetes.write_text("[]", encoding="utf-8")
    manifiesto = raiz / "manifest.json"
    manifiesto.write_text(json.dumps({"modelos": modelos}), encoding="utf-8")
    return ["--paquetes", str(sin_paquetes), "--raiz", str(raiz), "--manifiesto", str(manifiesto)]


def test_main_con_modelo_sin_declarar_devuelve_uno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _crear_modelo(tmp_path, "models/detector.onnx")

    codigo = main(_argumentos(tmp_path, []))

    assert codigo == 1
    assert capsys.readouterr().out.startswith("models/detector.onnx no está en")


def test_main_con_manifiesto_completo_devuelve_cero(tmp_path: Path) -> None:
    _crear_modelo(tmp_path, "models/detector.onnx")

    assert main(_argumentos(tmp_path, [_entrada("models/detector.onnx")])) == 0


@pytest.mark.integration
def test_script_ejecutado_como_programa_falla_con_el_manifiesto_actual_por_la_agpl(
    tmp_path: Path,
) -> None:
    sin_paquetes = tmp_path / "paquetes.json"
    sin_paquetes.write_text("[]", encoding="utf-8")

    resultado = ejecutar_script("check_licenses.py", "--paquetes", str(sin_paquetes))

    assert resultado.returncode == 1
    assert "yolov8n.pt: licencia_pesos prohibida o sin revisar (AGPL-3.0)." in resultado.stdout
