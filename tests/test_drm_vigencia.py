"""DRM: días restantes, licencia de prueba y reloj atrasado (SPEC/10 §4.2, T-04)."""

from pathlib import Path
from typing import Any

import pytest
from Crypto.PublicKey import RSA

from src.security import drm
from src.security.drm import DRMValidator
from src.security.vigencia_licencia import MotivoDeRechazo
from tests.licencias_firmadas import RelojEn, firmar, generar_llave, publica_de

EMITIDA = 1_800_000_000
DIA = 86_400
HORA = 3_600
VENCE = EMITIDA + 14 * DIA
DIAS_TRAS_DIEZ = 4


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path / "OficinaEficiencia"


@pytest.fixture
def validador(llave: RSA.RsaKey, appdata: Path) -> DRMValidator:
    return DRMValidator(publica_de(llave))


@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch) -> Any:
    def poner(instante: float) -> None:
        monkeypatch.setattr(drm, "datetime", RelojEn(instante))

    poner(EMITIDA)
    return poner


def _prueba(validador: DRMValidator, llave: RSA.RsaKey, **cambios: Any) -> str:
    carga = {
        "hw_id": validador.machine_id,
        "tier": "prueba",
        "emitida": EMITIDA,
        "exp": VENCE,
        "modulos": ["epp"],
    }
    return firmar(llave, {**carga, **cambios})


# --- Días restantes y tipo -------------------------------------------------------------------


def test_sin_licencia_no_hay_dias_restantes_ni_es_prueba(validador: DRMValidator) -> None:
    assert validador.dias_restantes() is None
    assert validador.es_prueba() is False
    assert validador.motivo_de_rechazo is None


def test_una_prueba_emitida_hace_diez_dias_tiene_cuatro_restantes(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.activate_license(_prueba(validador, llave))

    reloj(EMITIDA + 10 * DIA)

    assert validador.dias_restantes() == DIAS_TRAS_DIEZ
    assert validador.es_prueba() is True


def test_una_licencia_comercial_no_es_prueba(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.activate_license(_prueba(validador, llave, tier="comercial"))

    assert validador.es_prueba() is False


# --- Motivo de rechazo -----------------------------------------------------------------------


def test_sin_archivo_de_licencia_el_motivo_es_sin_licencia(validador: DRMValidator) -> None:
    assert validador.validate_license() is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.SIN_LICENCIA


def test_una_licencia_vigente_no_tiene_motivo_de_rechazo(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.validate_license()

    assert validador.activate_license(_prueba(validador, llave)) is True
    assert validador.motivo_de_rechazo is None


def test_una_licencia_vencida_dice_que_vencio(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    reloj(VENCE + 1)

    assert validador.activate_license(_prueba(validador, llave)) is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.VENCIDA


@pytest.mark.parametrize(
    "licencia",
    ["", "   ", "no-es-base64!", "eyJ0ZXN0IjogMX0="],
    ids=["vacia", "espacios", "basura", "sin_firma"],
)
def test_una_llave_ilegible_es_invalida(licencia: str, validador: DRMValidator, reloj: Any) -> None:
    assert validador.activate_license(licencia) is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.INVALIDA


def test_una_licencia_de_otro_equipo_es_invalida(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    assert validador.activate_license(_prueba(validador, llave, hw_id="cd" * 32)) is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.INVALIDA


def test_una_licencia_firmada_con_otra_llave_es_invalida(
    validador: DRMValidator, reloj: Any
) -> None:
    assert validador.activate_license(_prueba(validador, generar_llave())) is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.INVALIDA


def test_un_archivo_de_licencia_ilegible_es_invalido(
    validador: DRMValidator, appdata: Path
) -> None:
    (appdata / "license.key").write_bytes(b"\xff\xfe\x00")

    assert validador.validate_license() is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.INVALIDA


# --- Reloj atrasado --------------------------------------------------------------------------


def test_atrasar_el_reloj_dos_dias_rechaza_la_licencia_por_fecha_incorrecta(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    reloj(EMITIDA + 5 * DIA)
    validador.activate_license(_prueba(validador, llave))

    reloj(EMITIDA + 3 * DIA)

    assert validador.validate_license() is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA


def test_validar_tambien_anota_la_ultima_hora_vista(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.activate_license(_prueba(validador, llave))
    reloj(EMITIDA + 5 * DIA)
    validador.validate_license()

    reloj(EMITIDA + 3 * DIA)

    assert validador.validate_license() is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA


def test_un_ajuste_de_una_hora_hacia_atras_no_bloquea(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    reloj(EMITIDA + 5 * DIA)
    validador.activate_license(_prueba(validador, llave))

    reloj(EMITIDA + 5 * DIA - HORA)

    assert validador.validate_license() is True


def test_una_licencia_rechazada_no_avanza_la_ultima_hora_vista(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    reloj(VENCE + 30 * DIA)
    validador.activate_license(_prueba(validador, llave))

    reloj(EMITIDA)

    assert validador.activate_license(_prueba(validador, llave)) is True


def test_con_el_reloj_atrasado_no_se_activa_ni_se_guarda_otra_licencia(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any, appdata: Path
) -> None:
    reloj(EMITIDA + 5 * DIA)
    primera = _prueba(validador, llave)
    validador.activate_license(primera)
    reloj(EMITIDA + 3 * DIA)

    activada = validador.activate_license(_prueba(validador, llave, tier="comercial"))

    assert activada is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA
    assert (appdata / "license.key").read_text(encoding="utf-8") == primera


def test_un_reloj_anterior_a_la_emision_rechaza_la_licencia(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    reloj(EMITIDA - 2 * DIA)

    assert validador.activate_license(_prueba(validador, llave)) is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA


def test_un_registro_de_reloj_alterado_rechaza_la_licencia(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any, appdata: Path
) -> None:
    validador.activate_license(_prueba(validador, llave))
    (appdata / "reloj.sig").write_text(f"{EMITIDA - DIA}:{'0' * 64}", encoding="utf-8")

    assert validador.validate_license() is False
    assert validador.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA


# --- Revalidación ----------------------------------------------------------------------------


def test_al_dejar_de_regir_la_licencia_deja_de_habilitar_modulos(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.activate_license(_prueba(validador, llave))
    habilitado_antes = validador.incluye_modulo("epp")
    reloj(VENCE + 1)

    vigente = validador.validate_license()

    assert (habilitado_antes, vigente) == (True, False)
    assert validador.incluye_modulo("epp") is False
    assert validador.license_data is None
    assert validador.motivo_de_rechazo is MotivoDeRechazo.VENCIDA


def test_si_se_borra_el_archivo_de_licencia_deja_de_habilitar_modulos(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any, appdata: Path
) -> None:
    validador.activate_license(_prueba(validador, llave))
    (appdata / "license.key").unlink()

    assert validador.validate_license() is False
    assert validador.license_data is None
    assert validador.motivo_de_rechazo is MotivoDeRechazo.SIN_LICENCIA


def test_una_activacion_fallida_no_borra_la_licencia_que_ya_regia(
    validador: DRMValidator, llave: RSA.RsaKey, reloj: Any
) -> None:
    validador.activate_license(_prueba(validador, llave))

    assert validador.activate_license("basura") is False
    assert validador.incluye_modulo("epp") is True


def test_un_vencimiento_fuera_del_calendario_no_tiene_fecha_que_mostrar(
    validador: DRMValidator,
) -> None:
    validador.license_data = {"exp": 10**18}

    assert validador.get_expiration_date() is None
