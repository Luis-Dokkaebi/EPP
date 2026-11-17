"""Emisor de licencias del proveedor (SPEC/10 §4, T-03, AC-T01 y AC-T02)."""

import base64
import csv
import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from scripts import keygen_b2b
from scripts.keygen_b2b import (
    Pedido,
    PedidoInvalidoError,
    PruebaRepetidaError,
    RegistroDeEmisiones,
    contenido_de_la_licencia,
    emitir_licencia,
    pedido_del_tier,
)
from tests.licencias_firmadas import SEPARADOR, generar_llave

HW_ID = "ab" * 32
OTRO_HW_ID = "cd" * 32
EMITIDA = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
EPOCH_EMITIDA = 1794495600
SEGUNDOS_POR_DIA = 86400
IDENTIFICADOR = "0b0e6a3e-8a4f-4b6a-9d55-7c1d2f3a4b5c"
DIAS_DE_PRUEBA = 14
DIAS_DE_APRENDIZAJE = 7
DIAS_COMERCIALES = 365
CAMARAS_POR_OMISION = 4
CAMARAS_PEDIDAS = 8
DIAS_PEDIDOS = 30


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def registro(tmp_path: Path) -> RegistroDeEmisiones:
    return RegistroDeEmisiones(tmp_path / "emisiones.csv")


def _pedido(tier: str = "prueba", hw_id: str = HW_ID) -> Pedido:
    return pedido_del_tier(hw_id, "acme-planta1", tier)


def _abrir(licencia: str, llave: RSA.RsaKey) -> dict[str, Any]:
    """Verifica la firma con la llave pública y devuelve el contenido firmado."""
    carga, firma = base64.b64decode(licencia).split(SEPARADOR, 1)
    pkcs1_15.new(llave.public_key()).verify(SHA256.new(carga), firma)
    contenido: dict[str, Any] = json.loads(carga)
    return contenido


def _filas(registro: RegistroDeEmisiones) -> list[dict[str, str]]:
    with registro.ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


# --- Contenido firmado (AC-T01) --------------------------------------------------------------


def test_la_licencia_de_prueba_lleva_todos_los_campos_firmados(
    llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    licencia = emitir_licencia(_pedido(), llave, registro, EMITIDA, IDENTIFICADOR)

    assert _abrir(licencia, llave) == {
        "id": IDENTIFICADOR,
        "cliente": "acme-planta1",
        "hw_id": HW_ID,
        "tier": "prueba",
        "emitida": EPOCH_EMITIDA,
        "exp": EPOCH_EMITIDA + DIAS_DE_PRUEBA * SEGUNDOS_POR_DIA,
        "max_cams": CAMARAS_POR_OMISION,
        "modulos": ["epp"],
    }


@pytest.mark.parametrize(
    ("tier", "dias", "modulos"),
    [
        ("aprendizaje", DIAS_DE_APRENDIZAJE, ()),
        ("prueba", DIAS_DE_PRUEBA, ("epp",)),
        ("comercial", DIAS_COMERCIALES, ("epp",)),
    ],
)
def test_cada_tier_trae_sus_dias_y_modulos_por_omision(
    tier: str, dias: int, modulos: tuple[str, ...]
) -> None:
    pedido = _pedido(tier)

    assert (pedido.dias, pedido.modulos, pedido.camaras) == (dias, modulos, CAMARAS_POR_OMISION)


def test_el_contenido_respeta_dias_camaras_y_modulos_pedidos() -> None:
    pedido = Pedido(
        HW_ID, "acme-planta1", "comercial", DIAS_PEDIDOS, CAMARAS_PEDIDAS, ("epp", "eficiencia")
    )

    contenido = contenido_de_la_licencia(pedido, EMITIDA, IDENTIFICADOR)

    assert contenido["exp"] == EPOCH_EMITIDA + DIAS_PEDIDOS * SEGUNDOS_POR_DIA
    assert contenido["max_cams"] == CAMARAS_PEDIDAS
    assert contenido["modulos"] == ["epp", "eficiencia"]


# --- Pedidos inválidos -----------------------------------------------------------------------


MENSAJE_MACHINE_ID = "El Machine ID son 64 caracteres hex."
MENSAJE_CLIENTE = "El cliente es un código corto: minúsculas, números y guiones (máximo 40)."
MENSAJE_TIER = "El tier 'enterprise' no existe: usa aprendizaje, prueba, comercial."
MENSAJE_DIAS = "Los días van de 1 a 3650."
MENSAJE_CAMARAS = "Las cámaras van de 1 a 64."


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"hw_id": "AB" * 32}, MENSAJE_MACHINE_ID),
        ({"hw_id": "ab" * 31}, MENSAJE_MACHINE_ID),
        ({"hw_id": "ab" * 32 + "0"}, MENSAJE_MACHINE_ID),
        ({"hw_id": "zz" * 32}, MENSAJE_MACHINE_ID),
        ({"cliente": ""}, MENSAJE_CLIENTE),
        ({"cliente": "Acme Planta"}, MENSAJE_CLIENTE),
        ({"cliente": "-acme"}, MENSAJE_CLIENTE),
        ({"cliente": "a" * 41}, MENSAJE_CLIENTE),
        ({"tier": "enterprise"}, MENSAJE_TIER),
        ({"dias": 0}, MENSAJE_DIAS),
        ({"dias": 3651}, MENSAJE_DIAS),
        ({"camaras": 0}, MENSAJE_CAMARAS),
        ({"camaras": 65}, MENSAJE_CAMARAS),
        ({"modulos": ("zeta", "epp", "nomina")}, "Módulos desconocidos: nomina, zeta."),
        ({"dias": 0, "camaras": 0}, f"{MENSAJE_DIAS} {MENSAJE_CAMARAS}"),
    ],
)
def test_un_pedido_invalido_no_se_emite(
    cambios: dict[str, Any], mensaje: str, llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    campos = {
        "hw_id": HW_ID,
        "cliente": "acme-planta1",
        "tier": "prueba",
        "dias": DIAS_DE_PRUEBA,
        "camaras": CAMARAS_POR_OMISION,
        "modulos": ("epp",),
    }
    pedido = Pedido(**{**campos, **cambios})

    with pytest.raises(PedidoInvalidoError) as error:
        emitir_licencia(pedido, llave, registro, EMITIDA, IDENTIFICADOR)

    assert str(error.value) == mensaje
    assert not registro.ruta.exists()


@pytest.mark.parametrize(
    "pedido",
    [
        Pedido(HW_ID, "a", "prueba", 1, 1, ()),
        Pedido(HW_ID, "a" * 40, "prueba", 3650, 64, ("eficiencia",)),
    ],
    ids=["minimos", "maximos"],
)
def test_los_limites_del_pedido_son_validos(
    pedido: Pedido, llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    licencia = emitir_licencia(pedido, llave, registro, EMITIDA, IDENTIFICADOR)

    assert _abrir(licencia, llave)["max_cams"] == pedido.camaras


def test_un_tier_desconocido_no_tiene_valores_por_omision() -> None:
    with pytest.raises(PedidoInvalidoError) as error:
        pedido_del_tier(HW_ID, "acme", "enterprise")

    assert str(error.value) == MENSAJE_TIER


@pytest.mark.parametrize("campo", ["dias", "modulos"])
def test_un_pedido_no_se_puede_alterar_despues_de_creado(campo: str) -> None:
    pedido = _pedido()

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(pedido, campo, DIAS_COMERCIALES)


# --- Registro de emisiones y una prueba por equipo (AC-T02) ----------------------------------


def test_cada_emision_queda_en_el_registro(
    llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    emitir_licencia(_pedido("aprendizaje"), llave, registro, EMITIDA, IDENTIFICADOR)
    emitir_licencia(_pedido("prueba"), llave, registro, EMITIDA, "otro-id")

    assert _filas(registro) == [
        {
            "id": IDENTIFICADOR,
            "cliente": "acme-planta1",
            "hw_id": HW_ID,
            "tier": "aprendizaje",
            "emitida": "2026-11-12T15:00:00+00:00",
            "vence": "2026-11-19T15:00:00+00:00",
            "camaras": "4",
            "modulos": "",
        },
        {
            "id": "otro-id",
            "cliente": "acme-planta1",
            "hw_id": HW_ID,
            "tier": "prueba",
            "emitida": "2026-11-12T15:00:00+00:00",
            "vence": "2026-11-26T15:00:00+00:00",
            "camaras": "4",
            "modulos": "epp",
        },
    ]


def test_el_registro_crea_su_carpeta_si_falta(llave: RSA.RsaKey, tmp_path: Path) -> None:
    registro = RegistroDeEmisiones(tmp_path / "boveda" / "2026" / "emisiones.csv")

    emitir_licencia(_pedido(), llave, registro, EMITIDA, IDENTIFICADOR)

    assert len(_filas(registro)) == 1


def test_no_se_emite_una_segunda_prueba_para_el_mismo_equipo(
    llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    emitir_licencia(_pedido(), llave, registro, EMITIDA, IDENTIFICADOR)

    with pytest.raises(PruebaRepetidaError) as error:
        emitir_licencia(_pedido(), llave, registro, EMITIDA, "segundo-intento")

    assert str(error.value) == (
        "El equipo abababababab... ya recibió una licencia de prueba (SPEC/10 §4.2)."
    )

    assert [fila["id"] for fila in _filas(registro)] == [IDENTIFICADOR]


def test_otro_equipo_si_recibe_su_prueba(llave: RSA.RsaKey, registro: RegistroDeEmisiones) -> None:
    emitir_licencia(_pedido(), llave, registro, EMITIDA, IDENTIFICADOR)

    emitir_licencia(_pedido(hw_id=OTRO_HW_ID), llave, registro, EMITIDA, "otro-id")

    assert [fila["hw_id"] for fila in _filas(registro)] == [HW_ID, OTRO_HW_ID]


@pytest.mark.parametrize("tier", ["aprendizaje", "comercial"])
def test_tras_la_prueba_el_mismo_equipo_recibe_otros_tiers(
    tier: str, llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    emitir_licencia(_pedido(), llave, registro, EMITIDA, IDENTIFICADOR)

    emitir_licencia(_pedido(tier), llave, registro, EMITIDA, "otro-id")

    assert [fila["tier"] for fila in _filas(registro)] == ["prueba", tier]


def test_las_licencias_comerciales_se_pueden_renovar(
    llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    emitir_licencia(_pedido("comercial"), llave, registro, EMITIDA, IDENTIFICADOR)

    emitir_licencia(_pedido("comercial"), llave, registro, EMITIDA, "renovacion")

    assert [fila["id"] for fila in _filas(registro)] == [IDENTIFICADOR, "renovacion"]


def test_el_registro_no_puede_vivir_dentro_del_repositorio() -> None:
    dentro = Path(keygen_b2b.__file__).resolve().parents[1] / "emisiones.csv"

    with pytest.raises(PedidoInvalidoError) as error:
        RegistroDeEmisiones(dentro)

    assert str(error.value) == (
        f"El registro de emisiones debe vivir fuera del repositorio, no en {dentro}."
    )


def test_el_registro_puede_vivir_junto_al_repositorio() -> None:
    junto = Path(keygen_b2b.__file__).resolve().parents[2] / "emisiones.csv"

    assert RegistroDeEmisiones(junto).ruta == junto


def test_el_registro_anota_varios_modulos_separados_por_coma(
    llave: RSA.RsaKey, registro: RegistroDeEmisiones
) -> None:
    pedido = Pedido(
        HW_ID, "acme", "comercial", DIAS_PEDIDOS, CAMARAS_PEDIDAS, ("epp", "eficiencia")
    )

    emitir_licencia(pedido, llave, registro, EMITIDA, IDENTIFICADOR)

    assert _filas(registro)[0]["modulos"] == "epp,eficiencia"
