"""Sucursal simulada para features/modo_sombra_epp.feature: base real en tmp_path, canal falso.

Abrir la sucursal es lo mismo que hace la aplicación (`preparar_avisos` y, si hay despachador,
iniciarlo); el canal de aviso se reemplaza por uno en memoria que anota a quién se avisó.
"""

import sqlite3
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

import pytest

from src import composicion_avisos
from src.alerts.domain.aviso import Aviso
from src.alerts.domain.errores import ConfiguracionAlertasError
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from tests.dobles_ppe import INICIO, RelojFalso

FIN_DEL_MODO_SOMBRA = INICIO
UNA_HORA = timedelta(hours=1)
ESPERA_DEL_DESPACHADOR = timedelta(seconds=10)
# Basta con que haya un canal configurado: la simulación reemplaza su construcción.
CANAL = {"EPP_ALERTAS_WEBHOOK_URL": "https://avisos.example.com/epp"}


class CanalEnMemoria:
    def __init__(self) -> None:
        self.avisados: list[str | None] = []

    def enviar(self, aviso: Aviso) -> None:
        self.avisados.append(aviso.persona)


class SucursalEnSombra:
    def __init__(self, carpeta: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ruta = carpeta / "tenant.db"
        self.conectar: Callable[[], sqlite3.Connection] = lambda: sqlite3.connect(ruta)
        self._carpeta = carpeta / "snapshots"
        self.canal = CanalEnMemoria()
        self.error: ConfiguracionAlertasError | None = None
        crear_tabla_infracciones(self.conectar)
        monkeypatch.setattr(composicion_avisos, "canales_desde_entorno", self._canales)

    def _canales(self, _entorno: Mapping[str, str], *_resto: object) -> CanalEnMemoria:
        return self.canal

    def registrar(self, nombre: str, elemento: str, desfase: timedelta) -> None:
        incumplimiento = Incumplimiento(1, nombre, ElementoEPP(elemento), "Boca de pozo")
        inicio = FIN_DEL_MODO_SOMBRA + desfase
        RepositorioInfraccionesSQLite(self.conectar).guardar(
            InfraccionIniciada(incumplimiento, inicio, "epp-1", None)
        )

    def abrir(self, entorno: Mapping[str, str]) -> None:
        reloj = RelojFalso(FIN_DEL_MODO_SOMBRA + 2 * UNA_HORA)
        try:
            despachador = composicion_avisos.preparar_avisos(
                {**CANAL, **entorno}, self.conectar, self._carpeta, reloj
            )
        except ConfiguracionAlertasError as error:
            self.error = error
            return
        if despachador is not None:
            despachador.iniciar()
            despachador.detener(ESPERA_DEL_DESPACHADOR)

    def estado_de(self, nombre: str) -> str:
        consulta = "SELECT estado_notificacion FROM ppe_infracciones WHERE employee_name = ?"
        conexion = self.conectar()
        ((estado,),) = conexion.execute(consulta, (nombre,)).fetchall()
        conexion.close()
        return str(estado)
