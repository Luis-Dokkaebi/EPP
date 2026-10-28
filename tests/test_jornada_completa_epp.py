"""Recorrido de punta a punta del módulo de EPP, como lo usa quien compra el producto (SPEC/9 §16).

Cada prueba recorre la cadena completa que arma la aplicación: polígono de la zona, casillas de
EPP exigido, cámara, caso de uso con los parámetros decididos (D4: 4 s de confirmación y 10 min
de enfriamiento; D5: 30 días de retención), base del tenant, evidencia, aviso por webhook, panel
"Alertas EPP" y reporte Excel. Verifica en conjunto AC-011 a AC-016 y AC-019, que el resto de la
suite prueba pieza por pieza. Ver tests/simulacion_jornada_epp.py.
"""

import json
from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path

import pytest

from src.ppe.domain.elementos import ElementoEPP
from tests.servidores_falsos import ServidorWebhookFalso
from tests.simulacion_jornada_epp import (
    BOCA_DE_POZO,
    FUERA_DE_TODA_ZONA,
    INICIO_DEL_TURNO,
    POLIGONO_BOCA_DE_POZO,
    SUPERVISOR,
    SucursalSimulada,
    operario,
)

CASCO, CHALECO = ElementoEPP.CASCO, ElementoEPP.CHALECO
CONFIRMACION = timedelta(seconds=4)  # D4
CASI_CONFIRMACION = timedelta(seconds=3)
DIEZ_MINUTOS = timedelta(minutes=10)
PRIMER_REINTENTO = timedelta(seconds=30)
RETENCION_DIAS = 30  # D5


@pytest.fixture(autouse=True)
def sin_proxy_hacia_la_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    """El tráfico al webhook falso en 127.0.0.1 nunca pasa por un proxy del entorno."""
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")


@pytest.fixture
def sucursal(tmp_path: Path) -> SucursalSimulada:
    """Sucursal con la zona "Boca de pozo" dibujada y el casco exigido, cámara conectada."""
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)
    sucursal.exigir(BOCA_DE_POZO, CASCO)
    sucursal.conectar_camara()
    return sucursal


@pytest.fixture
def webhook() -> Iterator[ServidorWebhookFalso]:
    with ServidorWebhookFalso() as servidor:
        yield servidor


def _ana_sin_casco_confirmada(sucursal: SucursalSimulada) -> None:
    sucursal.filmar([operario("Ana", CHALECO)], CONFIRMACION)


# --- Configuración de zonas ---------------------------------------------------------------------


def test_marcar_el_epp_de_una_zona_lo_guarda_y_lo_confirma_al_usuario(tmp_path: Path) -> None:
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)

    mensaje = sucursal.exigir(BOCA_DE_POZO, CASCO, CHALECO)

    assert mensaje == "Zonas guardadas"
    assert json.loads(sucursal.ruta_zonas.read_text(encoding="utf-8"))["zonas"] == {
        BOCA_DE_POZO: {
            "poligono": [list(punto) for punto in POLIGONO_BOCA_DE_POZO],
            "epp_requerido": ["casco", "chaleco"],
        }
    }


def test_volver_a_dibujar_una_zona_conserva_su_epp_exigido(tmp_path: Path) -> None:
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)
    sucursal.exigir(BOCA_DE_POZO, CASCO)

    sucursal.dibujar_zona(BOCA_DE_POZO, ((0, 0), (500, 0), (500, 500), (0, 500)))

    zona = json.loads(sucursal.ruta_zonas.read_text(encoding="utf-8"))["zonas"][BOCA_DE_POZO]
    assert zona["epp_requerido"] == ["casco"]


# --- Detección de infracciones (AC-012, AC-013, AC-015) ----------------------------------------


def test_sin_casco_4_segundos_en_la_zona_aparece_una_alerta_con_imagen_en_el_panel(
    sucursal: SucursalSimulada,
) -> None:
    _ana_sin_casco_confirmada(sucursal)

    (alerta,) = sucursal.alertas()
    assert (alerta.persona, alerta.zona, alerta.elemento) == ("Ana", BOCA_DE_POZO, "casco")
    assert alerta.hora == (INICIO_DEL_TURNO + CONFIRMACION).strftime("%d/%m %H:%M:%S")
    assert alerta.aviso == "Aviso pendiente"
    assert alerta.recibido is None
    assert sucursal.evidencias() == [Path(str(alerta.miniatura))]


def test_la_evidencia_queda_dentro_de_la_carpeta_de_la_sucursal(
    sucursal: SucursalSimulada,
) -> None:
    _ana_sin_casco_confirmada(sucursal)

    (evidencia,) = sucursal.evidencias()
    assert evidencia.is_relative_to(sucursal.carpeta_snapshots / "epp")
    assert evidencia.stat().st_size > 0


def test_una_ausencia_mas_corta_que_la_confirmacion_no_genera_alerta(
    sucursal: SucursalSimulada,
) -> None:
    sucursal.filmar([operario("Ana", CHALECO)], CASI_CONFIRMACION)

    assert sucursal.alertas() == []
    assert sucursal.evidencias() == []


def test_un_operario_con_todo_su_epp_no_genera_alertas(sucursal: SucursalSimulada) -> None:
    sucursal.filmar([operario("Ana", CASCO, CHALECO)], DIEZ_MINUTOS)

    assert sucursal.alertas() == []


def test_fuera_de_toda_zona_no_se_exige_epp(sucursal: SucursalSimulada) -> None:
    sucursal.filmar([operario("Ana", x=FUERA_DE_TODA_ZONA)], DIEZ_MINUTOS)

    assert sucursal.alertas() == []


def test_una_zona_sin_epp_marcado_no_genera_alertas(tmp_path: Path) -> None:
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)
    sucursal.conectar_camara()

    sucursal.filmar([operario("Ana")], DIEZ_MINUTOS)

    assert sucursal.alertas() == []


def test_solo_se_alerta_el_elemento_que_la_zona_exige(sucursal: SucursalSimulada) -> None:
    sucursal.filmar([operario("Ana", CASCO)], DIEZ_MINUTOS)

    assert sucursal.alertas() == []


def test_un_cambio_de_epp_exigido_rige_al_reconectar_la_camara(tmp_path: Path) -> None:
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)
    sucursal.conectar_camara()
    sucursal.exigir(BOCA_DE_POZO, CASCO)
    sucursal.filmar([operario("Ana")], CONFIRMACION)
    antes_de_reconectar = sucursal.alertas()

    sucursal.conectar_camara()
    sucursal.filmar([operario("Ana")], CONFIRMACION)

    assert antes_de_reconectar == []
    assert [alerta.elemento for alerta in sucursal.alertas()] == ["casco"]


def test_un_operario_no_identificado_figura_como_persona_no_identificada(
    sucursal: SucursalSimulada,
) -> None:
    sucursal.filmar([operario(None, CHALECO)], CONFIRMACION)

    assert [alerta.persona for alerta in sucursal.alertas()] == ["persona no identificada"]


def test_cada_operario_sin_casco_genera_su_propia_alerta(sucursal: SucursalSimulada) -> None:
    ana = operario("Ana", track_id=1)
    luis = operario("Luis", CASCO, x=250.0, track_id=2)
    pedro = operario("Pedro", x=150.0, track_id=3)

    sucursal.filmar([ana, luis, pedro], CONFIRMACION)

    assert sorted(alerta.persona for alerta in sucursal.alertas()) == ["Ana", "Pedro"]


# --- Una alerta por infracción (AC-014) --------------------------------------------------------


def test_una_infraccion_sostenida_10_minutos_genera_una_sola_alerta(
    sucursal: SucursalSimulada,
) -> None:
    sucursal.filmar([operario("Ana", CHALECO)], DIEZ_MINUTOS)

    assert len(sucursal.alertas()) == 1
    assert len(sucursal.evidencias()) == 1


def test_si_el_seguimiento_cambia_el_id_de_un_empleado_reconocido_no_se_duplica_la_alerta(
    sucursal: SucursalSimulada,
) -> None:
    sucursal.filmar([operario("Ana", track_id=1)], CONFIRMACION)

    sucursal.filmar([operario("Ana", track_id=2)], 2 * CONFIRMACION)

    assert len(sucursal.alertas()) == 1


# --- Avisos al responsable (AC-016) ------------------------------------------------------------


def test_el_aviso_llega_al_webhook_con_la_imagen_y_queda_enviado(
    sucursal: SucursalSimulada, webhook: ServidorWebhookFalso
) -> None:
    _ana_sin_casco_confirmada(sucursal)

    sucursal.abrir_con_webhook(webhook.url)

    (pedido,) = webhook.aceptados
    cuerpo = json.loads(pedido.cuerpo)
    assert (cuerpo["persona"], cuerpo["elemento"], cuerpo["zona"]) == ("Ana", "casco", BOCA_DE_POZO)
    assert cuerpo["imagen_jpeg_base64"]
    assert [alerta.aviso for alerta in sucursal.alertas()] == ["Aviso enviado"]


def test_con_el_canal_caido_el_aviso_espera_y_sale_una_sola_vez_al_restablecerse(
    sucursal: SucursalSimulada, webhook: ServidorWebhookFalso
) -> None:
    _ana_sin_casco_confirmada(sucursal)
    webhook.estado = HTTPStatus.SERVICE_UNAVAILABLE
    sucursal.abrir_con_webhook(webhook.url)
    con_el_canal_caido = [alerta.aviso for alerta in sucursal.alertas()]

    webhook.estado = HTTPStatus.OK
    sucursal.reloj.avanzar(PRIMER_REINTENTO)
    sucursal.abrir_con_webhook(webhook.url)

    assert con_el_canal_caido == ["Aviso pendiente"]
    assert len(webhook.aceptados) == 1
    assert [alerta.aviso for alerta in sucursal.alertas()] == ["Aviso enviado"]


def test_un_aviso_enviado_no_se_vuelve_a_enviar_al_reabrir_la_sucursal(
    sucursal: SucursalSimulada, webhook: ServidorWebhookFalso
) -> None:
    _ana_sin_casco_confirmada(sucursal)
    sucursal.abrir_con_webhook(webhook.url)

    sucursal.abrir_con_webhook(webhook.url)

    assert len(webhook.recibidos) == 1


# --- Panel y reporte (SPEC/9 §8.2 y §8.4) ------------------------------------------------------


def test_el_responsable_marca_la_alerta_como_recibida_y_queda_firmada(
    sucursal: SucursalSimulada,
) -> None:
    _ana_sin_casco_confirmada(sucursal)
    panel = sucursal.panel()
    hora_del_acuse = sucursal.reloj.ahora().strftime("%H:%M")

    panel.marcar_recibido(panel.filas[0].id_infraccion)

    assert [alerta.recibido for alerta in sucursal.alertas()] == [
        f"Recibido por {SUPERVISOR} a las {hora_del_acuse}"
    ]


def test_el_panel_filtra_las_alertas_por_zona(tmp_path: Path) -> None:
    sucursal = SucursalSimulada(tmp_path)
    sucursal.dibujar_zona(BOCA_DE_POZO, POLIGONO_BOCA_DE_POZO)
    sucursal.dibujar_zona("Taller", ((500, 0), (800, 0), (800, 400), (500, 400)))
    sucursal.exigir(BOCA_DE_POZO, CASCO)
    sucursal.exigir("Taller", CASCO)
    sucursal.conectar_camara()
    sucursal.filmar(
        [operario("Ana"), operario("Luis", x=FUERA_DE_TODA_ZONA, track_id=2)], CONFIRMACION
    )
    panel = sucursal.panel()

    panel.filtrar_por_zona("Taller")

    assert panel.zonas == ["Todas las zonas", BOCA_DE_POZO, "Taller"]
    assert [alerta.persona for alerta in panel.filas] == ["Luis"]


def test_el_reporte_de_cumplimiento_del_dia_cuenta_la_infraccion(
    sucursal: SucursalSimulada,
) -> None:
    _ana_sin_casco_confirmada(sucursal)

    (fila,) = sucursal.reporte_del_dia(INICIO_DEL_TURNO.date())

    assert fila[1:5] == ("Ana", BOCA_DE_POZO, "casco", 1)


def test_el_reporte_de_un_dia_sin_infracciones_lo_dice(sucursal: SucursalSimulada) -> None:
    filas = sucursal.reporte_del_dia(INICIO_DEL_TURNO.date())

    assert filas == [("Sin infracciones en el período", None, None, None, None, None, None)]


# --- Retención de evidencias (AC-019) ----------------------------------------------------------


def test_pasados_30_dias_la_evidencia_se_borra_y_el_registro_se_anonimiza(
    sucursal: SucursalSimulada,
) -> None:
    _ana_sin_casco_confirmada(sucursal)
    sucursal.reloj.avanzar(timedelta(days=RETENCION_DIAS + 1))

    sucursal.abrir_sin_canal()

    assert sucursal.evidencias() == []
    assert sucursal.registros() == [(None, BOCA_DE_POZO, "casco", "PENDIENTE", None)]


def test_antes_de_30_dias_la_evidencia_se_conserva(sucursal: SucursalSimulada) -> None:
    _ana_sin_casco_confirmada(sucursal)
    sucursal.reloj.avanzar(timedelta(days=RETENCION_DIAS - 1))

    sucursal.abrir_sin_canal()

    assert len(sucursal.evidencias()) == 1
    assert [fila[0] for fila in sucursal.registros()] == ["Ana"]
