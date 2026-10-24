# tests/test_crash_logger.py
# TASK-5.1 DoD: el crash log en disco es ilegible (cifrado AES-256) y el
# usuario solo ve un mensaje generico "Contacte a Soporte B2B".

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.security import crash_logger


def _sin_pantalla():
    raise RuntimeError("las pruebas no abren ventanas")


def test_crash_log_is_encrypted_and_roundtrips(tmp_path, monkeypatch):
    log_path = str(tmp_path / "crash_logs.dat")
    monkeypatch.setattr(crash_logger, "_crash_log_path", lambda: log_path)

    machine_id = "a" * 64
    try:
        raise ValueError("Test Crash B2B - secreto arquitectonico")
    except ValueError:
        et, ev, tb = sys.exc_info()
        crash_logger.write_crash(et, ev, tb, machine_id=machine_id)

    raw = open(log_path, "rb").read()
    # Ilegible a simple vista: el texto del traceback NO aparece en claro.
    assert b"secreto arquitectonico" not in raw
    assert b"Traceback" not in raw
    assert raw[:4] == b"OEC1"  # cabecera del contenedor cifrado

    # Soporte puede descifrar con la clave del hardware.
    decrypted = crash_logger.decrypt_crash_logs(machine_id=machine_id, path=log_path)
    assert "Test Crash B2B - secreto arquitectonico" in decrypted
    assert "ValueError" in decrypted


def test_wrong_machine_cannot_decrypt(tmp_path, monkeypatch):
    log_path = str(tmp_path / "crash_logs.dat")
    monkeypatch.setattr(crash_logger, "_crash_log_path", lambda: log_path)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        crash_logger.write_crash(*sys.exc_info(), machine_id="b" * 64)

    bad = crash_logger.decrypt_crash_logs(machine_id="c" * 64, path=log_path)
    assert "boom" not in bad
    assert "ilegible" in bad


def test_excepthook_installed_and_shows_generic_message(monkeypatch, tmp_path):
    monkeypatch.setattr(crash_logger, "_crash_log_path", lambda: str(tmp_path / "c.dat"))
    # Hermética: restaura el gancho al terminar y nunca abre un diálogo real de Tk (que
    # bloquearía la prueba si el aviso no llegara a `notify`).
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr("tkinter.Tk", _sin_pantalla)
    seen = {}
    crash_logger.install_global_excepthook(notify=lambda msg: seen.setdefault("msg", msg))
    assert sys.excepthook is not sys.__excepthook__

    try:
        raise Exception("Test Crash B2B")
    except Exception:
        sys.excepthook(*sys.exc_info())

    assert "Soporte B2B" in seen.get("msg", "")
    # El traceback se persistio cifrado.
    assert os.path.exists(str(tmp_path / "c.dat"))
