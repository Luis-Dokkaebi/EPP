"""Verificación de modelos contra el manifiesto aprobado (SPEC/9 §1.8, AC-002).

Falla cerrada: modelo no listado, hash distinto o tabla vacía impiden arrancar el tracking.
"""

import hashlib
import json
import logging
from pathlib import Path

import pytest

from scripts.generar_manifiesto_embebido import generar_modulo
from src.models import model_verifier
from src.models.manifiesto_aprobado import MODELOS_APROBADOS
from src.models.model_verifier import (
    ModelIntegrityError,
    assert_model_integrity,
    compute_model_hash,
    verify_model,
)
from tests.utilidades_scripts import RAIZ

CONTENIDO = b"pesos de prueba"
UN_MIB = 1 << 20


def _modelo(carpeta: Path, relativo: str, contenido: bytes = CONTENIDO) -> Path:
    ruta = carpeta / relativo
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def _aprobados(**archivos: bytes) -> dict[str, str]:
    return {
        nombre.replace("__", "/"): hashlib.sha256(contenido).hexdigest()
        for nombre, contenido in archivos.items()
    }


def test_verify_model_acepta_un_modelo_declarado_con_su_hash(tmp_path: Path) -> None:
    ruta = _modelo(tmp_path, "modelo.onnx")

    assert verify_model(str(ruta), _aprobados(**{"modelo.onnx": CONTENIDO})) is True


def test_verify_model_rechaza_un_hash_distinto_y_lo_registra(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ruta = _modelo(tmp_path, "modelo.onnx", b"modelo con puerta trasera")
    aprobados = _aprobados(**{"modelo.onnx": CONTENIDO})

    assert verify_model(str(ruta), aprobados) is False
    actual = hashlib.sha256(b"modelo con puerta trasera").hexdigest()
    assert caplog.messages == [
        "[ModelVerifier] Integridad del modelo COMPROMETIDA. "
        f"esperado={aprobados['modelo.onnx'][:12]}... actual={actual[:12]}..."
    ]


def test_verify_model_rechaza_un_modelo_no_listado_y_lo_registra(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ruta = _modelo(tmp_path, "otro.onnx")

    assert verify_model(str(ruta), _aprobados(**{"modelo.onnx": CONTENIDO})) is False
    assert caplog.messages == [
        f"[ModelVerifier] Modelo no declarado en models/manifest.json: {ruta}"
    ]


def test_verify_model_con_tabla_vacia_falla_cerrado(tmp_path: Path) -> None:
    assert verify_model(str(_modelo(tmp_path, "modelo.onnx")), {}) is False


def test_verify_model_elige_la_entrada_mas_especifica_por_ruta(tmp_path: Path) -> None:
    ruta = _modelo(tmp_path, "models/yolov8/yolov8n.pt", b"copia")
    aprobados = _aprobados(**{"yolov8n.pt": b"original", "models__yolov8__yolov8n.pt": b"copia"})

    assert verify_model(str(ruta), aprobados) is True


def test_verify_model_no_confunde_un_nombre_con_otro_que_lo_contiene(tmp_path: Path) -> None:
    ruta = _modelo(tmp_path, "xyolov8n.pt")

    assert verify_model(str(ruta), _aprobados(**{"yolov8n.pt": CONTENIDO})) is False


def test_verify_model_sin_archivo_lanza_file_not_found(tmp_path: Path) -> None:
    ruta = tmp_path / "modelo.onnx"

    with pytest.raises(FileNotFoundError) as error:
        verify_model(str(ruta), _aprobados(**{"modelo.onnx": CONTENIDO}))

    assert str(error.value) == f"Modelo AI no encontrado para verificacion: {ruta}"


class _ArchivoQueRegistraLecturas:
    def __init__(self, contenido: bytes) -> None:
        self._contenido = contenido
        self.tamanos: list[int | None] = []

    def __enter__(self) -> "_ArchivoQueRegistraLecturas":
        return self

    def __exit__(self, *_excepcion: object) -> None:
        return None

    def read(self, tamano: int | None = None) -> bytes:
        self.tamanos.append(tamano)
        parte, self._contenido = self._contenido[:UN_MIB], self._contenido[UN_MIB:]
        return parte


def test_compute_model_hash_lee_por_bloques_de_un_mib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _modelo(tmp_path, "modelo.onnx")
    archivo = _ArchivoQueRegistraLecturas(b"x" * (UN_MIB + 1))
    monkeypatch.setattr(model_verifier, "open", lambda *_args: archivo, raising=False)

    huella = compute_model_hash(str(ruta))

    assert archivo.tamanos == [UN_MIB, UN_MIB, UN_MIB]
    assert huella == hashlib.sha256(b"x" * (UN_MIB + 1)).hexdigest()


def test_assert_model_integrity_lanza_error_si_no_esta_aprobado(tmp_path: Path) -> None:
    ruta = _modelo(tmp_path, "modelo.onnx", b"otro contenido")

    with pytest.raises(ModelIntegrityError) as error:
        assert_model_integrity(str(ruta), _aprobados(**{"modelo.onnx": CONTENIDO}))

    assert str(error.value) == (
        "El modelo AI ha sido manipulado o reemplazado. "
        "Inferencia abortada por seguridad (TASK-5.2)."
    )


def test_assert_model_integrity_no_lanza_si_esta_aprobado(tmp_path: Path) -> None:
    ruta = _modelo(tmp_path, "modelo.onnx")

    assert_model_integrity(str(ruta), _aprobados(**{"modelo.onnx": CONTENIDO}))


def test_verify_model_sin_tabla_usa_los_modelos_aprobados_embebidos(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="src.models.model_verifier")

    assert verify_model(str(RAIZ / "yolov8n.pt")) is True
    assert caplog.messages == ["[ModelVerifier] Integridad del modelo AI verificada (SHA-256 OK)."]


def test_manifiesto_embebido_coincide_con_models_manifest_json() -> None:
    manifiesto = json.loads((RAIZ / "models" / "manifest.json").read_text(encoding="utf-8"))
    esperado = {entrada["archivo"]: entrada["sha256"] for entrada in manifiesto["modelos"]}

    assert esperado == MODELOS_APROBADOS, (
        "src/models/manifiesto_aprobado.py está desactualizado o fue manipulado: "
        "corre python scripts/generar_manifiesto_embebido.py"
    )


def test_manifiesto_embebido_es_exactamente_el_que_genera_el_script() -> None:
    manifiesto = json.loads((RAIZ / "models" / "manifest.json").read_text(encoding="utf-8"))
    actual = (RAIZ / "src" / "models" / "manifiesto_aprobado.py").read_text(encoding="utf-8")

    assert generar_modulo(manifiesto) == actual
