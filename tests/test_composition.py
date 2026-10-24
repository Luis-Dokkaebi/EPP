"""Raíz de composición única (SPEC/9 §1.3.6): GUI y headless crean el detector del mismo modo."""

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from config import config as configuracion
from src import composition as composicion
from src.composition import (
    MOTOR_ONNX,
    MOTOR_ULTRALYTICS,
    ModeloNoDeclaradoError,
    MotorDesconocidoError,
    clases_declaradas,
    crear_detector,
    crear_detector_configurado,
)
from src.inference.adapters.onnx_detector import DetectorOnnx
from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.types import Caja, ClaseObjeto, Deteccion
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

ID_PERSONA = 0


@pytest.fixture
def modelos_cargados(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModeloFalso]:
    """Reemplaza el paquete `ultralytics`: la prueba no carga pesos reales (CLAUDE.md §16)."""
    cargados: dict[str, ModeloFalso] = {}

    def yolo(ruta: str) -> ModeloFalso:
        cargados[ruta] = ModeloFalso([DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0), 0.5)])
        return cargados[ruta]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=yolo))
    return cargados


def test_crear_detector_carga_el_modelo_de_la_ruta_indicada(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    crear_detector("modelos/personas.pt", confianza_minima=0.0)

    assert list(modelos_cargados) == ["modelos/personas.pt"]


def test_crear_detector_devuelve_un_puerto_con_clases_semanticas(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.0)

    detecciones = detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8))

    assert detecciones == [Deteccion(ClaseObjeto.PERSONA, 0.5, Caja(1.0, 2.0, 3.0, 4.0))]


def test_crear_detector_aplica_la_confianza_minima(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.6)

    assert detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8)) == []


def _manifiesto_onnx(ruta: str) -> dict[str, list[dict[str, object]]]:
    return {
        "modelos": [
            {
                "archivo": ruta,
                "clases": {"1": "persona"},
                "media": [0.5] * 3,
                "desviacion": [0.25] * 3,
            }
        ]
    }


def test_crear_detector_con_motor_ultralytics_es_el_adaptador_de_ultralytics(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", 0.0, motor=MOTOR_ULTRALYTICS, manifiesto={})

    assert isinstance(detector, DetectorUltralytics)


def test_crear_detector_con_motor_onnx_usa_clases_y_normalizacion_del_manifiesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrada = types.SimpleNamespace(name="x", shape=(1, 3, 4, 4))
    monkeypatch.setattr(
        composicion,
        "crear_sesion",
        lambda _ruta: types.SimpleNamespace(get_inputs=lambda: [entrada]),
    )

    detector = crear_detector(
        "m.onnx", 0.5, motor=MOTOR_ONNX, manifiesto=_manifiesto_onnx("m.onnx")
    )

    assert isinstance(detector, DetectorOnnx)


@pytest.mark.parametrize(
    ("motor", "manifiesto", "error", "mensaje"),
    [("tensorflow", {}, MotorDesconocidoError,
      "Motor desconocido: tensorflow (usa ultralytics u onnx)."),
     (MOTOR_ONNX, {"modelos": []}, ModeloNoDeclaradoError,
      "m.onnx no está declarado en models/manifest.json (clases y normalización).")],
    ids=["motor-desconocido", "onnx-sin-declarar"],
)  # fmt: skip
def test_crear_detector_falla_ruidosamente_con_un_error_tipado(
    motor: str, manifiesto: dict, error: type[Exception], mensaje: str
) -> None:
    with pytest.raises(error) as excepcion:
        crear_detector("m.onnx", 0.5, motor=motor, manifiesto=manifiesto)

    assert str(excepcion.value) == mensaje


def test_los_nombres_de_motor_son_los_que_admite_la_configuracion() -> None:
    """config.DETECTION_ENGINE usa estos textos literales: cambiarlos rompe la configuración."""
    assert (MOTOR_ULTRALYTICS, MOTOR_ONNX) == ("ultralytics", "onnx")


class TorchFalso(types.SimpleNamespace):
    """Doble de `torch`: registra los `weights_only` con los que se llamó a `torch.load`."""

    def __init__(self) -> None:
        self.recibidos: list[object] = []
        super().__init__(load=self.load_original)

    def load_original(self, *_argumentos: object, **opciones: object) -> str:
        self.recibidos.append(opciones.get("weights_only"))
        return "pesos"


@pytest.fixture
def torch_falso(monkeypatch: pytest.MonkeyPatch) -> TorchFalso:
    torch = TorchFalso()
    monkeypatch.setitem(sys.modules, "torch", torch)
    return torch


def _yolo_que(accion: object) -> types.SimpleNamespace:
    return types.SimpleNamespace(YOLO=accion)


def test_motor_ultralytics_carga_los_pesos_heredados_sin_weights_only(
    monkeypatch: pytest.MonkeyPatch, torch_falso: TorchFalso
) -> None:
    """CR-05: ultralytics 8.1 necesita pickle completo; se retira con el motor (A-16, D8)."""

    def yolo(ruta: str) -> ModeloFalso:
        sys.modules["torch"].load(ruta)
        return ModeloFalso([])

    monkeypatch.setitem(sys.modules, "ultralytics", _yolo_que(yolo))

    crear_detector("m.pt", 0.0)

    assert torch_falso.recibidos == [False]


def test_motor_ultralytics_restaura_torch_load_aunque_la_carga_falle(
    monkeypatch: pytest.MonkeyPatch, torch_falso: TorchFalso
) -> None:
    def yolo_roto(_ruta: str) -> None:
        raise RuntimeError("pesos corruptos")

    monkeypatch.setitem(sys.modules, "ultralytics", _yolo_que(yolo_roto))

    with pytest.raises(RuntimeError, match="pesos corruptos"):
        crear_detector("m.pt", 0.0)

    assert torch_falso.load == torch_falso.load_original


def test_motor_onnx_reconoce_el_modelo_por_su_ruta_relativa_del_manifiesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrada = types.SimpleNamespace(name="x", shape=(1, 3, 4, 4))
    monkeypatch.setattr(
        composicion, "crear_sesion", lambda _r: types.SimpleNamespace(get_inputs=lambda: [entrada])
    )
    manifiesto = _manifiesto_onnx("models/m.onnx")

    detector = crear_detector(
        "/opt/app/models/m.onnx", 0.5, motor=MOTOR_ONNX, manifiesto=manifiesto
    )

    assert isinstance(detector, DetectorOnnx)


@pytest.mark.parametrize("ruta", ["/opt/app/otros/m.onnx", "/opt/app/xmodels/m.onnx", "m.onnx"])
def test_motor_onnx_no_confunde_carpetas_con_el_mismo_nombre_de_archivo(ruta: str) -> None:
    with pytest.raises(ModeloNoDeclaradoError):
        crear_detector(ruta, 0.5, motor=MOTOR_ONNX, manifiesto=_manifiesto_onnx("models/m.onnx"))


def test_el_motor_configurado_sigue_siendo_ultralytics_hasta_que_onnx_pase_la_puerta() -> None:
    """El cambio a ONNX espera la puerta de A-13 (umbrales de D2) y un modelo aprobado."""
    assert configuracion.DETECTION_ENGINE == MOTOR_ULTRALYTICS


def test_detector_configurado_ultralytics_no_lee_el_manifiesto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, modelos_cargados: dict[str, ModeloFalso]
) -> None:
    monkeypatch.setattr(configuracion, "MODEL_PATH", "pesos/app.pt")
    monkeypatch.setattr(configuracion, "MANIFEST_PATH", str(tmp_path / "no-existe.json"))

    detector = crear_detector_configurado(0.0)

    assert isinstance(detector, DetectorUltralytics)
    assert list(modelos_cargados) == ["pesos/app.pt"]


def test_detector_configurado_onnx_usa_el_manifiesto_de_la_configuracion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifiesto = tmp_path / "manifest.json"
    manifiesto.write_text(json.dumps(_manifiesto_onnx("models/app.onnx")), encoding="utf-8")
    entrada = types.SimpleNamespace(name="x", shape=(1, 3, 4, 4))
    rutas: list[str] = []
    monkeypatch.setattr(
        composicion,
        "crear_sesion",
        lambda ruta: rutas.append(ruta) or types.SimpleNamespace(get_inputs=lambda: [entrada]),
    )
    monkeypatch.setattr(configuracion, "DETECTION_ENGINE", MOTOR_ONNX)
    monkeypatch.setattr(configuracion, "MODEL_PATH", "/app/models/app.onnx")
    monkeypatch.setattr(configuracion, "MANIFEST_PATH", str(manifiesto))

    detector = crear_detector_configurado(0.5)

    assert isinstance(detector, DetectorOnnx)
    assert rutas == ["/app/models/app.onnx"]


def test_las_clases_declaradas_salen_de_la_entrada_del_manifiesto() -> None:
    entrada = {"archivo": "m.onnx", "clases": {"0": "persona", "5": "casco"}}

    assert clases_declaradas(entrada) == frozenset({ClaseObjeto.PERSONA, ClaseObjeto.CASCO})
