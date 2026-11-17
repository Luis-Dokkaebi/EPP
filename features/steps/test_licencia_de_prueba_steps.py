"""Pasos de features/licencia_de_prueba.feature: traducen el texto y llaman a la simulación."""

from datetime import timedelta
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.security.vigencia_licencia import MotivoDeRechazo
from tests.simulacion_licencia_de_prueba import HOY, LO_APRENDIDO, EquipoDelCliente

pytestmark = pytest.mark.bdd

scenarios("../licencia_de_prueba.feature")

DIAS_DE_PRUEBA = 14
EMPLEADOS = ["Ana", "Luis"]


@pytest.fixture
def equipo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EquipoDelCliente:
    return EquipoDelCliente(tmp_path, monkeypatch)


@given(
    parsers.parse(
        "una licencia de prueba de {duracion:d} días emitida hace {dias:d} días para este equipo"
    )
)
def prueba_emitida_hace(equipo: EquipoDelCliente, duracion: int, dias: int) -> None:
    equipo.instalar(equipo.emitir("prueba", HOY - timedelta(days=dias), duracion))


@given("una licencia de aprendizaje emitida hoy para este equipo")
def aprendizaje_emitida_hoy(equipo: EquipoDelCliente) -> None:
    equipo.instalar(equipo.emitir("aprendizaje", HOY))


@given("una licencia de prueba que vence en 30 minutos")
def prueba_por_vencer(equipo: EquipoDelCliente) -> None:
    emitida = HOY - timedelta(days=DIAS_DE_PRUEBA) + timedelta(minutes=30)
    equipo.instalar(equipo.emitir("prueba", emitida))


@given("una licencia de prueba vigente")
def prueba_vigente(equipo: EquipoDelCliente) -> None:
    equipo.instalar(equipo.emitir("prueba", HOY - timedelta(days=5)))


@given("una licencia de prueba vencida")
def prueba_vencida(equipo: EquipoDelCliente) -> None:
    equipo.instalar(equipo.emitir("prueba", HOY - timedelta(days=DIAS_DE_PRUEBA + 1)))


@given("una licencia de prueba emitida para otro equipo", target_fixture="licencia_ajena")
def prueba_de_otro_equipo(equipo: EquipoDelCliente) -> str:
    return equipo.emitir_para_otro_equipo()


@given("que este equipo ya recibió su licencia de prueba")
def prueba_ya_recibida(equipo: EquipoDelCliente) -> None:
    equipo.emitir("prueba", HOY - timedelta(days=30))


@given("la aplicación está vigilando cámaras")
def app_vigilando(equipo: EquipoDelCliente) -> None:
    assert equipo.abrir() is True
    equipo.guardar_lo_aprendido()


@given("la aplicación ya funcionó hoy")
def app_ya_funciono(equipo: EquipoDelCliente) -> None:
    assert equipo.abrir() is True


@given("empleados registrados durante la prueba")
def empleados_registrados(equipo: EquipoDelCliente) -> None:
    for nombre in EMPLEADOS:
        equipo.registrar_empleado(nombre)


@when("abro la aplicación")
def abrir(equipo: EquipoDelCliente) -> None:
    equipo.abrir()


@when("pasa una hora")
def pasa_una_hora(equipo: EquipoDelCliente) -> None:
    equipo.adelantar(timedelta(hours=1))
    equipo.revalidar()


@when("la fecha del equipo se atrasa dos días")
def atrasar_el_reloj(equipo: EquipoDelCliente) -> None:
    equipo.adelantar(-timedelta(days=2))
    equipo.abrir()


@when("activo una licencia comercial para este equipo")
def activar_comercial(equipo: EquipoDelCliente) -> None:
    equipo.activar(equipo.emitir("comercial", HOY))


@when("intento activarla")
def activar_ajena(equipo: EquipoDelCliente, licencia_ajena: str) -> None:
    equipo.activar(licencia_ajena)


@when("el proveedor intenta emitirle otra licencia de prueba")
def emitir_otra_prueba(equipo: EquipoDelCliente) -> None:
    equipo.intentar_otra_prueba()


@then("el módulo EPP está activo")
def epp_activo(equipo: EquipoDelCliente) -> None:
    assert equipo.licencia.incluye_modulo("epp") is True


@then("el módulo EPP no está activo")
def epp_inactivo(equipo: EquipoDelCliente) -> None:
    assert equipo.licencia.license_data is not None
    assert equipo.licencia.incluye_modulo("epp") is False


@then(parsers.parse('veo el aviso "{texto}"'))
def veo_el_aviso(equipo: EquipoDelCliente, texto: str) -> None:
    assert equipo.aviso() == texto


@then("no veo ningún aviso de prueba")
def sin_aviso(equipo: EquipoDelCliente) -> None:
    assert equipo.aviso() is None


@then("la vigilancia se detiene")
def vigilancia_detenida(equipo: EquipoDelCliente) -> None:
    assert equipo.app.vigilando is False
    assert equipo.licencia.motivo_de_rechazo is MotivoDeRechazo.VENCIDA


@then("se pide una licencia para continuar")
def se_pide_licencia(equipo: EquipoDelCliente) -> None:
    assert equipo.app.pidio_licencia is True


@then("los rostros, zonas e historial se conservan")
def lo_aprendido_se_conserva(equipo: EquipoDelCliente) -> None:
    assert equipo.lo_aprendido() == {
        relativo: f"contenido de {relativo}" for relativo in LO_APRENDIDO
    }


@then("la licencia se rechaza por fecha incorrecta")
def rechazo_por_fecha(equipo: EquipoDelCliente) -> None:
    assert equipo.licencia.motivo_de_rechazo is MotivoDeRechazo.FECHA_INCORRECTA
    assert equipo.licencia.incluye_modulo("epp") is False


@then("los empleados registrados siguen reconociéndose")
def empleados_siguen(equipo: EquipoDelCliente) -> None:
    assert equipo.ultima_activacion is True
    assert equipo.licencia.get_tier() == "comercial"
    assert equipo.empleados_reconocibles() == EMPLEADOS


@then("la activación se rechaza")
def activacion_rechazada(equipo: EquipoDelCliente) -> None:
    assert equipo.ultima_activacion is False
    assert equipo.licencia.motivo_de_rechazo is MotivoDeRechazo.INVALIDA


@then("la emisión se rechaza")
def emision_rechazada(equipo: EquipoDelCliente) -> None:
    assert equipo.emision_rechazada is True
