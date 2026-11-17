"""Rotación de la llave maestra del proveedor (SPEC/10 F-02, T-02): fuera del repo y cifrada."""

import getpass
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from Crypto.PublicKey import RSA

from scripts import generar_llaves_maestras
from scripts.generar_llaves_maestras import (
    RotacionInvalidaError,
    embeber_llave_publica,
    guardar_par_de_llaves,
)
from src.security.drm import DRMValidator
from tests.licencias_firmadas import firmar, generar_llave
from tests.utilidades_scripts import RAIZ

CLAVE = "una frase larga para la boveda"  # pragma: allowlist secret
CODIGO_DE_RECHAZO = 2
VENCE = 1907755200
MODULO_DRM = '''"""DRM."""

_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
VIEJA
-----END PUBLIC KEY-----"""

_HARDWARE_SALT = b"sal"
'''


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def repositorio(tmp_path: Path) -> Path:
    """Copia mínima del repositorio: el módulo DRM y la llave pública que se entrega."""
    raiz = tmp_path / "repo"
    (raiz / "src" / "security").mkdir(parents=True)
    (raiz / "scripts").mkdir()
    (raiz / "src" / "security" / "drm.py").write_text(MODULO_DRM, encoding="utf-8")
    (raiz / "scripts" / "llave_publica_clientes.pem").write_text("VIEJA", encoding="utf-8")
    return raiz


@pytest.fixture
def rotacion(repositorio: Path, llave: RSA.RsaKey, monkeypatch: pytest.MonkeyPatch) -> Path:
    """La herramienta apuntando a la copia del repositorio y generando la llave de la corrida."""
    monkeypatch.setattr(generar_llaves_maestras, "RAIZ_DEL_REPOSITORIO", repositorio)
    monkeypatch.setattr(generar_llaves_maestras, "_generar", lambda: llave)
    return repositorio


@pytest.fixture
def contrasenas(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Lo que el dueño teclea cada vez que se le pide la contraseña."""
    respuestas = [CLAVE, CLAVE]
    monkeypatch.setattr(getpass, "getpass", lambda _texto: respuestas.pop(0))
    yield respuestas


def _pem_embebido(raiz: Path) -> bytes:
    codigo = (raiz / "src" / "security" / "drm.py").read_text(encoding="utf-8")
    bloque = re.search(r"-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----", codigo, re.S)
    assert bloque is not None
    return bloque.group(0).encode("ascii")


def test_la_privada_se_guarda_cifrada_y_la_publica_en_claro(
    llave: RSA.RsaKey, tmp_path: Path
) -> None:
    boveda = tmp_path / "boveda"

    guardar_par_de_llaves(llave, boveda, CLAVE)

    privada = (boveda / "llave_maestra_privada.pem").read_bytes()
    assert b"ENCRYPTED" in privada
    assert RSA.import_key(privada, passphrase=CLAVE) == llave
    with pytest.raises(ValueError, match="RSA key format is not supported"):
        RSA.import_key(privada)
    assert RSA.import_key((boveda / "llave_publica_clientes.pem").read_bytes()) == (
        llave.public_key()
    )


def test_una_boveda_dentro_del_repositorio_se_rechaza(llave: RSA.RsaKey) -> None:
    with pytest.raises(RotacionInvalidaError) as error:
        guardar_par_de_llaves(llave, RAIZ / "scripts", CLAVE)

    assert str(error.value) == (
        f"La llave privada no puede guardarse dentro del repositorio ({RAIZ / 'scripts'})."
    )
    assert not (RAIZ / "scripts" / "llave_maestra_privada.pem").exists()


def test_una_contrasena_corta_se_rechaza(llave: RSA.RsaKey, tmp_path: Path) -> None:
    with pytest.raises(RotacionInvalidaError) as error:
        guardar_par_de_llaves(llave, tmp_path / "boveda", "corta-11car")

    assert str(error.value) == "La contraseña debe tener al menos 12 caracteres."
    assert not (tmp_path / "boveda").exists()


def test_una_contrasena_de_doce_caracteres_alcanza(llave: RSA.RsaKey, tmp_path: Path) -> None:
    guardar_par_de_llaves(llave, tmp_path / "boveda", "doce-caract.")

    assert (tmp_path / "boveda" / "llave_maestra_privada.pem").exists()


def test_no_se_pisa_una_llave_que_ya_existe(llave: RSA.RsaKey, tmp_path: Path) -> None:
    guardar_par_de_llaves(llave, tmp_path, CLAVE)
    anterior = (tmp_path / "llave_maestra_privada.pem").read_bytes()

    with pytest.raises(RotacionInvalidaError) as error:
        guardar_par_de_llaves(generar_llave(), tmp_path, CLAVE)

    assert str(error.value) == f"Ya hay una llave en {tmp_path}: no se sobrescribe."
    assert (tmp_path / "llave_maestra_privada.pem").read_bytes() == anterior


def test_embeber_reemplaza_la_llave_del_drm_y_la_que_se_entrega(
    llave: RSA.RsaKey, repositorio: Path
) -> None:
    publica = llave.public_key().export_key()

    embeber_llave_publica(publica, repositorio)

    codigo = (repositorio / "src" / "security" / "drm.py").read_text(encoding="utf-8")
    assert _pem_embebido(repositorio) == publica
    assert codigo.startswith('"""DRM."""\n\n_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----\n')
    assert codigo.endswith('-----END PUBLIC KEY-----"""\n\n_HARDWARE_SALT = b"sal"\n')
    assert (repositorio / "scripts" / "llave_publica_clientes.pem").read_bytes() == publica


def test_embeber_falla_si_el_drm_no_tiene_una_sola_llave_publica(
    llave: RSA.RsaKey, repositorio: Path
) -> None:
    (repositorio / "src" / "security" / "drm.py").write_text('"""Sin llave."""\n', "utf-8")

    with pytest.raises(RotacionInvalidaError) as error:
        embeber_llave_publica(llave.public_key().export_key(), repositorio)

    assert str(error.value) == "src/security/drm.py debe tener exactamente una llave pública."
    assert (repositorio / "scripts" / "llave_publica_clientes.pem").read_text() == "VIEJA"


def test_la_rotacion_completa_deja_la_app_aceptando_solo_la_llave_nueva(
    llave: RSA.RsaKey,
    rotacion: Path,
    contrasenas: list[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    boveda = tmp_path / "boveda"

    codigo = generar_llaves_maestras.main(["--salida", str(boveda)])

    validador = DRMValidator(_pem_embebido(rotacion))
    carga = {"hw_id": validador.machine_id, "exp": VENCE}
    assert codigo == 0
    assert contrasenas == []
    assert validador.activate_license(firmar(llave, carga)) is True
    assert validador.activate_license(firmar(generar_llave(), carga)) is False
    assert capsys.readouterr().out == (
        f"Par de llaves nuevo en {boveda} (la privada va cifrada con su contraseña).\n"
        "La llave pública quedó embebida en src/security/drm.py y en "
        "scripts/llave_publica_clientes.pem.\n"
        "Siguiente: borre del repositorio cualquier llave privada anterior, haga commit y "
        "reconstruya el ejecutable. Las licencias y manifiestos firmados con la llave "
        "anterior dejan de valer.\n"
    )


def test_si_las_dos_contrasenas_no_coinciden_no_se_rota(
    rotacion: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respuestas = [CLAVE, CLAVE + "x"]
    monkeypatch.setattr(getpass, "getpass", lambda _texto: respuestas.pop(0))

    codigo = generar_llaves_maestras.main(["--salida", str(tmp_path / "boveda")])

    assert codigo == CODIGO_DE_RECHAZO
    assert capsys.readouterr().err == "No se rotó la llave: las dos contraseñas no coinciden.\n"
    assert not (tmp_path / "boveda").exists()
    assert (rotacion / "scripts" / "llave_publica_clientes.pem").read_text() == "VIEJA"


def test_las_contrasenas_se_piden_dos_veces_con_su_texto(
    rotacion: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preguntas: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda texto: preguntas.append(texto) or CLAVE)

    generar_llaves_maestras.main(["--salida", str(tmp_path / "boveda")])

    assert preguntas == ["Contraseña nueva para la llave privada: ", "Repita la contraseña: "]


def test_sin_carpeta_de_salida_no_se_rota(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        generar_llaves_maestras.main([])

    assert salida.value.code == CODIGO_DE_RECHAZO
    assert "the following arguments are required: --salida" in capsys.readouterr().err


def test_la_llave_que_se_genera_es_rsa_de_2048_bits() -> None:
    assert generar_llaves_maestras.BITS_DE_LA_LLAVE == len(bin(generar_llave().n)) - len("0b")
