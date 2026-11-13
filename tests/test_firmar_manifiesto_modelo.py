"""Firma del manifiesto de un modelo afinado (SPEC/10 F-05, T-07): del proveedor a la app."""

import getpass
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from Crypto.PublicKey import RSA

from scripts import firmar_manifiesto_modelo
from scripts.firmar_manifiesto_modelo import (
    ModeloNoFirmableError,
    contenido_a_firmar,
    entrada_del_modelo,
)
from src.models.model_verifier import verify_model
from src.models.modelo_de_la_app import resolver_modelo
from tests.licencias_firmadas import generar_llave, publica_de
from tests.utilidades_scripts import ejecutar_script

PESOS = b"pesos afinados para acme"
SHA = hashlib.sha256(PESOS).hexdigest()
FECHA = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
CODIGO_DE_RECHAZO = 2
CLAVE = "frase larga de la boveda"  # pragma: allowlist secret
ENTRADA: dict[str, Any] = {
    "nombre": "epp-acme",
    "version": "0.1-acme",
    "archivo": "models/epp_acme.onnx",
    "sha256": SHA,
    "motor": "onnx",
    "clases": {"0": "persona", "1": "cabeza", "2": "casco", "3": "chaleco"},
    "media": [0.485, 0.456, 0.406],
    "desviacion": [0.229, 0.224, 0.225],
}
OTRA = {**ENTRADA, "nombre": "base", "archivo": "models/epp_base.onnx"}


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def proveedor(llave: RSA.RsaKey, tmp_path: Path) -> Path:
    """Carpeta del proveedor: el modelo exportado, el manifiesto en claro y su llave privada."""
    (tmp_path / "epp_acme.onnx").write_bytes(PESOS)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"version_esquema": 1, "modelos": [OTRA, ENTRADA]}), encoding="utf-8"
    )
    (tmp_path / "privada.pem").write_bytes(llave.export_key())
    return tmp_path


def _argumentos(proveedor: Path, **cambios: str) -> list[str]:
    opciones = {
        "--modelo": str(proveedor / "epp_acme.onnx"),
        "--manifiesto": str(proveedor / "manifest.json"),
        "--cliente": "acme-planta1",
        "--llave": str(proveedor / "privada.pem"),
        "--salida": str(proveedor / "instalar" / "modelo.manifest"),
        **cambios,
    }
    return [texto for par in opciones.items() for texto in par]


def test_la_entrada_del_modelo_es_la_que_declara_su_archivo(proveedor: Path) -> None:
    manifiesto = {"modelos": [OTRA, ENTRADA]}

    assert entrada_del_modelo(proveedor / "epp_acme.onnx", manifiesto) == ENTRADA


def test_el_contenido_firmado_lleva_cliente_fecha_y_el_modelo_sin_carpetas() -> None:
    assert contenido_a_firmar(ENTRADA, "acme-planta1", FECHA) == {
        "version_esquema": 1,
        "cliente": "acme-planta1",
        "fecha": "2026-11-12T15:00:00+00:00",
        "modelos": [{**ENTRADA, "archivo": "epp_acme.onnx"}],
    }


@pytest.mark.parametrize(
    ("manifiesto", "mensaje"),
    [
        ({"modelos": [OTRA]}, "epp_acme.onnx no está declarado en el manifiesto."),
        ({}, "epp_acme.onnx no está declarado en el manifiesto."),
        (
            {"modelos": [{**ENTRADA, "sha256": "cd" * 32}]},
            "El sha256 de epp_acme.onnx no coincide con el del manifiesto: exporta de nuevo.",
        ),
        (
            {"modelos": [{**ENTRADA, "motor": "ultralytics"}]},
            "Solo se firman modelos del motor onnx; epp_acme.onnx declara ultralytics.",
        ),
    ],
    ids=["no_declarado", "sin_modelos", "otro_hash", "otro_motor"],
)
def test_un_modelo_que_no_coincide_con_su_manifiesto_no_se_firma(
    manifiesto: dict[str, Any], mensaje: str, proveedor: Path
) -> None:
    with pytest.raises(ModeloNoFirmableError) as error:
        entrada_del_modelo(proveedor / "epp_acme.onnx", manifiesto)

    assert str(error.value) == mensaje


def test_el_manifiesto_firmado_se_instala_y_la_app_carga_el_modelo(
    proveedor: Path, llave: RSA.RsaKey, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = firmar_manifiesto_modelo.main(_argumentos(proveedor))
    instalado = proveedor / "instalar"
    (instalado / "epp_acme.onnx").write_bytes(PESOS)

    modelo = resolver_modelo(instalado, publica_de(llave))

    assert codigo == 0
    assert (modelo.ruta, modelo.motor) == (str(instalado / "epp_acme.onnx"), "onnx")
    assert verify_model(modelo.ruta, modelo.aprobados) is True
    assert modelo.leer_manifiesto()["cliente"] == "acme-planta1"
    assert capsys.readouterr().out == (
        f"Manifiesto firmado en {instalado / 'modelo.manifest'}.\n"
        "Copie ese archivo y epp_acme.onnx a la carpeta OficinaEficiencia\\modelo dentro de "
        "%APPDATA% del equipo del cliente y reinicie la aplicación.\n"
    )


def test_la_fecha_firmada_es_la_del_momento_de_firmar(
    proveedor: Path, llave: RSA.RsaKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(firmar_manifiesto_modelo, "_ahora", lambda: FECHA)

    firmar_manifiesto_modelo.main(_argumentos(proveedor))

    modelo = resolver_modelo(proveedor / "instalar", publica_de(llave))
    assert modelo.leer_manifiesto()["fecha"] == "2026-11-12T15:00:00+00:00"


def test_un_modelo_alterado_despues_de_firmar_no_pasa_la_verificacion(
    proveedor: Path, llave: RSA.RsaKey
) -> None:
    firmar_manifiesto_modelo.main(_argumentos(proveedor))
    instalado = proveedor / "instalar"
    (instalado / "epp_acme.onnx").write_bytes(PESOS + b" con puerta trasera")

    modelo = resolver_modelo(instalado, publica_de(llave))

    assert verify_model(modelo.ruta, modelo.aprobados) is False


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"--modelo": "no-existe.onnx"}, "no-existe.onnx"),
        ({"--manifiesto": "no-existe.json"}, "no-existe.json"),
        ({"--llave": "no-existe.pem"}, "no-existe.pem"),
        ({"--cliente": "Acme Planta"}, "El cliente es un código corto"),
    ],
    ids=["sin_modelo", "sin_manifiesto", "sin_llave", "cliente_invalido"],
)
def test_sin_lo_necesario_no_se_firma_y_se_explica(
    cambios: dict[str, str], mensaje: str, proveedor: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = firmar_manifiesto_modelo.main(_argumentos(proveedor, **cambios))

    error = capsys.readouterr().err
    assert codigo == CODIGO_DE_RECHAZO
    assert error.startswith("No se firmó el manifiesto: ")
    assert mensaje in error
    assert not (proveedor / "instalar" / "modelo.manifest").exists()


def test_una_llave_cifrada_pide_la_contrasena(
    proveedor: Path, llave: RSA.RsaKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    (proveedor / "privada.pem").write_bytes(llave.export_key(passphrase=CLAVE, pkcs=8))
    preguntas: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda texto: preguntas.append(texto) or CLAVE)

    codigo = firmar_manifiesto_modelo.main(_argumentos(proveedor))

    assert (codigo, preguntas) == (0, ["Contraseña de la llave: "])
    assert resolver_modelo(proveedor / "instalar", publica_de(llave)).motor == "onnx"


def test_una_llave_sin_cifrar_no_pide_contrasena(
    proveedor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preguntas: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda texto: preguntas.append(texto) or CLAVE)

    firmar_manifiesto_modelo.main(_argumentos(proveedor))

    assert preguntas == []


@pytest.mark.integration
def test_el_script_se_ejecuta_como_programa(proveedor: Path) -> None:
    resultado = ejecutar_script("firmar_manifiesto_modelo.py", *_argumentos(proveedor))

    assert resultado.returncode == 0, resultado.stderr
    assert (proveedor / "instalar" / "modelo.manifest").exists()


@pytest.mark.parametrize("opcion", ["--modelo", "--manifiesto", "--llave", "--salida", "--cliente"])
def test_sin_una_opcion_obligatoria_no_se_firma(
    opcion: str, proveedor: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(proveedor)
    posicion = argumentos.index(opcion)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        firmar_manifiesto_modelo.main(argumentos)

    assert salida.value.code == CODIGO_DE_RECHAZO
    assert f"the following arguments are required: {opcion}" in capsys.readouterr().err


def test_la_ayuda_describe_la_herramienta(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "200")

    with pytest.raises(SystemExit):
        firmar_manifiesto_modelo.main(["--help"])

    assert (
        "\n\nFirma el manifiesto de un modelo afinado para un cliente (SPEC/10 F-05). "
        "Solo del proveedor.\n\noptions:"
    ) in capsys.readouterr().out


def test_firmar_de_nuevo_en_una_carpeta_anidada_reemplaza_el_manifiesto(
    proveedor: Path, llave: RSA.RsaKey
) -> None:
    salida = proveedor / "entregas" / "acme" / "modelo.manifest"
    argumentos = _argumentos(proveedor, **{"--salida": str(salida)})

    codigos = [firmar_manifiesto_modelo.main(argumentos) for _ in range(2)]

    assert codigos == [0, 0]
    assert resolver_modelo(salida.parent, publica_de(llave)).motor == "onnx"


def test_un_cliente_invalido_se_explica_completo() -> None:
    with pytest.raises(ModeloNoFirmableError) as error:
        contenido_a_firmar(ENTRADA, "Acme Planta", FECHA)

    assert str(error.value) == (
        "El cliente es un código corto: minúsculas, números y guiones (máximo 40)."
    )
