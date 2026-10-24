"""El módulo de EPP dentro de la ventana principal (SPEC/9 §5.4; D5 y D10)."""

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from config import config
from src.composicion_epp import RelojSistema
from src.gui import epp_en_la_app


class Licencia:
    def __init__(self, *modulos: str) -> None:
        self._modulos = modulos

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo in self._modulos


class DespachadorFalso:
    def __init__(self) -> None:
        self.iniciado = False

    def iniciar(self) -> None:
        self.iniciado = True


Pedido = tuple[object, Callable[[], sqlite3.Connection], Path, object]


@pytest.mark.parametrize(
    ("licencia", "habilitado"),
    [(None, False), (Licencia("reportes"), False), (Licencia("reportes", "epp"), True)],
    ids=["sin_licencia", "licencia_sin_epp", "licencia_con_epp"],
)
def test_el_modulo_se_habilita_solo_con_una_licencia_que_incluye_epp(
    licencia: Licencia | None, habilitado: bool
) -> None:
    assert epp_en_la_app.modulo_habilitado(licencia) is habilitado


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

    monkeypatch.setattr("src.composicion_avisos.preparar_avisos", preparar)
    return pedidos


def test_los_avisos_se_preparan_con_la_base_y_las_evidencias_de_la_sucursal(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pedidos = _preparar_con(monkeypatch, DespachadorFalso())

    epp_en_la_app.iniciar_avisos()

    ((entorno, conectar, carpeta, reloj),) = pedidos
    conectar().close()
    assert (entorno, carpeta) == (os.environ, sucursal / "snapshots")
    assert isinstance(reloj, RelojSistema)
    assert (sucursal / "tenant.db").is_file()


def test_los_avisos_preparados_arrancan(sucursal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    despachador = DespachadorFalso()
    _preparar_con(monkeypatch, despachador)

    iniciado = epp_en_la_app.iniciar_avisos()

    assert iniciado is despachador
    assert despachador.iniciado is True


def test_sin_avisos_que_despachar_no_hay_despachador(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _preparar_con(monkeypatch, None)

    assert epp_en_la_app.iniciar_avisos() is None
