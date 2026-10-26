"""Crash log cifrado: formato, ubicación y aviso al usuario (CLAUDE.md §7, módulo crítico).

El formato en disco no puede cambiar: Soporte descifra logs que escribieron versiones viejas.
"""

import hashlib
import importlib
import logging
import re
import sys
import tkinter
import tkinter.messagebox
import traceback
from pathlib import Path
from types import ModuleType, TracebackType

import pytest
from Crypto.Cipher import AES

from config.path_utils import ConfigManager
from src.security import crash_logger

MAQUINA = "maquina-de-prueba"
INFO_DE_LA_CLAVE = b"oe_crash_log_aes256_v1"
MENSAJE = "La aplicación encontró un error inesperado.\n\nContacte a Soporte B2B."
NODO_DE_RED = 654321
LARGO_CABECERA = 4
LARGO_NONCE = 12
LARGO_TAG = 16
LARGO_LARGO = 4
ENCABEZADO = re.compile(r"\n===== CRASH \d{4}-\d{2}-\d{2}T[\d:.]+ =====\n")

Excepcion = tuple[type[BaseException], BaseException, TracebackType]


def _excepcion(mensaje: str) -> Excepcion:
    try:
        raise ValueError(mensaje)
    except ValueError:
        tipo, valor, rastro = sys.exc_info()
    assert tipo is not None and valor is not None and rastro is not None
    return tipo, valor, rastro


@pytest.fixture
def appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path / "OficinaEficiencia" / "Config" / "crash_logs.dat"


@pytest.fixture
def gancho(monkeypatch: pytest.MonkeyPatch, appdata: Path) -> None:
    """Deja sys.excepthook como estaba al terminar la prueba."""
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)


def _drm_vigente() -> ModuleType:
    """El src.security.drm que importará crash_logger en la llamada.

    Otras pruebas lo sacan de sys.modules; el objeto importado al cargar este archivo puede no
    ser ya el que se usa.
    """
    return importlib.import_module("src.security.drm")


class DRMQueFalla:
    def __init__(self) -> None:
        raise RuntimeError("sin WMI")


class RaizFalsa:
    def __init__(self, registro: list[str]) -> None:
        self._registro = registro

    def withdraw(self) -> None:
        self._registro.append("withdraw")

    def destroy(self) -> None:
        self._registro.append("destroy")


@pytest.fixture
def dialogo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    registro: list[str] = []
    monkeypatch.setattr(tkinter, "Tk", lambda: RaizFalsa(registro))
    monkeypatch.setattr(
        tkinter.messagebox, "showerror", lambda titulo, texto: registro.append(f"{titulo}|{texto}")
    )
    return registro


def test_la_entrada_tiene_cabecera_nonce_tag_largo_y_texto_con_la_clave_v1() -> None:
    entrada = crash_logger.encrypt_entry(b"hola", MAQUINA)

    nonce_ini = LARGO_CABECERA
    tag_ini = nonce_ini + LARGO_NONCE
    largo_ini = tag_ini + LARGO_TAG
    texto_ini = largo_ini + LARGO_LARGO
    clave = hashlib.sha256(MAQUINA.encode() + INFO_DE_LA_CLAVE).digest()
    cifrador = AES.new(clave, AES.MODE_GCM, nonce=entrada[nonce_ini:tag_ini])
    texto = cifrador.decrypt_and_verify(entrada[texto_ini:], entrada[tag_ini:largo_ini])
    assert entrada[:LARGO_CABECERA] == b"OEC1"
    assert int.from_bytes(entrada[largo_ini:texto_ini], "big") == len(b"hola")
    assert texto == b"hola"


def test_sin_huella_y_sin_drm_cifra_con_el_nodo_de_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_drm_vigente(), "DRMValidator", DRMQueFalla)
    monkeypatch.setattr("uuid.getnode", lambda: NODO_DE_RED)
    log = tmp_path / "c.dat"
    log.write_bytes(crash_logger.encrypt_entry(b"respaldo"))

    texto = crash_logger.decrypt_crash_logs(machine_id=f"FALLBACK_{NODO_DE_RED}", path=str(log))

    assert texto == "respaldo"


def test_el_log_va_a_config_dentro_de_appdata(appdata: Path) -> None:
    ruta = crash_logger.write_crash(*_excepcion("boom"), machine_id=MAQUINA)

    assert Path(ruta) == appdata
    assert appdata.is_file()


def test_si_config_manager_falla_arma_la_misma_ruta_a_mano(
    appdata: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def falla(*_carpetas: str) -> str:
        raise OSError("sin permisos")

    monkeypatch.setattr(ConfigManager, "get_appdata_path", falla)
    appdata.parent.mkdir(parents=True)

    ruta = crash_logger.write_crash(*_excepcion("boom"), machine_id=MAQUINA)

    assert Path(ruta) == appdata


def test_sin_appdata_usa_la_carpeta_personal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # una ruta relativa equivocada también queda en tmp_path
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def falla(*_carpetas: str) -> str:
        raise OSError("sin permisos")

    monkeypatch.setattr(ConfigManager, "get_appdata_path", falla)

    ruta = crash_logger.write_crash(*_excepcion("boom"), machine_id=MAQUINA)

    assert Path(ruta) == tmp_path / "OficinaEficiencia" / "Config" / "crash_logs.dat"


def test_la_entrada_es_el_encabezado_con_fecha_y_el_traceback_completo(appdata: Path) -> None:
    excepcion = _excepcion("secreto")
    esperado = "".join(traceback.format_exception(*excepcion))

    crash_logger.write_crash(*excepcion, machine_id=MAQUINA)
    texto = crash_logger.decrypt_crash_logs(machine_id=MAQUINA)

    encabezado = ENCABEZADO.match(texto)
    assert encabezado is not None
    assert texto[encabezado.end() :] == esperado


def test_un_texto_que_no_es_utf8_valido_se_guarda_con_reemplazo(appdata: Path) -> None:
    crash_logger.write_crash(*_excepcion("roto \ud800"), machine_id=MAQUINA)

    texto = crash_logger.decrypt_crash_logs(machine_id=MAQUINA)

    assert "ValueError: roto ?" in texto


def test_bytes_descifrados_que_no_son_utf8_se_leen_con_reemplazo(tmp_path: Path) -> None:
    log = tmp_path / "c.dat"
    log.write_bytes(crash_logger.encrypt_entry(b"a\xffb", MAQUINA))

    assert crash_logger.decrypt_crash_logs(machine_id=MAQUINA, path=str(log)) == "a�b"


def test_la_ruta_explicita_tiene_prioridad_sobre_la_de_appdata(
    tmp_path: Path, appdata: Path
) -> None:
    log = tmp_path / "otro.dat"
    log.write_bytes(crash_logger.encrypt_entry(b"explicito", MAQUINA))

    assert crash_logger.decrypt_crash_logs(machine_id=MAQUINA, path=str(log)) == "explicito"


def test_sin_log_devuelve_texto_vacio(tmp_path: Path) -> None:
    texto = crash_logger.decrypt_crash_logs(machine_id=MAQUINA, path=str(tmp_path / "no.dat"))

    assert texto == ""


def test_varias_entradas_se_leen_en_orden_y_lo_que_sigue_sin_cabecera_se_ignora(
    tmp_path: Path,
) -> None:
    log = tmp_path / "c.dat"
    entradas = [crash_logger.encrypt_entry(t, MAQUINA) for t in (b"uno", b"dos", b"tres")]
    log.write_bytes(b"".join(entradas) + b"basura")

    assert crash_logger.decrypt_crash_logs(machine_id=MAQUINA, path=str(log)) == "unodostres"


def test_una_entrada_manipulada_se_marca_ilegible_sin_perder_las_demas(tmp_path: Path) -> None:
    log = tmp_path / "c.dat"
    manipulada = bytearray(crash_logger.encrypt_entry(b"dos", MAQUINA))
    manipulada[-1] ^= 0xFF
    log.write_bytes(
        crash_logger.encrypt_entry(b"uno", MAQUINA)
        + bytes(manipulada)
        + crash_logger.encrypt_entry(b"tres", MAQUINA)
    )

    texto = crash_logger.decrypt_crash_logs(machine_id=MAQUINA, path=str(log))

    assert texto == "uno[entrada ilegible: clave incorrecta o log manipulado]tres"


@pytest.mark.usefixtures("gancho")
def test_el_gancho_avisa_el_mensaje_generico_y_registra_la_ruta(
    appdata: Path, caplog: pytest.LogCaptureFixture
) -> None:
    avisos: list[str] = []
    crash_logger.install_global_excepthook(notify=avisos.append)

    with caplog.at_level(logging.ERROR, logger=crash_logger.__name__):
        sys.excepthook(*_excepcion("boom"))

    assert avisos == [MENSAJE]
    assert [r.getMessage() for r in caplog.records] == [
        f"[CrashLogger] Crash cifrado registrado en {appdata}"
    ]


@pytest.mark.usefixtures("gancho")
def test_sin_notify_muestra_un_dialogo_de_error(dialogo: list[str]) -> None:
    crash_logger.install_global_excepthook()

    sys.excepthook(*_excepcion("boom"))

    assert dialogo == ["withdraw", f"Error|{MENSAJE}", "destroy"]


@pytest.mark.usefixtures("gancho")
def test_sin_interfaz_grafica_imprime_el_mensaje(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def sin_pantalla() -> None:
        raise tkinter.TclError("no display name")

    monkeypatch.setattr(tkinter, "Tk", sin_pantalla)
    crash_logger.install_global_excepthook()

    sys.excepthook(*_excepcion("boom"))

    assert capsys.readouterr().out == MENSAJE + "\n"
