"""Línea de comandos del benchmark de motores (SPEC/9 §1.5): video, etiquetas y variantes."""

import json
import subprocess
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.inference.adapters.onnx_detector import DetectorOnnx
from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.types import Caja, ClaseObjeto, Deteccion
from tests.utilidades_scripts import RAIZ
from tools import bench_detectores
from tools.bench_detectores import crear_variante, leer_frames_etiquetados, main

LADO = 32
PERSONA = [4, 4, 20, 28]
PERSONA_FIJA = Caja(4, 4, 20, 28)
FRAME = np.zeros((4, 4, 3), dtype=np.uint8)


class DetectorFijo:
    def __init__(self, detecciones: list[Deteccion]) -> None:
        self._detecciones = detecciones

    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        return self._detecciones


def _video(carpeta: Path, cuadros: int = 3) -> Path:
    ruta = carpeta / "clip.avi"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), 5, (LADO, LADO))
    for valor in range(cuadros):
        escritor.write(np.full((LADO, LADO, 3), valor * 40, dtype=np.uint8))
    escritor.release()
    return ruta


def _etiquetas(carpeta: Path) -> Path:
    ruta = carpeta / "etiquetas.json"
    ruta.write_text(json.dumps({"frames": {"0": [PERSONA], "2": [PERSONA]}}), encoding="utf-8")
    return ruta


def test_leer_frames_etiquetados_devuelve_solo_los_frames_con_etiqueta(tmp_path: Path) -> None:
    frames = leer_frames_etiquetados(_video(tmp_path), _etiquetas(tmp_path))

    assert [int(frame[0, 0, 0]) for frame, _ in frames] == [0, 80]
    assert [cajas for _, cajas in frames] == [[Caja(4, 4, 20, 28)], [Caja(4, 4, 20, 28)]]


def test_leer_frames_etiquetados_falla_si_el_video_tiene_menos_frames(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no tiene el frame 2"):
        leer_frames_etiquetados(_video(tmp_path, cuadros=2), _etiquetas(tmp_path))


def test_crear_variante_ultralytics_usa_la_raiz_de_composicion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=lambda _r: None))

    detector = crear_variante("ultralytics", "yolov8n.pt", 0.5, manifiesto={})

    assert isinstance(detector, DetectorUltralytics)


def test_crear_variante_onnx_toma_normalizacion_y_clases_del_manifiesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sesion = types.SimpleNamespace(
        get_inputs=lambda: [types.SimpleNamespace(name="x", shape=(1, 3, 4, 4))]
    )
    monkeypatch.setattr(bench_detectores, "crear_sesion", lambda ruta: sesion)
    manifiesto = {
        "modelos": [
            {
                "archivo": "m.onnx",
                "clases": {"1": "persona"},
                "media": [0.5] * 3,
                "desviacion": [0.25] * 3,
            }
        ]
    }

    detector = crear_variante("onnx", "m.onnx", 0.5, manifiesto=manifiesto)

    assert isinstance(detector, DetectorOnnx)


def test_crear_variante_onnx_sin_declarar_en_el_manifiesto_falla() -> None:
    with pytest.raises(ValueError, match="m.onnx no está declarado en models/manifest.json"):
        crear_variante("onnx", "m.onnx", 0.5, manifiesto={"modelos": []})


def test_crear_variante_con_motor_desconocido_falla() -> None:
    with pytest.raises(ValueError, match="Motor desconocido: tensorflow"):
        crear_variante("tensorflow", "m.pb", 0.5, manifiesto={})


def test_main_mide_cada_variante_contra_el_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    acierto = [Deteccion(ClaseObjeto.PERSONA, 0.9, Caja(4, 4, 20, 28))]
    variantes = {"base.pt": DetectorFijo(acierto), "nuevo.onnx": DetectorFijo([])}
    monkeypatch.setattr(
        bench_detectores, "crear_variante", lambda _motor, ruta, _c, manifiesto: variantes[ruta]
    )

    codigo = main(
        ["--video", str(_video(tmp_path)), "--etiquetas", str(_etiquetas(tmp_path)),
         "--hardware", "CI", "--confianza-minima", "0.5",
         "--variante", "base", "ultralytics", "base.pt", "estado actual",
         "--variante", "nuevo", "onnx", "nuevo.onnx", "más liviano"]
    )  # fmt: skip

    salida = capsys.readouterr().out.splitlines()
    assert codigo == 0
    assert salida[0].startswith("base | estado actual | CI | ")
    assert salida[0].endswith("| 1.000 | ref | precisión 1.000")
    assert salida[1].startswith("nuevo | más liviano | CI | ")
    assert "| 0.000 | no (fps: umbral sin definir (decisión D2);" in salida[1]
    assert "recall de persona 0.000 < baseline 1.000)" in salida[1]


TRES_MIB = 3 * 1024 * 1024
TRES = 3.0
OBLIGATORIOS = ["--video", "v.avi", "--etiquetas", "e.json", "--hardware", "CI",
                "--confianza-minima", "0.5", "--variante", "a", "onnx", "a.onnx", "h"]  # fmt: skip


def test_memoria_se_informa_en_mib(monkeypatch: pytest.MonkeyPatch) -> None:
    proceso = types.SimpleNamespace(memory_info=lambda: types.SimpleNamespace(rss=TRES_MIB))
    monkeypatch.setattr(bench_detectores.psutil, "Process", lambda: proceso)

    assert bench_detectores._memoria_mb() == TRES  # - función privada sin entrada


@pytest.mark.parametrize(
    ("motor", "manifiesto", "mensaje"),
    [("tensorflow", {}, "Motor desconocido: tensorflow (usa ultralytics u onnx)."),
     ("onnx", {"modelos": []},
      "m.onnx no está declarado en models/manifest.json (clases y normalización).")],
)  # fmt: skip
def test_crear_variante_explica_el_error(motor: str, manifiesto: dict, mensaje: str) -> None:
    with pytest.raises(ValueError) as error:
        crear_variante(motor, "m.onnx", 0.5, manifiesto=manifiesto)

    assert str(error.value) == mensaje


@pytest.mark.parametrize(
    ("opcion", "cantidad"),
    [("--video", 2), ("--etiquetas", 2), ("--hardware", 2), ("--confianza-minima", 2),
     ("--variante", 5)],
)  # fmt: skip
def test_main_exige_cada_argumento_obligatorio(opcion: str, cantidad: int) -> None:
    posicion = OBLIGATORIOS.index(opcion)

    with pytest.raises(SystemExit):
        main(OBLIGATORIOS[:posicion] + OBLIGATORIOS[posicion + cantidad :])


@pytest.fixture
def manifiestos_recibidos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[dict]:
    """Corre main desde tmp_path con dobles y devuelve el manifiesto que recibió cada variante."""
    vistos: list[dict] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        bench_detectores, "leer_frames_etiquetados", lambda *_a: [(FRAME, [PERSONA_FIJA])]
    )
    monkeypatch.setattr(
        bench_detectores,
        "crear_variante",
        lambda *a: vistos.append(a[3]) or DetectorFijo([]),
    )
    return vistos


def test_main_lee_el_manifiesto_por_omision_del_directorio_actual(
    tmp_path: Path, manifiestos_recibidos: list[dict]
) -> None:
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "manifest.json").write_text('{"modelos": [{"x": 1}]}', encoding="utf-8")

    main(OBLIGATORIOS)

    assert manifiestos_recibidos == [{"modelos": [{"x": 1}]}]


def test_main_sin_manifiesto_usa_una_lista_vacia(manifiestos_recibidos: list[dict]) -> None:
    main(OBLIGATORIOS)

    assert manifiestos_recibidos == [{"modelos": []}]


@pytest.mark.integration
def test_modulo_muestra_la_ayuda_con_las_columnas_de_cada_variante() -> None:
    # S603: el intérprete de la suite con argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "tools.bench_detectores", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert "--variante NOMBRE MOTOR RUTA HIPOTESIS" in resultado.stdout
    assert "la primera es el baseline" in resultado.stdout
    assert '{"frames": {"<índice del frame>": [[x1, y1, x2, y2], ...]}}' in resultado.stdout
