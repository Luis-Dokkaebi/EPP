"""DRM: huella de hardware y licencias firmadas (CLAUDE.md §7, módulo crítico).

La huella y la sal no pueden cambiar: las licencias ya emitidas llevan el hw_id calculado así.
Las licencias de estas pruebas se firman con una llave generada aquí, nunca con la privada
versionada (#17).
"""

import base64
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from src.security import drm
from src.security.drm import DRMValidator

SAL = b"0f1c1n4_3f1c13nc14_V1"
NODO_DE_RED = 42
SEPARADOR = b"||SIGNATURE||"
VENCE = 1907755200  # 15/06/2030 12:00 UTC: el mismo día en cualquier huso de ±12 h
CAMARAS_POR_OMISION = 4
LARGO_DE_LLAVE = 2048  # el mismo largo que la llave del producto
CAMARAS_DE_LA_LICENCIA = 16


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8") + SAL).hexdigest()


def _componente(**campos: Any) -> SimpleNamespace:
    return SimpleNamespace(**campos)


def _conexion(
    placas: list[SimpleNamespace],
    cpus: list[SimpleNamespace],
    discos: list[SimpleNamespace],
    bios: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Conexión WMI falsa con las cuatro consultas que usa el DRM."""
    return SimpleNamespace(
        Win32_BaseBoard=lambda: placas,
        Win32_Processor=lambda: cpus,
        Win32_DiskDrive=lambda: discos,
        Win32_ComputerSystemProduct=lambda: bios or [],
    )


def _modulo_wmi(*conexiones: SimpleNamespace | Exception) -> SimpleNamespace:
    """Módulo `wmi` falso: cada llamada a WMI() entrega la conexión siguiente o lanza su error."""
    pendientes = list(conexiones)

    def conectar() -> SimpleNamespace:
        siguiente = pendientes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    return SimpleNamespace(WMI=conectar)


@pytest.fixture
def appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path / "OficinaEficiencia"


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return RSA.generate(LARGO_DE_LLAVE)


@pytest.fixture(scope="module")
def llave_ajena() -> RSA.RsaKey:
    return RSA.generate(LARGO_DE_LLAVE)


@pytest.fixture
def validador(llave: RSA.RsaKey, appdata: Path, monkeypatch: pytest.MonkeyPatch) -> DRMValidator:
    monkeypatch.setattr(drm, "_PUBLIC_KEY_PEM", llave.public_key().export_key())
    return DRMValidator()


def _firmar(llave: RSA.RsaKey, carga: dict[str, Any]) -> str:
    texto = json.dumps(carga).encode("utf-8")
    firma = pkcs1_15.new(llave).sign(SHA256.new(texto))
    return base64.b64encode(texto + SEPARADOR + firma).decode("ascii")


def _carga(validador: DRMValidator, **extra: Any) -> dict[str, Any]:
    return {"hw_id": validador.machine_id, "exp": VENCE, **extra}


class RelojEn:
    """Reemplaza `datetime` en drm: `now()` devuelve siempre el mismo instante."""

    def __init__(self, instante: float) -> None:
        self._instante = instante

    def now(self) -> datetime:
        return datetime.fromtimestamp(self._instante)

    @staticmethod
    def fromtimestamp(instante: float) -> datetime:
        return datetime.fromtimestamp(instante)


# --- Huella de hardware ---------------------------------------------------------------------


def test_la_huella_usa_cpu_placa_y_disco_con_la_sal_v1(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conexion = _conexion(
        placas=[_componente(SerialNumber=" PLACA-1 "), _componente(SerialNumber=None)],
        cpus=[_componente(ProcessorId=" CPU-1 "), _componente(ProcessorId=None)],
        discos=[_componente(SerialNumber=" DISCO-1 "), _componente(SerialNumber=None)],
    )
    monkeypatch.setitem(sys.modules, "wmi", _modulo_wmi(conexion))

    assert DRMValidator().machine_id == _huella("B2B_CPU-1_PLACA-1_DISCO-1")


def test_los_componentes_que_wmi_no_informa_quedan_como_desconocidos(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conexion = _conexion(placas=[], cpus=[], discos=[_componente(SerialNumber="")])
    monkeypatch.setitem(sys.modules, "wmi", _modulo_wmi(conexion))

    huella = DRMValidator().machine_id

    assert huella == _huella("B2B_UNKNOWN_CPU_UNKNOWN_BOARD_UNKNOWN_DISK")


def test_sin_wmi_completo_usa_la_mac_y_el_uuid_de_la_bios(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bios = _conexion([], [], [], bios=[_componente(UUID=" BIOS-1 "), _componente(UUID=None)])
    monkeypatch.setitem(sys.modules, "wmi", _modulo_wmi(PermissionError("denegado"), bios))
    monkeypatch.setattr("uuid.getnode", lambda: NODO_DE_RED)

    assert DRMValidator().machine_id == _huella(f"B2B_FALLBACK_{NODO_DE_RED}_BIOS-1")


def test_una_bios_sin_uuid_queda_como_no_bios(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sin_uuid = _conexion([], [], [], bios=[])
    monkeypatch.setitem(sys.modules, "wmi", _modulo_wmi(PermissionError("denegado"), sin_uuid))
    monkeypatch.setattr("uuid.getnode", lambda: NODO_DE_RED)

    assert DRMValidator().machine_id == _huella(f"B2B_FALLBACK_{NODO_DE_RED}_NO_BIOS")


def test_sin_wmi_instalado_usa_la_mac_y_el_nombre_del_equipo(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "wmi", None)
    monkeypatch.setattr("uuid.getnode", lambda: NODO_DE_RED)
    monkeypatch.setattr(drm.platform, "node", lambda: "pc-oficina")

    assert DRMValidator().machine_id == _huella(f"B2B_FALLBACK_{NODO_DE_RED}_pc-oficina")


# --- Licencias -------------------------------------------------------------------------------


def test_sin_licencia_activa_no_hay_datos_y_rigen_los_valores_basicos(
    validador: DRMValidator,
) -> None:
    assert validador.license_data is None
    assert validador.get_max_cameras() == CAMARAS_POR_OMISION
    assert validador.get_tier() == "basic"
    assert validador.get_expiration_date() is None


def test_sin_archivo_de_licencia_no_valida_ni_registra_errores(
    validador: DRMValidator, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=drm.__name__):
        assert validador.validate_license() is False

    assert caplog.records == []


def test_activar_guarda_la_licencia_en_appdata_y_validar_la_vuelve_a_leer(
    validador: DRMValidator, llave: RSA.RsaKey, appdata: Path
) -> None:
    carga = _carga(validador, tier="enterprise", max_cams=CAMARAS_DE_LA_LICENCIA)
    licencia = _firmar(llave, carga)

    assert validador.activate_license(f"  {licencia}\n") is True
    otro = DRMValidator()

    assert (appdata / "license.key").read_text(encoding="utf-8") == licencia
    assert otro.validate_license() is True
    assert otro.license_data == carga
    assert otro.get_max_cameras() == CAMARAS_DE_LA_LICENCIA
    assert otro.get_tier() == "enterprise"
    assert otro.get_expiration_date() == "2030-06-15"


def test_una_licencia_sin_camaras_ni_nivel_usa_los_valores_basicos(
    validador: DRMValidator, llave: RSA.RsaKey
) -> None:
    validador.activate_license(_firmar(llave, _carga(validador)))

    assert validador.get_max_cameras() == CAMARAS_POR_OMISION
    assert validador.get_tier() == "basic"


def test_una_licencia_guardada_con_otra_llave_no_valida(
    validador: DRMValidator, llave_ajena: RSA.RsaKey, appdata: Path
) -> None:
    appdata.mkdir(parents=True, exist_ok=True)
    (appdata / "license.key").write_text(_firmar(llave_ajena, _carga(validador)), encoding="utf-8")

    assert validador.validate_license() is False
    assert validador.license_data is None


def test_un_archivo_de_licencia_ilegible_no_valida_y_se_registra(
    validador: DRMValidator, appdata: Path, caplog: pytest.LogCaptureFixture
) -> None:
    appdata.mkdir(parents=True, exist_ok=True)
    (appdata / "license.key").write_bytes(b"\xff\xfe\x00")

    with caplog.at_level(logging.WARNING, logger=drm.__name__):
        assert validador.validate_license() is False

    assert [r.getMessage() for r in caplog.records] == [
        "[DRM] License validation failed: UnicodeDecodeError"
    ]


def test_una_licencia_que_no_es_base64_se_rechaza_y_se_registra(
    validador: DRMValidator, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=drm.__name__):
        assert validador.activate_license("no-es-base64!") is False

    assert [r.getMessage() for r in caplog.records] == [
        "[DRM] Cryptographic verification failed: Error"
    ]


def test_la_licencia_vale_hasta_el_segundo_exacto_de_su_vencimiento(
    validador: DRMValidator, llave: RSA.RsaKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drm, "datetime", RelojEn(VENCE))

    assert validador.activate_license(_firmar(llave, _carga(validador))) is True


def test_la_licencia_vence_un_segundo_despues(
    validador: DRMValidator, llave: RSA.RsaKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drm, "datetime", RelojEn(VENCE + 1))

    assert validador.activate_license(_firmar(llave, _carga(validador))) is False
