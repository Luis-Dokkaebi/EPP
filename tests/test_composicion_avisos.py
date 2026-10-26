"""Avisos de EPP al abrir la sucursal: retención, modo sombra y despachador (SPEC/9 §5.4, §7)."""

import logging
import os
import sqlite3
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

import pytest

from config import config
from src import composicion_avisos
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import ConfiguracionAlertasError
from src.alerts.domain.reintentos import PoliticaReintentos
from src.alerts.hilo_despachador import HiloDespachador
from src.composicion_avisos import iniciar_avisos_de_la_sucursal, preparar_avisos
from src.composicion_epp import RelojSistema
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from tests.dobles_ppe import INICIO, RelojFalso

WEBHOOK = {
    "EPP_ALERTAS_WEBHOOK_URL": "https://avisos.example.com/epp",
    # Valores ficticios de prueba, no credenciales reales.
    "EPP_ALERTAS_WEBHOOK_SECRETO": "secreto-de-prueba",  # pragma: allowlist secret
    "EPP_ALERTAS_WEBHOOK_TIMEOUT_S": "2",
}
UN_DIA = timedelta(days=1)
RETENCION = timedelta(days=30)


@pytest.fixture
def conectar(tmp_path: Path) -> Callable[[], sqlite3.Connection]:
    ruta = tmp_path / "tenant.db"
    return lambda: sqlite3.connect(ruta)


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    return tmp_path / "snapshots"


def _registrar(conectar: Callable[[], sqlite3.Connection], inicio_offset: timedelta,
               evidencia: str | None = None) -> None:  # fmt: skip
    crear_tabla_infracciones(conectar)
    incumplimiento = Incumplimiento(1, "Ana", ElementoEPP.CASCO, "Anden")
    evento = InfraccionIniciada(incumplimiento, INICIO + inicio_offset, "epp-1", evidencia)
    RepositorioInfraccionesSQLite(conectar).guardar(evento)


def _estados(conectar: Callable[[], sqlite3.Connection]) -> list[str]:
    conexion = conectar()
    filas = conexion.execute("SELECT estado_notificacion FROM ppe_infracciones ORDER BY id")
    estados = [estado for (estado,) in filas]
    conexion.close()
    return estados


def test_sin_canales_configurados_no_hay_despachador(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    assert preparar_avisos({}, conectar, carpeta, RelojFalso(INICIO)) is None


def test_con_un_canal_queda_un_despachador_listo_para_iniciar(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    despachador = preparar_avisos(WEBHOOK, conectar, carpeta, RelojFalso(INICIO))

    assert isinstance(despachador, HiloDespachador)
    assert despachador.en_marcha is False


def test_en_modo_sombra_no_hay_despachador_aunque_haya_canales(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    entorno = {**WEBHOOK, "EPP_MODO_SOMBRA": "1"}

    assert preparar_avisos(entorno, conectar, carpeta, RelojFalso(INICIO)) is None


def test_al_salir_del_modo_sombra_se_descartan_las_pendientes_de_ese_periodo(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    _registrar(conectar, -UN_DIA)
    _registrar(conectar, UN_DIA)
    entorno = {**WEBHOOK, "EPP_FIN_MODO_SOMBRA": INICIO.isoformat()}

    preparar_avisos(entorno, conectar, carpeta, RelojFalso(INICIO + 2 * UN_DIA))

    assert _estados(conectar) == ["DESCARTADA", "PENDIENTE"]


def test_en_modo_sombra_no_se_descarta_nada_todavia(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    _registrar(conectar, -UN_DIA)
    entorno = {"EPP_MODO_SOMBRA": "1", "EPP_FIN_MODO_SOMBRA": INICIO.isoformat()}

    preparar_avisos(entorno, conectar, carpeta, RelojFalso(INICIO))

    assert _estados(conectar) == ["PENDIENTE"]


@pytest.mark.parametrize(
    ("fin", "mensaje"),
    [
        ("ayer", r"^EPP_FIN_MODO_SOMBRA debe ser una fecha ISO 8601 con huso horario: ayer$"),
        (
            "2026-10-22T08:00:00",
            r"^EPP_FIN_MODO_SOMBRA debe llevar huso horario: 2026-10-22T08:00:00$",
        ),
    ],
    ids=["texto", "sin_huso"],
)
def test_un_fin_de_modo_sombra_invalido_falla_en_voz_alta(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path, fin: str, mensaje: str
) -> None:
    with pytest.raises(ConfiguracionAlertasError, match=mensaje):
        preparar_avisos({"EPP_FIN_MODO_SOMBRA": fin}, conectar, carpeta, RelojFalso(INICIO))


def test_al_abrir_la_sucursal_se_purgan_las_evidencias_de_mas_de_30_dias(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    vieja, nueva = carpeta / "epp" / "vieja.jpg", carpeta / "epp" / "nueva.jpg"
    vieja.parent.mkdir(parents=True)
    vieja.write_bytes(b"jpg")
    nueva.write_bytes(b"jpg")
    _registrar(conectar, -RETENCION - UN_DIA, str(vieja))
    _registrar(conectar, -RETENCION + UN_DIA, str(nueva))

    preparar_avisos({}, conectar, carpeta, RelojFalso(INICIO))

    assert (vieja.exists(), nueva.exists()) == (False, True)


def test_preparar_crea_las_tablas_de_una_sucursal_nueva(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path
) -> None:
    preparar_avisos({}, conectar, carpeta, RelojFalso(INICIO))

    assert _estados(conectar) == []


def test_los_reintentos_el_circuito_y_el_intervalo_son_los_del_plan() -> None:
    assert composicion_avisos.POLITICA_DE_REINTENTOS == PoliticaReintentos(
        espera_inicial=timedelta(seconds=30),
        factor=2.0,
        espera_maxima=timedelta(minutes=30),
        intentos_maximos=8,
    )
    assert (
        composicion_avisos.FALLAS_PARA_ABRIR_EL_CIRCUITO,
        composicion_avisos.PAUSA_DEL_CIRCUITO,
        composicion_avisos.INTERVALO_DE_DESPACHO,
    ) == (3, timedelta(minutes=5), timedelta(seconds=15))


class CanalFalso:
    def __init__(self) -> None:
        self.enviados: list[int] = []

    def enviar(self, aviso: Aviso) -> None:
        self.enviados.append(aviso.id_aviso)


def test_el_despachador_entrega_las_pendientes_por_los_canales_del_entorno(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _registrar(conectar, timedelta(0))
    canal = CanalFalso()
    pedidos: list[Mapping[str, str]] = []

    def canales(entorno: Mapping[str, str], *_resto: object) -> CanalFalso:
        pedidos.append(entorno)
        return canal

    monkeypatch.setattr(composicion_avisos, "canales_desde_entorno", canales)
    despachador = preparar_avisos(WEBHOOK, conectar, carpeta, RelojFalso(INICIO))
    assert despachador is not None

    despachador.iniciar()
    despachador.detener(timedelta(seconds=10))

    assert (pedidos, canal.enviados, _estados(conectar)) == ([WEBHOOK], [1], ["ENVIADA"])


def test_cada_paso_al_abrir_la_sucursal_queda_registrado(
    conectar: Callable[[], sqlite3.Connection], carpeta: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _registrar(conectar, -UN_DIA)
    sombra = {"EPP_MODO_SOMBRA": "1"}
    salida = {"EPP_FIN_MODO_SOMBRA": INICIO.isoformat()}

    with caplog.at_level(logging.INFO, logger=composicion_avisos.__name__):
        preparar_avisos(sombra, conectar, carpeta, RelojFalso(INICIO))
        preparar_avisos(salida, conectar, carpeta, RelojFalso(INICIO))

    assert [r.getMessage() for r in caplog.records] == [
        "Evidencias de EPP purgadas por retención: 0",
        "Módulo EPP en modo sombra: se registra sin avisar",
        "Evidencias de EPP purgadas por retención: 0",
        "Avisos del modo sombra descartados: 1",
        "Sin canal de aviso configurado (D1: email y webhook): no se avisa",
    ]


# --- Arranque desde la aplicación (GUI y modo sin interfaz) ------------------------------------


class DespachadorFalso:
    def __init__(self) -> None:
        self.iniciado = False

    def iniciar(self) -> None:
        self.iniciado = True


Pedido = tuple[object, Callable[[], sqlite3.Connection], Path, object]


@pytest.fixture
def sucursal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "get_db_path", lambda: str(tmp_path / "tenant.db"))
    monkeypatch.setattr(config, "get_snapshots_dir", lambda: str(tmp_path / "snapshots"))
    return tmp_path


def _preparar_con(
    monkeypatch: pytest.MonkeyPatch, despachador: DespachadorFalso | None
) -> list[Pedido]:
    pedidos: list[Pedido] = []

    def preparar(
        entorno: object, conectar: Callable[[], sqlite3.Connection], carpeta: Path, reloj: object
    ) -> DespachadorFalso | None:
        pedidos.append((entorno, conectar, carpeta, reloj))
        return despachador

    monkeypatch.setattr(composicion_avisos, "preparar_avisos", preparar)
    return pedidos


def test_la_sucursal_prepara_los_avisos_con_su_base_y_sus_evidencias(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pedidos = _preparar_con(monkeypatch, DespachadorFalso())

    iniciar_avisos_de_la_sucursal()

    ((entorno, conectar, carpeta, reloj),) = pedidos
    conectar().close()
    assert (entorno, carpeta) == (os.environ, sucursal / "snapshots")
    assert isinstance(reloj, RelojSistema)
    assert (sucursal / "tenant.db").is_file()


def test_los_avisos_preparados_de_la_sucursal_arrancan(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    despachador = DespachadorFalso()
    _preparar_con(monkeypatch, despachador)

    iniciado = iniciar_avisos_de_la_sucursal()

    assert iniciado is despachador
    assert despachador.iniciado is True


def test_sin_avisos_que_despachar_la_sucursal_no_tiene_despachador(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _preparar_con(monkeypatch, None)

    assert iniciar_avisos_de_la_sucursal() is None
