"""Emisor de licencias como programa (SPEC/10 T-03): de la línea de comandos a la app."""

import getpass
from pathlib import Path

import pytest
from Crypto.PublicKey import RSA

from scripts import keygen_b2b
from src.security.drm import DRMValidator
from tests.licencias_firmadas import generar_llave, publica_de
from tests.utilidades_scripts import RAIZ, ejecutar_script

CODIGO_DE_RECHAZO = 2
CLAVE = "frase larga de la boveda"  # pragma: allowlist secret
CAMARAS_PEDIDAS = 8


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def archivo_de_llave(llave: RSA.RsaKey, tmp_path: Path) -> Path:
    ruta = tmp_path / "privada.pem"
    ruta.write_bytes(llave.export_key())
    return ruta


@pytest.fixture
def validador(llave: RSA.RsaKey, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DRMValidator:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return DRMValidator(publica_de(llave))


def _argumentos(validador: DRMValidator, llave: Path, tier: str, *extra: str) -> list[str]:
    registro = llave.parent / "emisiones.csv"
    return [
        "--hw-id", validador.machine_id, "--cliente", "acme-planta1", "--tier", tier,
        "--llave", str(llave), "--registro", str(registro), *extra,
    ]  # fmt: skip


def _licencia_impresa(salida: str) -> str:
    return salida.strip().splitlines()[-1]


def test_la_licencia_de_prueba_emitida_activa_el_modulo_epp_en_la_app(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = keygen_b2b.main(_argumentos(validador, archivo_de_llave, "prueba"))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert validador.activate_license(_licencia_impresa(salida)) is True
    assert validador.incluye_modulo("epp") is True
    assert validador.get_tier() == "prueba"
    assert salida.startswith(
        "Licencia prueba para acme-planta1: 14 días, 4 cámaras, módulos: epp.\n"
        "Llave de activación (copiar completa y enviar al cliente):\n"
    )


def test_la_licencia_de_aprendizaje_no_activa_el_modulo_epp(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    keygen_b2b.main(_argumentos(validador, archivo_de_llave, "aprendizaje"))

    salida = capsys.readouterr().out
    assert validador.activate_license(_licencia_impresa(salida)) is True
    assert validador.incluye_modulo("epp") is False
    assert "7 días, 4 cámaras, módulos: ninguno." in salida


def test_dias_camaras_y_modulos_se_pueden_pedir(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    opciones = ("--dias", "30", "--camaras", str(CAMARAS_PEDIDAS), "--modulos", "epp,eficiencia")

    keygen_b2b.main(_argumentos(validador, archivo_de_llave, "comercial", *opciones))

    salida = capsys.readouterr().out
    validador.activate_license(_licencia_impresa(salida))
    assert validador.get_max_cameras() == CAMARAS_PEDIDAS
    assert validador.incluye_modulo("eficiencia") is True
    assert "30 días, 8 cámaras, módulos: epp, eficiencia." in salida


def test_modulos_vacio_emite_sin_modulos(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    keygen_b2b.main(_argumentos(validador, archivo_de_llave, "comercial", "--modulos", ""))

    validador.activate_license(_licencia_impresa(capsys.readouterr().out))
    assert validador.incluye_modulo("epp") is False


def test_la_segunda_prueba_para_el_mismo_equipo_se_rechaza(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(validador, archivo_de_llave, "prueba")
    keygen_b2b.main(argumentos)
    capsys.readouterr()

    codigo = keygen_b2b.main(argumentos)

    salida = capsys.readouterr()
    assert codigo == CODIGO_DE_RECHAZO
    assert salida.out == ""
    assert salida.err.startswith("No se emitió la licencia: El equipo ")
    assert "ya recibió una licencia de prueba" in salida.err


def test_una_llave_cifrada_pide_la_contrasena(
    validador: DRMValidator,
    llave: RSA.RsaKey,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cifrada = tmp_path / "cifrada.pem"
    cifrada.write_bytes(llave.export_key(passphrase=CLAVE, pkcs=8))
    preguntas: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda texto: preguntas.append(texto) or CLAVE)

    codigo = keygen_b2b.main(_argumentos(validador, cifrada, "prueba"))

    assert codigo == 0
    assert preguntas == ["Contraseña de la llave: "]
    assert validador.activate_license(_licencia_impresa(capsys.readouterr().out)) is True


def test_una_llave_sin_cifrar_no_pide_contrasena(
    validador: DRMValidator, archivo_de_llave: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preguntas: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda texto: preguntas.append(texto) or CLAVE)

    keygen_b2b.main(_argumentos(validador, archivo_de_llave, "prueba"))

    assert preguntas == []


def test_una_contrasena_equivocada_no_emite_ni_registra(
    validador: DRMValidator,
    llave: RSA.RsaKey,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cifrada = tmp_path / "cifrada.pem"
    cifrada.write_bytes(llave.export_key(passphrase=CLAVE, pkcs=8))
    monkeypatch.setattr(getpass, "getpass", lambda texto: "otra")

    codigo = keygen_b2b.main(_argumentos(validador, cifrada, "prueba"))

    assert codigo == CODIGO_DE_RECHAZO
    assert capsys.readouterr().err.startswith("No se emitió la licencia: ")
    assert not (tmp_path / "emisiones.csv").exists()


def test_sin_archivo_de_llave_no_emite(
    validador: DRMValidator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = keygen_b2b.main(_argumentos(validador, tmp_path / "no-existe.pem", "prueba"))

    assert codigo == CODIGO_DE_RECHAZO
    assert "no-existe.pem" in capsys.readouterr().err


def test_un_registro_dentro_del_repositorio_se_rechaza(
    validador: DRMValidator, archivo_de_llave: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(validador, archivo_de_llave, "prueba")
    argumentos[argumentos.index("--registro") + 1] = str(RAIZ / "emisiones.csv")

    codigo = keygen_b2b.main(argumentos)

    assert codigo == CODIGO_DE_RECHAZO
    assert "fuera del repositorio" in capsys.readouterr().err
    assert not (RAIZ / "emisiones.csv").exists()


@pytest.mark.integration
def test_el_script_se_ejecuta_como_programa(archivo_de_llave: Path) -> None:
    resultado = ejecutar_script(
        "keygen_b2b.py",
        "--hw-id", "ab" * 32, "--cliente", "acme", "--tier", "comercial",
        "--llave", str(archivo_de_llave),
        "--registro", str(archivo_de_llave.parent / "emisiones.csv"),
    )  # fmt: skip

    assert resultado.returncode == 0, resultado.stderr
    assert "Licencia comercial para acme: 365 días" in resultado.stdout


AYUDA = """\
usage: keygen_b2b.py [-h] --hw-id HW_ID --cliente CLIENTE --tier {aprendizaje,prueba,comercial}
                     --llave LLAVE --registro REGISTRO [--dias DIAS] [--camaras CAMARAS]
                     [--modulos MODULOS]

Emisor de licencias del proveedor (SPEC/10 §4, T-03). NUNCA se entrega al cliente.

options:
  -h, --help            show this help message and exit
  --hw-id HW_ID         Machine ID que muestra la app
  --cliente CLIENTE     código corto, p. ej. acme-planta1
  --tier {aprendizaje,prueba,comercial}
  --llave LLAVE         llave privada .pem
  --registro REGISTRO   CSV fuera del repositorio
  --dias DIAS           por omisión, los del tier
  --camaras CAMARAS
  --modulos MODULOS     separados por coma; por omisión, los del tier
"""


def test_la_ayuda_explica_cada_opcion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setattr("sys.argv", ["keygen_b2b.py"])

    with pytest.raises(SystemExit):
        keygen_b2b.main(["--help"])

    assert capsys.readouterr().out == AYUDA


@pytest.mark.parametrize("opcion", ["--hw-id", "--cliente", "--tier", "--llave", "--registro"])
def test_sin_una_opcion_obligatoria_no_se_emite(
    opcion: str,
    validador: DRMValidator,
    archivo_de_llave: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argumentos = _argumentos(validador, archivo_de_llave, "prueba")
    posicion = argumentos.index(opcion)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        keygen_b2b.main(argumentos)

    assert salida.value.code == CODIGO_DE_RECHAZO
    assert f"the following arguments are required: {opcion}" in capsys.readouterr().err
