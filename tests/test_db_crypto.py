"""Bóveda de la base en reposo: casos que tests/test_db_encryption.py no fija (CLAUDE.md §7).

La clave y el formato del blob deben seguir siendo los mismos: las bases ya cifradas en las PCs
de los clientes tienen que poder abrirse con la versión nueva.
"""

import hashlib
import importlib
import logging
import os
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest

from src.security import db_crypto
from src.security.db_crypto import EncryptedDBVault, derive_db_key, is_sqlite_file

INFO_DE_LA_CLAVE = b"oe_db_at_rest_aes256_v1"
NODO_DE_RED = 123456
CLAVE = derive_db_key("maquina-de-prueba")


def _base_en_claro(ruta: Path) -> None:
    conexion = sqlite3.connect(ruta)
    conexion.execute("CREATE TABLE empleados (id INTEGER, nombre TEXT)")
    conexion.commit()
    conexion.close()


def _drm_vigente() -> ModuleType:
    """El src.security.drm que importará db_crypto en la llamada.

    Otras pruebas lo sacan de sys.modules; el objeto importado al cargar este archivo puede no
    ser ya el que se usa.
    """
    return importlib.import_module("src.security.drm")


class DRMQueFalla:
    def __init__(self) -> None:
        raise RuntimeError("sin WMI")


class DRMDePrueba:
    machine_id = "huella-de-hardware"


def test_la_clave_es_el_sha256_de_la_huella_y_la_etiqueta_v1() -> None:
    esperada = hashlib.sha256(b"maquina-de-prueba" + INFO_DE_LA_CLAVE).digest()

    assert derive_db_key("maquina-de-prueba") == esperada


def test_sin_huella_explicita_usa_la_del_drm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_drm_vigente(), "DRMValidator", DRMDePrueba)

    assert derive_db_key() == derive_db_key("huella-de-hardware")


def test_si_el_drm_falla_usa_el_nodo_de_red_como_respaldo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_drm_vigente(), "DRMValidator", DRMQueFalla)
    monkeypatch.setattr("uuid.getnode", lambda: NODO_DE_RED)

    assert derive_db_key() == derive_db_key(f"FALLBACK_{NODO_DE_RED}")


def test_un_blob_sin_la_cabecera_de_la_boveda_es_invalido(tmp_path: Path) -> None:
    boveda = EncryptedDBVault(str(tmp_path / "local.db"), key=CLAVE)
    Path(boveda.enc_path).write_bytes(b"SQLite format 3\x00" + bytes(32))

    with pytest.raises(
        ValueError, match=r"^Formato de boveda invalido \(cabecera no reconocida\)\.$"
    ):
        boveda.unlock()


def test_cifrar_sin_base_en_claro_falla_nombrando_la_ruta(tmp_path: Path) -> None:
    ruta = tmp_path / "local.db"

    with pytest.raises(FileNotFoundError) as error:
        EncryptedDBVault(str(ruta), key=CLAVE).lock()

    assert str(error.value) == f"No existe BD en claro para cifrar: {ruta}"


def test_cifrar_avisa_si_no_puede_borrar_la_base_en_claro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ruta = tmp_path / "local.db"
    _base_en_claro(ruta)

    def borrado_bloqueado(_ruta: str) -> None:
        raise PermissionError("en uso")

    monkeypatch.setattr(db_crypto.os, "remove", borrado_bloqueado)
    with caplog.at_level(logging.WARNING, logger=db_crypto.__name__):
        EncryptedDBVault(str(ruta), key=CLAVE).lock()

    assert ruta.exists()
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "[DBVault] No se pudo borrar el .db en claro (en uso?)."
    ]


def test_cifrar_y_descifrar_quedan_registrados(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ruta = tmp_path / "local.db"
    _base_en_claro(ruta)
    boveda = EncryptedDBVault(str(ruta), key=CLAVE)

    with caplog.at_level(logging.INFO, logger=db_crypto.__name__):
        boveda.lock()
        boveda.unlock()

    assert [r.getMessage() for r in caplog.records] == [
        f"[DBVault] BD cifrada en reposo -> {boveda.enc_path}",
        f"[DBVault] BD descifrada para uso -> {ruta}",
    ]


def test_descifrar_una_ruta_relativa_no_crea_carpetas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _base_en_claro(tmp_path / "local.db")
    boveda = EncryptedDBVault("local.db", key=CLAVE)
    boveda.lock()

    boveda.unlock()

    assert sorted(os.listdir(tmp_path)) == ["local.db", "local.enc_db"]
    assert is_sqlite_file("local.db") is True


def test_un_archivo_que_no_existe_no_es_una_base_sqlite(tmp_path: Path) -> None:
    assert is_sqlite_file(str(tmp_path / "no_existe.db")) is False
