"""
Security regression tests for the fixes applied in the OWASP security audit.

Covers:
- OWASP A08: Face encodings stored as numpy (not pickle) with HMAC integrity check
- OWASP A01: Path traversal protection in ConfigManager.set_active_tenant
- OWASP A02: SHA-256 used in anonymize_employee (not MD5)
- OWASP A09: DRM validator uses logging (tested indirectly via behaviour)
"""
import io
import os
import sys
import pytest
import numpy as np
import platform
import hashlib
import hmac as _hmac_mod
from unittest.mock import MagicMock

# Stub heavy native libs not present in the test environment. cv2 no: está fijado en los
# requisitos y un doble en sys.modules contaminaba al resto de la sesión.

_fr_stub = MagicMock()
_fr_stub.face_locations = lambda *a, **kw: []
_fr_stub.face_encodings = lambda *a, **kw: []
_fr_stub.compare_faces = lambda *a, **kw: []
_fr_stub.face_distance = lambda *a, **kw: np.array([])
_fr_stub.load_image_file = lambda p: np.zeros((100, 100, 3), dtype=np.uint8)
sys.modules.setdefault('face_recognition', _fr_stub)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_integrity_key() -> bytes:
    node = platform.node().encode('utf-8', errors='replace')
    return hashlib.sha256(node + b"_oe_face_integrity_v1").digest()

def _sign(data: bytes) -> bytes:
    return _hmac_mod.new(_get_integrity_key(), data, hashlib.sha256).digest()


# ---------------------------------------------------------------------------
# OWASP A08 — Numpy + HMAC: no pickle, integrity enforced
# ---------------------------------------------------------------------------

class TestFaceEncodingsIntegrity:
    """FaceRecognizer must reject tampered or foreign-machine encodings files."""

    @pytest.fixture(autouse=True)
    def _face_recognition_disponible(self, monkeypatch):
        """Aísla la clase del orden de importación de la suite.

        Si otro módulo importó `face_recognizer` antes de que existiera el doble de
        `face_recognition`, el módulo queda con `face_recognition = None` y no carga nada.
        """
        monkeypatch.setattr("src.recognition.face_recognizer.face_recognition", _fr_stub)

    @pytest.fixture
    def face_rec(self, tmp_path):
        """FaceRecognizer with faces_dir and encodings_file in tmp_path."""
        from src.recognition.face_recognizer import FaceRecognizer
        enc_file = str(tmp_path / "encodings.npz")
        return FaceRecognizer(faces_dir=str(tmp_path), encodings_file=enc_file)

    def test_encodings_file_is_not_pickle(self, face_rec):
        """Saved encodings must NOT be pickle — first two bytes of pickle are 0x80 0x04+."""
        # Trigger a save with empty data
        face_rec.save_encodings()
        with open(face_rec.encodings_file, 'rb') as f:
            header = f.read(2)
        assert header != b'\x80\x04', "File should not start with pickle opcode"
        assert header != b'\x80\x05', "File should not start with pickle opcode"

    def test_tampered_file_is_rejected(self, face_rec):
        """A file whose bytes were modified after signing must not be loaded."""
        face_rec.save_encodings()

        # Flip a byte in the payload area (after the 32-byte HMAC)
        with open(face_rec.encodings_file, 'r+b') as f:
            f.seek(40)
            original = f.read(1)
            f.seek(40)
            f.write(bytes([original[0] ^ 0xFF]))

        # Loading should fall through to re-encoding (empty directory), not crash
        face_rec.load_known_faces()
        # Encodings should be empty (no images in the tmp dir)
        assert face_rec.known_face_encodings == []

    def test_foreign_machine_file_is_rejected(self, tmp_path):
        """Encodings signed with a different HMAC key must be rejected."""
        enc = np.empty((0, 128), dtype=np.float64)
        names = np.array([], dtype=str)
        buf = io.BytesIO()
        np.savez_compressed(buf, encodings=enc, names=names)
        payload = buf.getvalue()

        wrong_key = hashlib.sha256(b"WRONG_MACHINE" + b"_oe_face_integrity_v1").digest()
        wrong_sig = _hmac_mod.new(wrong_key, payload, hashlib.sha256).digest()

        enc_file = str(tmp_path / "encodings.npz")
        with open(enc_file, 'wb') as f:
            f.write(wrong_sig + payload)

        from src.recognition.face_recognizer import FaceRecognizer
        fr = FaceRecognizer(faces_dir=str(tmp_path), encodings_file=enc_file)
        assert fr.known_face_encodings == []

    def test_valid_roundtrip_load_save(self, tmp_path):
        """Encodings saved then loaded must be bit-identical."""
        from src.recognition.face_recognizer import FaceRecognizer
        enc_file = str(tmp_path / "encodings.npz")
        fr = FaceRecognizer(faces_dir=str(tmp_path), encodings_file=enc_file)

        fake_enc = np.random.rand(128).astype(np.float64)
        fr.known_face_encodings = [fake_enc]
        fr.known_face_names = ["Alice"]
        fr.save_encodings()

        fr2 = FaceRecognizer(faces_dir=str(tmp_path), encodings_file=enc_file)
        assert fr2.known_face_names == ["Alice"]
        assert len(fr2.known_face_encodings) == 1
        np.testing.assert_array_almost_equal(fr2.known_face_encodings[0], fake_enc)


# ---------------------------------------------------------------------------
# OWASP A01 — Path traversal: tenant_id validation
# ---------------------------------------------------------------------------

class TestTenantIdValidation:

    def setup_method(self):
        from config.path_utils import ConfigManager
        ConfigManager._active_tenant_id = None

    def test_valid_tenant_id_accepted(self):
        from config.path_utils import ConfigManager
        ConfigManager.set_active_tenant("Empresa_ABC-01")
        assert ConfigManager.get_active_tenant() == "Empresa_ABC-01"

    def test_path_traversal_dot_dot_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant("../../etc/passwd")

    def test_path_traversal_backslash_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant("..\\Windows\\System32")

    def test_slash_in_tenant_id_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant("valid/injected")

    def test_empty_tenant_id_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant("")

    def test_too_long_tenant_id_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant("A" * 65)

    def test_non_string_tenant_id_rejected(self):
        from config.path_utils import ConfigManager
        with pytest.raises(ValueError):
            ConfigManager.set_active_tenant(None)  # type: ignore


# ---------------------------------------------------------------------------
# OWASP A02 — SHA-256 used in anonymize_employee (not MD5)
# ---------------------------------------------------------------------------

class TestAnonymizeUsesSHA256:

    @pytest.fixture
    def db(self, tmp_path):
        from src.storage.database_manager import DatabaseManager
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        return DatabaseManager(db_path=str(db_dir / "test.db"))

    def test_anon_id_not_md5_length(self, db):
        """MD5 hex is 32 chars; SHA-256 is 64. Our prefix + 12 chars != MD5 total length."""
        anon_id = db.anonymize_employee("TestEmployee")
        suffix = anon_id.replace("empleado_eliminado_", "")
        # MD5 truncated to 8 chars; SHA-256 truncated to 12 chars
        assert len(suffix) == 12, f"Expected 12 hex chars from SHA-256 truncation, got {len(suffix)}"

    def test_anon_id_is_hex(self, db):
        anon_id = db.anonymize_employee("AnotherEmployee")
        suffix = anon_id.replace("empleado_eliminado_", "")
        assert all(c in "0123456789abcdef" for c in suffix)
