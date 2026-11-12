# tests/test_drm_rsa_b2b.py
# ===================================================================
# Tests de Seguridad B2B: WMI Fingerprint + RSA-2048 License Validation
# TASK-4.1 DoD: Hash determinista + Fallback WMI robusto
# TASK-4.2 DoD: Licencias forjadas rechazadas, validas aceptadas
# ===================================================================

import unittest
import sys
import os
import json
import base64
import hashlib
import time

# Setup path for project imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import src.security
import src.security.drm


@pytest.fixture(autouse=True)
def _modulo_drm_restaurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estas pruebas borran src.security.drm de sys.modules para reimportarlo; al terminar,
    sys.modules y el paquete vuelven a apuntar al mismo módulo original. Si no, un monkeypatch
    posterior parcha un módulo y el código importa otro (tests/test_aislamiento_pruebas_drm.py).
    """
    monkeypatch.setitem(sys.modules, "src.security.drm", src.security.drm)
    monkeypatch.setattr(src.security, "drm", src.security.drm)


class TestHardwareFingerprint(unittest.TestCase):
    """TASK-4.1: Validar que el fingerprint WMI sea determinista e inmutable."""

    def test_fingerprint_deterministic(self):
        """El hash debe ser identico en 10 iteraciones consecutivas (DoD 4.1)."""
        from src.security.drm import DRMValidator

        drm = DRMValidator()

        hashes = []
        for _ in range(10):
            # Forzar regeneracion fresca cada vez
            fresh_hash = drm._generate_machine_id()
            hashes.append(fresh_hash)

        # Todas las iteraciones deben producir el mismo hash
        self.assertTrue(
            len(set(hashes)) == 1,
            f"Fingerprint NO es determinista: {len(set(hashes))} hashes distintos generados",
        )
        print(f"[PASS] Fingerprint determinista: {hashes[0][:20]}...")

    def test_fingerprint_is_sha256(self):
        """El hash debe ser un SHA-256 valido (64 caracteres hexadecimales)."""
        from src.security.drm import DRMValidator

        drm = DRMValidator()
        mid = drm.machine_id

        self.assertEqual(len(mid), 64, f"Longitud incorrecta: {len(mid)} (esperado 64)")
        self.assertTrue(all(c in "0123456789abcdef" for c in mid), "No es hexadecimal valido")
        print(f"[PASS] Machine ID SHA-256 valido: {mid[:20]}...")

    def test_fingerprint_not_empty(self):
        """El hash nunca debe ser vacio o None."""
        from src.security.drm import DRMValidator

        drm = DRMValidator()
        self.assertIsNotNone(drm.machine_id)
        self.assertTrue(len(drm.machine_id) > 0)


class TestWMIFallback(unittest.TestCase):
    """TASK-4.1: Simular fallo de WMI y verificar que el Fallback funcione."""

    def test_wmi_crash_fallback(self):
        """
        Simulacion de crasheo WMI: Ocultamos el modulo wmi temporalmente
        para forzar el bloque except y verificar que el Fallback (MAC address)
        genere un hash valido sin crashear.
        """
        import importlib

        # Guardar el modulo wmi real si existe
        original_wmi = sys.modules.get("wmi")

        try:
            # SIMULAR CRASH: Forzar que "import wmi" lance ImportError
            sys.modules["wmi"] = None  # Esto causa ImportError al intentar import

            # Reimportar drm para que use el modulo "roto"
            if "src.security.drm" in sys.modules:
                del sys.modules["src.security.drm"]

            from src.security.drm import DRMValidator

            drm = DRMValidator()

            # El Fallback debe generar un hash valido (no crashear)
            fallback_hash = drm.machine_id
            self.assertIsNotNone(fallback_hash)
            self.assertEqual(len(fallback_hash), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in fallback_hash))

            print(f"[PASS] WMI Fallback exitoso. Hash generado: {fallback_hash[:20]}...")

        finally:
            # Restaurar el modulo wmi original
            if original_wmi is not None:
                sys.modules["wmi"] = original_wmi
            elif "wmi" in sys.modules:
                del sys.modules["wmi"]

            # Limpiar cache del modulo drm para proximos tests
            if "src.security.drm" in sys.modules:
                del sys.modules["src.security.drm"]

    def test_fallback_hash_is_different_from_normal(self):
        """
        El hash de fallback PUEDE diferir del hash WMI real
        (porque usan componentes distintos), pero ambos deben ser validos.
        """
        # Obtener hash normal
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm_normal = DRMValidator()
        normal_hash = drm_normal.machine_id

        # Obtener hash con fallback (simulando WMI crash)
        original_wmi = sys.modules.get("wmi")
        try:
            sys.modules["wmi"] = None
            if "src.security.drm" in sys.modules:
                del sys.modules["src.security.drm"]

            from src.security.drm import DRMValidator as DRMFallback

            drm_fallback = DRMFallback()
            fallback_hash = drm_fallback.machine_id

            # Ambos deben ser SHA-256 validos
            self.assertEqual(len(normal_hash), 64)
            self.assertEqual(len(fallback_hash), 64)

            print(f"[INFO] Hash WMI:      {normal_hash[:30]}...")
            print(f"[INFO] Hash Fallback:  {fallback_hash[:30]}...")
            print(f"[INFO] Son iguales: {normal_hash == fallback_hash}")

        finally:
            if original_wmi is not None:
                sys.modules["wmi"] = original_wmi
            elif "wmi" in sys.modules:
                del sys.modules["wmi"]
            if "src.security.drm" in sys.modules:
                del sys.modules["src.security.drm"]


class TestRSALicenseValidation(unittest.TestCase):
    """TASK-4.2: Validar el ciclo completo de licenciamiento RSA-2048."""

    @classmethod
    def setUpClass(cls):
        """Cargar llaves maestras para emitir licencias de prueba."""
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256

        cls.SHA256 = SHA256
        cls.pkcs1_15 = pkcs1_15

        # Cargar llave privada del proveedor
        key_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "tu_llave_maestra_privada.pem"
        )
        with open(key_path, "rb") as f:
            cls.private_key = RSA.import_key(f.read())

    def _sign_license(self, payload_dict):
        """Helper: Firma un payload con la llave privada real."""
        payload_str = json.dumps(payload_dict, separators=(",", ":"))
        hash_obj = self.SHA256.new(payload_str.encode("utf-8"))
        firma = self.pkcs1_15.new(self.private_key).sign(hash_obj)
        raw = payload_str.encode("utf-8") + b"||SIGNATURE||" + firma
        return base64.b64encode(raw).decode("utf-8")

    def test_valid_license_accepted(self):
        """Una licencia firmada correctamente con hardware ID valido se acepta."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        # Emitir licencia valida para ESTE hardware
        payload = {
            "hw_id": drm.machine_id,
            "exp": int(time.time()) + 86400 * 365,  # 1 anio
            "tier": "enterprise",
            "max_cams": 16,
        }
        license_b64 = self._sign_license(payload)

        # Validar
        result = drm.activate_license(license_b64)
        self.assertTrue(result, "Licencia valida fue RECHAZADA incorrectamente")
        self.assertEqual(drm.get_max_cameras(), 16)
        self.assertEqual(drm.get_tier(), "enterprise")
        print(
            f"[PASS] Licencia RSA-2048 valida aceptada. Tier: {drm.get_tier()}, Cams: {drm.get_max_cameras()}"
        )

        # Limpiar archivo de licencia creado por el test
        if os.path.exists(drm.license_path):
            os.remove(drm.license_path)

    def test_forged_license_rejected(self):
        """Una licencia con firma aleatoria (forjada) es rechazada."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        # Crear una licencia FALSA con firma inventada
        payload = {
            "hw_id": drm.machine_id,
            "exp": int(time.time()) + 86400,
            "tier": "pirata",
            "max_cams": 999,
        }
        payload_str = json.dumps(payload, separators=(",", ":"))
        fake_signature = os.urandom(256)  # Firma aleatoria de 256 bytes
        raw = payload_str.encode("utf-8") + b"||SIGNATURE||" + fake_signature
        forged_b64 = base64.b64encode(raw).decode("utf-8")

        result = drm.activate_license(forged_b64)
        self.assertFalse(result, "Licencia FORJADA fue aceptada (VULNERABILIDAD CRITICA)")
        print("[PASS] Licencia forjada rechazada correctamente")

    def test_expired_license_rejected(self):
        """Una licencia firmada correctamente PERO expirada es rechazada."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        # Emitir licencia que ya expiro (fecha en el pasado)
        payload = {
            "hw_id": drm.machine_id,
            "exp": int(time.time()) - 86400,  # Expiro ayer
            "tier": "enterprise",
            "max_cams": 4,
        }
        license_b64 = self._sign_license(payload)

        result = drm.activate_license(license_b64)
        self.assertFalse(result, "Licencia EXPIRADA fue aceptada (VULNERABILIDAD)")
        print("[PASS] Licencia expirada rechazada correctamente")

    def test_wrong_hardware_rejected(self):
        """Una licencia valida para OTRO hardware es rechazada en ESTE hardware."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        # Emitir licencia para un Machine ID totalmente diferente
        payload = {
            "hw_id": "aaaa" * 16,  # 64 chars falso
            "exp": int(time.time()) + 86400 * 365,
            "tier": "enterprise",
            "max_cams": 4,
        }
        license_b64 = self._sign_license(payload)

        result = drm.activate_license(license_b64)
        self.assertFalse(result, "Licencia de OTRO hardware fue aceptada (VULNERABILIDAD)")
        print("[PASS] Licencia de otro hardware rechazada correctamente")

    def test_tampered_payload_rejected(self):
        """Si alguien modifica el exp (Epoch) del payload para hackear la fecha, la firma colapsa."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        # Emitir licencia valida real
        payload = {
            "hw_id": drm.machine_id,
            "exp": int(time.time()) + 86400 * 30,  # 30 dias
            "tier": "enterprise",
            "max_cams": 4,
        }
        license_b64 = self._sign_license(payload)

        # AHORA: Tamper — cambiar exp a 2099 (intento de hackeo de fecha)
        raw = base64.b64decode(license_b64)
        parts = raw.split(b"||SIGNATURE||", 1)
        original_payload = json.loads(parts[0].decode("utf-8"))
        original_payload["exp"] = int(time.time()) + 86400 * 365 * 73  # "Hack" a 2099
        tampered_payload = json.dumps(original_payload, separators=(",", ":")).encode("utf-8")
        tampered_raw = tampered_payload + b"||SIGNATURE||" + parts[1]
        tampered_b64 = base64.b64encode(tampered_raw).decode("utf-8")

        result = drm.activate_license(tampered_b64)
        self.assertFalse(
            result, "Licencia TAMPERED (fecha hackeada) fue aceptada (VULNERABILIDAD CRITICA)"
        )
        print("[PASS] Licencia con payload alterado rechazada — firma RSA colapso correctamente")

    def test_garbage_input_rejected(self):
        """Texto aleatorio no-Base64 es rechazado sin crash."""
        if "src.security.drm" in sys.modules:
            del sys.modules["src.security.drm"]

        from src.security.drm import DRMValidator

        drm = DRMValidator()

        garbage_inputs = [
            "",
            "esto-no-es-base64",
            "AAAA" * 100,
            "!!!@@##$$%%",
            "eyJ0ZXN0IjogMX0=",  # Base64 valido pero sin firma
        ]

        for garbage in garbage_inputs:
            result = drm.activate_license(garbage)
            self.assertFalse(result, f"Input basura '{garbage[:20]}...' fue aceptado")

        print("[PASS] Todos los inputs basura rechazados sin crash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
