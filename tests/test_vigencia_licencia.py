"""Vigencia de una licencia ya verificada (SPEC/10 §4.2 y T-04): vencimiento y reloj atrasado."""

import hashlib
import hmac
from pathlib import Path

import pytest

from src.security.vigencia_licencia import (
    MotivoDeRechazo,
    RegistroDeRelojAlteradoError,
    UltimaHoraVista,
    dias_restantes,
    es_de_prueba,
    motivo_de_rechazo_por_fecha,
)

EMITIDA = 1_800_000_000
DIA = 86_400
HORA = 3_600
VENCE = EMITIDA + 14 * DIA
LICENCIA = {"emitida": EMITIDA, "exp": VENCE, "tier": "prueba"}
MACHINE_ID = "ab" * 32
MEDIO_SEGUNDO = 0.5


@pytest.fixture
def ultima(tmp_path: Path) -> UltimaHoraVista:
    return UltimaHoraVista(tmp_path / "reloj.sig", MACHINE_ID)


# --- Motivo de rechazo por fecha -------------------------------------------------------------


@pytest.mark.parametrize(
    ("ahora", "ultima_vista", "motivo"),
    [
        (EMITIDA, None, None),
        (VENCE, None, None),
        (VENCE + 1, None, MotivoDeRechazo.VENCIDA),
        (EMITIDA - HORA, None, None),
        (EMITIDA - HORA - 1, None, MotivoDeRechazo.FECHA_INCORRECTA),
        (EMITIDA + DIA, EMITIDA + DIA + HORA, None),
        (EMITIDA + DIA, EMITIDA + DIA + HORA + 1, MotivoDeRechazo.FECHA_INCORRECTA),
        (EMITIDA + DIA, EMITIDA, None),
        (VENCE + 1, VENCE + 3 * DIA, MotivoDeRechazo.VENCIDA),
    ],
    ids=[
        "recien_emitida",
        "ultimo_segundo",
        "vencida",
        "reloj_una_hora_antes_de_la_emision",
        "reloj_anterior_a_la_emision",
        "una_hora_antes_de_la_ultima_vista",
        "reloj_atrasado",
        "reloj_adelante_de_la_ultima_vista",
        "vencida_aunque_el_reloj_este_atrasado",
    ],
)
def test_motivo_de_rechazo_por_fecha(
    ahora: float, ultima_vista: float | None, motivo: MotivoDeRechazo | None
) -> None:
    assert motivo_de_rechazo_por_fecha(LICENCIA, ahora, ultima_vista) is motivo


def test_una_licencia_sin_vencimiento_declarado_esta_vencida() -> None:
    assert motivo_de_rechazo_por_fecha({}, 1, None) is MotivoDeRechazo.VENCIDA


@pytest.mark.parametrize(
    ("ahora", "motivo"),
    [(-HORA, None), (-HORA - 1, MotivoDeRechazo.FECHA_INCORRECTA)],
    ids=["en_el_limite", "antes_del_limite"],
)
def test_sin_fecha_de_emision_ni_hora_vista_el_piso_es_el_origen_del_tiempo(
    ahora: float, motivo: MotivoDeRechazo | None
) -> None:
    assert motivo_de_rechazo_por_fecha({"exp": VENCE}, ahora, None) is motivo


def test_cada_motivo_tiene_su_mensaje_para_el_usuario() -> None:
    assert {motivo.name: motivo.value for motivo in MotivoDeRechazo} == {
        "SIN_LICENCIA": "No hay una licencia activada en este equipo.",
        "INVALIDA": "La llave no es válida, está dañada o no corresponde a este equipo.",
        "VENCIDA": "La licencia venció. Contrate para continuar: lo aprendido se conserva.",
        "FECHA_INCORRECTA": "La fecha del equipo no es correcta.",
    }


# --- Días restantes y tipo -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ahora", "dias"),
    [
        (EMITIDA - 1, 15),
        (EMITIDA, 14),
        (EMITIDA + 1, 14),
        (EMITIDA + DIA, 13),
        (EMITIDA + 10 * DIA, 4),
        (VENCE - DIA, 1),
        (VENCE - 1, 1),
        (VENCE, 0),
        (VENCE + 5 * DIA, 0),
    ],
)
def test_dias_restantes_cuenta_los_dias_empezados(ahora: float, dias: int) -> None:
    assert dias_restantes(LICENCIA, ahora) == dias


def test_dias_restantes_sin_vencimiento_declarado_es_cero() -> None:
    assert dias_restantes({}, EMITIDA) == 0


def test_sin_vencimiento_declarado_los_dias_se_cuentan_desde_el_origen_del_tiempo() -> None:
    assert dias_restantes({}, -DIA) == 1


@pytest.mark.parametrize(
    ("datos", "prueba"),
    [({"tier": "prueba"}, True), ({"tier": "comercial"}, False), ({}, False)],
)
def test_solo_el_tier_prueba_es_de_prueba(datos: dict[str, object], prueba: bool) -> None:
    assert es_de_prueba(datos) is prueba


# --- Última hora vista -----------------------------------------------------------------------


def test_sin_registro_no_hay_ultima_hora_vista(ultima: UltimaHoraVista) -> None:
    assert ultima.leer() is None


def test_la_hora_anotada_se_vuelve_a_leer(ultima: UltimaHoraVista, tmp_path: Path) -> None:
    ultima.anotar(EMITIDA + 0.5)

    assert UltimaHoraVista(tmp_path / "reloj.sig", MACHINE_ID).leer() == EMITIDA + 0.5


def test_la_primera_hora_anotada_puede_ser_menor_que_un_segundo(ultima: UltimaHoraVista) -> None:
    ultima.anotar(MEDIO_SEGUNDO)

    assert ultima.leer() == MEDIO_SEGUNDO


def test_el_registro_guarda_la_hora_y_su_hmac_con_la_sal_v1(
    ultima: UltimaHoraVista, tmp_path: Path
) -> None:
    clave = hashlib.sha256(MACHINE_ID.encode("utf-8") + b"_oe_reloj_licencia_v1").digest()
    firma = hmac.new(clave, b"1800000000.0", hashlib.sha256).hexdigest()

    ultima.anotar(EMITIDA)

    assert (tmp_path / "reloj.sig").read_bytes() == b"1800000000.0:" + firma.encode("ascii")


def test_anotar_una_hora_anterior_conserva_la_mas_reciente(ultima: UltimaHoraVista) -> None:
    ultima.anotar(EMITIDA + DIA)

    ultima.anotar(EMITIDA)

    assert ultima.leer() == EMITIDA + DIA


def test_anotar_una_hora_posterior_avanza_el_registro(ultima: UltimaHoraVista) -> None:
    ultima.anotar(EMITIDA)

    ultima.anotar(EMITIDA + DIA)

    assert ultima.leer() == EMITIDA + DIA


def test_el_registro_crea_su_carpeta(tmp_path: Path) -> None:
    ultima = UltimaHoraVista(tmp_path / "nueva" / "carpeta" / "reloj.sig", MACHINE_ID)

    ultima.anotar(EMITIDA)

    assert ultima.leer() == EMITIDA


@pytest.mark.parametrize(
    "contenido",
    [
        f"{EMITIDA - DIA}:{'0' * 64}".encode(),
        f"{EMITIDA}".encode(),
        b"",
        b"no-es-un-registro",
        b"abc:def",
        "1:ñandú".encode(),
        b"\xff\xfe:\x00",
    ],
    ids=["hora_editada", "sin_firma", "vacio", "basura", "hora_ilegible", "acentos", "binario"],
)
def test_un_registro_alterado_se_detecta(
    contenido: bytes, ultima: UltimaHoraVista, tmp_path: Path
) -> None:
    ultima.anotar(EMITIDA)
    (tmp_path / "reloj.sig").write_bytes(contenido)

    with pytest.raises(RegistroDeRelojAlteradoError) as error:
        ultima.leer()

    assert str(error.value) == f"{tmp_path / 'reloj.sig'} no lleva la firma de este equipo."


def test_cambiar_la_hora_conservando_la_firma_se_detecta(
    ultima: UltimaHoraVista, tmp_path: Path
) -> None:
    ultima.anotar(EMITIDA + DIA)
    _, firma = (tmp_path / "reloj.sig").read_text(encoding="utf-8").split(":")
    (tmp_path / "reloj.sig").write_text(f"{float(EMITIDA)!r}:{firma}", encoding="utf-8")

    with pytest.raises(RegistroDeRelojAlteradoError):
        ultima.leer()


def test_el_registro_de_otro_equipo_no_vale(ultima: UltimaHoraVista, tmp_path: Path) -> None:
    ultima.anotar(EMITIDA)

    with pytest.raises(RegistroDeRelojAlteradoError):
        UltimaHoraVista(tmp_path / "reloj.sig", "cd" * 32).leer()


def test_un_registro_alterado_no_se_puede_sobrescribir_anotando(
    ultima: UltimaHoraVista, tmp_path: Path
) -> None:
    (tmp_path / "reloj.sig").write_text("basura", encoding="utf-8")

    with pytest.raises(RegistroDeRelojAlteradoError):
        ultima.anotar(EMITIDA)

    assert (tmp_path / "reloj.sig").read_text(encoding="utf-8") == "basura"
