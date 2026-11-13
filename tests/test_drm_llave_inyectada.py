"""La llave pública del DRM se inyecta (SPEC/10 T-01, AC-T04).

En producción rige la llave embebida; las pruebas firman con un par generado en la corrida y
nunca leen la llave privada del proveedor.
"""

from pathlib import Path

import pytest
from Crypto.PublicKey import RSA

from src.security import drm
from src.security.drm import DRMValidator
from tests.licencias_firmadas import firmar, generar_llave, publica_de
from tests.utilidades_scripts import RAIZ

BITS_DE_LA_LLAVE = 2048
VENCE = 1907755200  # 15/06/2030 12:00 UTC
NOMBRE_DE_LA_LLAVE_PRIVADA = "tu_llave_maestra" + "_privada"


@pytest.fixture
def appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


def test_el_validador_acepta_una_licencia_firmada_con_la_llave_inyectada(
    appdata: Path, llave: RSA.RsaKey
) -> None:
    validador = DRMValidator(publica_de(llave))
    licencia = firmar(llave, {"hw_id": validador.machine_id, "exp": VENCE})

    assert validador.activate_license(licencia) is True


def test_sin_llave_inyectada_rige_la_embebida_y_rechaza_otra_firma(
    appdata: Path, llave: RSA.RsaKey
) -> None:
    validador = DRMValidator()
    licencia = firmar(llave, {"hw_id": validador.machine_id, "exp": VENCE})

    assert validador.activate_license(licencia) is False


def test_la_licencia_guardada_se_valida_con_la_llave_inyectada(
    appdata: Path, llave: RSA.RsaKey
) -> None:
    emisor = DRMValidator(publica_de(llave))
    emisor.activate_license(firmar(llave, {"hw_id": emisor.machine_id, "exp": VENCE}))

    assert DRMValidator(publica_de(llave)).validate_license() is True
    assert DRMValidator().validate_license() is False


def test_la_llave_embebida_es_la_publica_rsa_2048_que_se_entrega_a_los_clientes() -> None:
    publicada = (RAIZ / "scripts" / "llave_publica_clientes.pem").read_bytes()

    embebida = RSA.import_key(drm._PUBLIC_KEY_PEM)

    assert embebida.size_in_bits() == BITS_DE_LA_LLAVE
    assert embebida.has_private() is False
    assert embebida == RSA.import_key(publicada)


def test_ninguna_prueba_nombra_la_llave_privada_del_repositorio() -> None:
    archivos = [*RAIZ.glob("tests/**/*.py"), *RAIZ.glob("features/**/*.py")]

    culpables = [
        str(archivo.relative_to(RAIZ))
        for archivo in archivos
        if NOMBRE_DE_LA_LLAVE_PRIVADA in archivo.read_text(encoding="utf-8")
    ]

    assert culpables == []
