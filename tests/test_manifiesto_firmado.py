"""Manifiesto de modelo firmado (SPEC/10 F-05, T-07, AC-T05): falla cerrado sin firma válida."""

import base64
from pathlib import Path
from typing import Any

import pytest
from Crypto.PublicKey import RSA

from src.models.manifiesto_firmado import (
    ManifiestoFirmadoInvalidoError,
    entrada_del_manifiesto,
    leer_manifiesto_firmado,
)
from tests.licencias_firmadas import SEPARADOR, firmar, generar_llave, publica_de

SHA = "ab" * 32
ENTRADA: dict[str, Any] = {
    "nombre": "epp-acme",
    "version": "0.1-acme",
    "archivo": "epp_acme.onnx",
    "sha256": SHA,
    "motor": "onnx",
    "clases": {"0": "persona", "1": "cabeza", "2": "casco", "3": "chaleco"},
    "media": [0.485, 0.456, 0.406],
    "desviacion": [0.229, 0.224, 0.225],
}
MANIFIESTO: dict[str, Any] = {
    "version_esquema": 1,
    "cliente": "acme-planta1",
    "fecha": "2026-11-12T15:00:00+00:00",
    "modelos": [ENTRADA],
}


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


def _guardar(carpeta: Path, contenido: str) -> Path:
    ruta = carpeta / "modelo.manifest"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def _con(**cambios: Any) -> dict[str, Any]:
    return {**MANIFIESTO, "modelos": [{**ENTRADA, **cambios}]}


def test_un_manifiesto_firmado_por_el_proveedor_se_lee_completo(
    llave: RSA.RsaKey, tmp_path: Path
) -> None:
    ruta = _guardar(tmp_path, f"  {firmar(llave, MANIFIESTO)}\n")

    manifiesto = leer_manifiesto_firmado(ruta, publica_de(llave))

    assert manifiesto == MANIFIESTO
    assert entrada_del_manifiesto(manifiesto) == ENTRADA


def test_un_manifiesto_firmado_con_otra_llave_se_rechaza(llave: RSA.RsaKey, tmp_path: Path) -> None:
    ruta = _guardar(tmp_path, firmar(generar_llave(), MANIFIESTO))

    with pytest.raises(ManifiestoFirmadoInvalidoError) as error:
        leer_manifiesto_firmado(ruta, publica_de(llave))

    assert str(error.value) == f"{ruta}: la firma no es del proveedor."


def test_un_manifiesto_alterado_despues_de_firmar_se_rechaza(
    llave: RSA.RsaKey, tmp_path: Path
) -> None:
    carga, firma = base64.b64decode(firmar(llave, MANIFIESTO)).split(SEPARADOR, 1)
    alterada = carga.replace(SHA.encode(), ("cd" * 32).encode())
    ruta = _guardar(tmp_path, base64.b64encode(alterada + SEPARADOR + firma).decode("ascii"))

    with pytest.raises(ManifiestoFirmadoInvalidoError, match="la firma no es del proveedor"):
        leer_manifiesto_firmado(ruta, publica_de(llave))


@pytest.mark.parametrize(
    "contenido",
    ["", "no-es-base64!", base64.b64encode(b'{"modelos": []}').decode("ascii")],
    ids=["vacio", "basura", "sin_firma"],
)
def test_un_archivo_sin_firma_se_rechaza(contenido: str, llave: RSA.RsaKey, tmp_path: Path) -> None:
    ruta = _guardar(tmp_path, contenido)

    with pytest.raises(ManifiestoFirmadoInvalidoError) as error:
        leer_manifiesto_firmado(ruta, publica_de(llave))

    assert str(error.value) == f"{ruta}: no es un manifiesto firmado."


def test_un_archivo_binario_se_rechaza(llave: RSA.RsaKey, tmp_path: Path) -> None:
    ruta = tmp_path / "modelo.manifest"
    ruta.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(ManifiestoFirmadoInvalidoError, match="no es un manifiesto firmado"):
        leer_manifiesto_firmado(ruta, publica_de(llave))


@pytest.mark.parametrize(
    ("manifiesto", "problema"),
    [
        ({**MANIFIESTO, "modelos": []}, "debe declarar exactamente un modelo."),
        ({**MANIFIESTO, "modelos": [ENTRADA, ENTRADA]}, "debe declarar exactamente un modelo."),
        ({"cliente": "acme"}, "debe declarar exactamente un modelo."),
        (_con(motor="ultralytics"), "el motor debe ser onnx."),
        (_con(archivo="../epp.onnx"), "el archivo del modelo debe ser un nombre sin carpetas."),
        (
            _con(archivo="modelos/epp.onnx"),
            "el archivo del modelo debe ser un nombre sin carpetas.",
        ),
        (_con(archivo=""), "el archivo del modelo debe ser un nombre sin carpetas."),
        (_con(archivo=".."), "el archivo del modelo debe ser un nombre sin carpetas."),
        (_con(archivo="."), "el archivo del modelo debe ser un nombre sin carpetas."),
        (_con(archivo="..\\epp.onnx"), "el archivo del modelo debe ser un nombre sin carpetas."),
        (_con(archivo="C:epp.onnx"), "el archivo del modelo debe ser un nombre sin carpetas."),
        (
            {**MANIFIESTO, "modelos": [{k: v for k, v in ENTRADA.items() if k != "sha256"}]},
            "al modelo le falta sha256.",
        ),
        (
            {**MANIFIESTO, "modelos": [{k: v for k, v in ENTRADA.items() if k != "clases"}]},
            "al modelo le falta clases.",
        ),
    ],
    ids=[
        "sin_modelos",
        "dos_modelos",
        "sin_lista",
        "otro_motor",
        "ruta_hacia_arriba",
        "con_carpeta",
        "archivo_vacio",
        "carpeta_de_arriba",
        "carpeta_actual",
        "ruta_de_windows",
        "unidad_de_windows",
        "sin_sha256",
        "sin_clases",
    ],
)
def test_un_manifiesto_firmado_pero_mal_formado_se_rechaza(
    manifiesto: dict[str, Any], problema: str, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    ruta = _guardar(tmp_path, firmar(llave, manifiesto))

    with pytest.raises(ManifiestoFirmadoInvalidoError) as error:
        leer_manifiesto_firmado(ruta, publica_de(llave))

    assert str(error.value) == f"{ruta}: {problema}"


@pytest.mark.parametrize("campo", ["version", "media", "desviacion", "archivo", "motor"])
def test_cada_campo_obligatorio_del_modelo_se_exige(
    campo: str, llave: RSA.RsaKey, tmp_path: Path
) -> None:
    entrada = {k: v for k, v in ENTRADA.items() if k != campo}
    ruta = _guardar(tmp_path, firmar(llave, {**MANIFIESTO, "modelos": [entrada]}))

    with pytest.raises(ManifiestoFirmadoInvalidoError) as error:
        leer_manifiesto_firmado(ruta, publica_de(llave))

    assert str(error.value) == f"{ruta}: al modelo le falta {campo}."
