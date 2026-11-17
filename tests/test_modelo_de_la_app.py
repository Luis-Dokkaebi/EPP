"""Qué modelo usa la app: el instalado y firmado para el cliente o el del ejecutable (T-07)."""

import json
from pathlib import Path
from typing import Any

import pytest
from Crypto.PublicKey import RSA

from config import config
from src.models import modelo_de_la_app as modulo
from src.models.manifiesto_aprobado import MODELOS_APROBADOS
from src.models.manifiesto_firmado import ManifiestoFirmadoInvalidoError
from src.models.modelo_de_la_app import modelo_de_la_app, resolver_modelo
from src.security import drm
from tests.licencias_firmadas import firmar, generar_llave, publica_de

SHA = "ab" * 32
ENTRADA: dict[str, Any] = {
    "nombre": "epp-acme",
    "version": "0.1-acme",
    "archivo": "epp_acme.onnx",
    "sha256": SHA,
    "motor": "onnx",
    "clases": {"0": "persona", "1": "cabeza", "2": "casco", "3": "chaleco"},
    "media": [0.485, 0.456, 0.406],
    "desviacion": [0.229, 0.224, 0.225],
}
MANIFIESTO = {"version_esquema": 1, "cliente": "acme-planta1", "modelos": [ENTRADA]}
MANIFIESTO_DEL_EJECUTABLE = {"modelos": [{"archivo": "yolov8n.pt"}]}


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def ejecutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """El modelo y el manifiesto que viajan dentro del ejecutable."""
    manifiesto = tmp_path / "manifest.json"
    manifiesto.write_text(json.dumps(MANIFIESTO_DEL_EJECUTABLE), encoding="utf-8")
    monkeypatch.setattr(config, "MODEL_PATH", "app/yolov8n.pt")
    monkeypatch.setattr(config, "DETECTION_ENGINE", "ultralytics")
    monkeypatch.setattr(config, "MANIFEST_PATH", str(manifiesto))
    return manifiesto


def _instalar(carpeta: Path, llave: RSA.RsaKey) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "modelo.manifest").write_text(firmar(llave, MANIFIESTO), encoding="utf-8")
    return carpeta


def test_sin_modelo_instalado_rige_el_del_ejecutable(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    modelo = resolver_modelo(tmp_path / "modelo", publica_de(llave))

    assert (modelo.ruta, modelo.motor) == ("app/yolov8n.pt", "ultralytics")
    assert modelo.aprobados is MODELOS_APROBADOS
    assert modelo.leer_manifiesto() == MANIFIESTO_DEL_EJECUTABLE


def test_el_manifiesto_del_ejecutable_no_se_lee_hasta_que_hace_falta(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    ejecutable.unlink()

    modelo = resolver_modelo(tmp_path / "modelo", publica_de(llave))

    assert modelo.ruta == "app/yolov8n.pt"
    with pytest.raises(FileNotFoundError):
        modelo.leer_manifiesto()


def test_un_modelo_instalado_y_firmado_reemplaza_al_del_ejecutable(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    carpeta = _instalar(tmp_path / "modelo", llave)

    modelo = resolver_modelo(carpeta, publica_de(llave))

    assert (modelo.ruta, modelo.motor) == (str(carpeta / "epp_acme.onnx"), "onnx")
    assert modelo.aprobados == {"epp_acme.onnx": SHA}
    assert modelo.leer_manifiesto() == MANIFIESTO


def test_un_manifiesto_instalado_con_otra_firma_no_cae_al_modelo_del_ejecutable(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    carpeta = _instalar(tmp_path / "modelo", generar_llave())

    with pytest.raises(ManifiestoFirmadoInvalidoError, match="la firma no es del proveedor"):
        resolver_modelo(carpeta, publica_de(llave))


def test_la_app_busca_el_modelo_instalado_en_su_carpeta_de_datos(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(modulo, "LLAVE_PUBLICA", publica_de(llave))
    carpeta = _instalar(tmp_path / "OficinaEficiencia" / "modelo", llave)

    assert modelo_de_la_app().ruta == str(carpeta / "epp_acme.onnx")


def test_la_app_verifica_el_manifiesto_con_la_llave_publica_del_proveedor(
    ejecutable: Path, llave: RSA.RsaKey, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _instalar(tmp_path / "OficinaEficiencia" / "modelo", llave)

    assert modulo.LLAVE_PUBLICA == drm.LLAVE_PUBLICA_DEL_PROVEEDOR == drm._PUBLIC_KEY_PEM
    with pytest.raises(ManifiestoFirmadoInvalidoError):
        modelo_de_la_app()


def test_sin_modelo_instalado_la_app_usa_el_del_ejecutable(ejecutable: Path) -> None:
    assert modelo_de_la_app().ruta == "app/yolov8n.pt"
