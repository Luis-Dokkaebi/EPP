"""Raíz de composición única (SPEC/9 §1.3.6): GUI y headless crean el detector del mismo modo."""

import json
from pathlib import Path

import numpy as np
import pytest

from config import config as configuracion
from src import composition as composicion
from src.composition import (
    ModeloNoDeclaradoError,
    clases_declaradas,
    crear_detector,
    crear_detector_configurado,
)
from src.inference.adapters.onnx_detector import DetectorOnnx
from src.inference.types import Caja, ClaseObjeto
from tests.dobles_onnx import ID_PERSONA, DeteccionCruda, SesionOnnxFalsa

LADO = 256


def _manifiesto_onnx(ruta: str) -> dict[str, list[dict[str, object]]]:
    return {
        "modelos": [
            {
                "archivo": ruta,
                "clases": {str(ID_PERSONA): "persona"},
                "media": [0.5] * 3,
                "desviacion": [0.25] * 3,
            }
        ]
    }


@pytest.fixture
def sesiones(monkeypatch: pytest.MonkeyPatch) -> dict[str, SesionOnnxFalsa]:
    """Reemplaza onnxruntime: la prueba no carga pesos reales (CLAUDE.md §16)."""
    creadas: dict[str, SesionOnnxFalsa] = {}

    def crear(ruta: str) -> SesionOnnxFalsa:
        persona = DeteccionCruda(ID_PERSONA, (16.0, 32.0, 48.0, 64.0), 0.5)
        creadas[ruta] = SesionOnnxFalsa([persona], LADO, LADO)
        return creadas[ruta]

    monkeypatch.setattr(composicion, "crear_sesion", crear)
    return creadas


def test_crear_detector_carga_el_modelo_de_la_ruta_indicada(sesiones) -> None:
    crear_detector("/app/models/m.onnx", 0.0, _manifiesto_onnx("models/m.onnx"))

    assert list(sesiones) == ["/app/models/m.onnx"]


def test_crear_detector_devuelve_un_puerto_con_clases_semanticas(sesiones) -> None:
    detector = crear_detector("m.onnx", 0.0, _manifiesto_onnx("m.onnx"))

    detecciones = detector.detectar(np.zeros((LADO, LADO, 3), dtype=np.uint8))

    [deteccion] = detecciones
    assert isinstance(detector, DetectorOnnx)
    assert (deteccion.clase, deteccion.caja) == (ClaseObjeto.PERSONA, Caja(16.0, 32.0, 48.0, 64.0))
    assert deteccion.confianza == pytest.approx(0.5)


def test_crear_detector_aplica_la_confianza_minima(sesiones) -> None:
    detector = crear_detector("m.onnx", 0.6, _manifiesto_onnx("m.onnx"))

    assert detector.detectar(np.zeros((LADO, LADO, 3), dtype=np.uint8)) == []


def test_crear_detector_sin_el_modelo_en_el_manifiesto_falla_con_error_tipado() -> None:
    with pytest.raises(ModeloNoDeclaradoError) as excepcion:
        crear_detector("m.onnx", 0.5, {"modelos": []})

    assert str(excepcion.value) == (
        "m.onnx no está declarado en models/manifest.json (clases y normalización)."
    )


@pytest.mark.parametrize("ruta", ["/opt/app/otros/m.onnx", "/opt/app/xmodels/m.onnx", "m.onnx"])
def test_crear_detector_no_confunde_carpetas_con_el_mismo_nombre_de_archivo(ruta: str) -> None:
    with pytest.raises(ModeloNoDeclaradoError):
        crear_detector(ruta, 0.5, _manifiesto_onnx("models/m.onnx"))


def test_la_app_detecta_con_rf_detr_nano_en_onnx() -> None:
    """ADR-001: RF-DETR Nano (Apache-2.0) con ONNX Runtime; sin Ultralytics (AGPL)."""
    assert Path(configuracion.MODEL_PATH).parts[-3:] == (
        "models",
        "rfdetr",
        "rfdetr-nano-coco-int8.onnx",
    )


def test_el_modelo_configurado_declara_persona_y_celular_con_ids_de_coco() -> None:
    manifiesto = composicion.leer_manifiesto(configuracion.MANIFEST_PATH)

    entrada = composicion.entrada_del_modelo(configuracion.MODEL_PATH, manifiesto)

    assert entrada["clases"] == {"1": "persona", "77": "celular"}
    assert entrada["licencia_pesos"] == "Apache-2.0"


def test_detector_configurado_usa_el_modelo_y_el_manifiesto_de_la_configuracion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sesiones
) -> None:
    manifiesto = tmp_path / "manifest.json"
    manifiesto.write_text(json.dumps(_manifiesto_onnx("models/app.onnx")), encoding="utf-8")
    monkeypatch.setattr(configuracion, "MODEL_PATH", "/app/models/app.onnx")
    monkeypatch.setattr(configuracion, "MANIFEST_PATH", str(manifiesto))

    detector = crear_detector_configurado(0.5)

    assert isinstance(detector, DetectorOnnx)
    assert list(sesiones) == ["/app/models/app.onnx"]


def test_las_clases_declaradas_salen_de_la_entrada_del_manifiesto() -> None:
    entrada = {"archivo": "m.onnx", "clases": {"0": "persona", "5": "casco"}}

    assert clases_declaradas(entrada) == frozenset({ClaseObjeto.PERSONA, ClaseObjeto.CASCO})
