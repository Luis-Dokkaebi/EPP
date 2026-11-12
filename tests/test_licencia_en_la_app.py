"""La licencia en la ventana principal (SPEC/10 T-05): aviso de la prueba y revalidación."""

from collections.abc import Callable, Iterator
from typing import Any

import customtkinter as ctk
import pytest

from src.gui import licencia_en_la_app
from src.gui.licencia_en_la_app import (
    COLOR_AVISO,
    COLOR_URGENTE,
    INTERVALO_DE_REVALIDACION_MS,
    LicenciaEnLaApp,
)

UNA_HORA_MS = 3_600_000
DIAS_SIN_URGENCIA = 10
DIAS_URGENTES = 2


class LicenciaFalsa:
    def __init__(self, dias: int | None, vigente: bool = True) -> None:
        self.dias = dias
        self.vigente = vigente
        self.prueba = True
        self.validaciones = 0

    def es_prueba(self) -> bool:
        return self.prueba

    def dias_restantes(self) -> int | None:
        return self.dias

    def validate_license(self) -> bool:
        self.validaciones += 1
        return self.vigente


class AppFalsa(ctk.CTk):
    """Ventana principal mínima: anota lo que la licencia le pide y los temporizadores."""

    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        self.barra = ctk.CTkFrame(self)
        self.pasos: list[str] = []
        self.programadas: list[tuple[int, Callable[[], None]]] = []

    def after(self, ms: int, func: Any = None, *args: Any) -> str:
        """La revalidación (una hora) se anota sin esperar; lo demás sigue en Tk."""
        if ms != INTERVALO_DE_REVALIDACION_MS:
            return str(super().after(ms, func, *args))
        self.programadas.append((ms, func))
        return "temporizador-falso"

    def suspender_por_licencia(self) -> None:
        self.pasos.append("suspender")

    def reanudar_con_licencia(self) -> None:
        self.pasos.append("reanudar")

    def on_closing(self) -> None:
        self.pasos.append("cerrar")


@pytest.fixture
def app() -> Iterator[AppFalsa]:
    aplicacion = AppFalsa()
    yield aplicacion
    aplicacion.destroy()


@pytest.fixture
def ventana_de_activacion(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Reemplaza la ventana real: `activa` decide si el usuario pega una licencia nueva."""
    pedido: dict[str, Any] = {"activa": False, "pedidas": []}

    def pedir(raiz: object, licencia: object) -> bool:
        pedido["pedidas"].append((raiz, licencia))
        return bool(pedido["activa"])

    monkeypatch.setattr(licencia_en_la_app, "pedir_licencia", pedir)
    return pedido


def _vigilar(app: AppFalsa, licencia: LicenciaFalsa) -> LicenciaEnLaApp:
    return LicenciaEnLaApp(app, licencia, app.barra)


def test_el_intervalo_de_revalidacion_es_una_hora() -> None:
    assert INTERVALO_DE_REVALIDACION_MS == UNA_HORA_MS


def test_una_prueba_con_dias_de_sobra_muestra_el_aviso_sin_urgencia(app: AppFalsa) -> None:
    vigilancia = _vigilar(app, LicenciaFalsa(DIAS_SIN_URGENCIA))

    assert vigilancia.aviso.cget("text") == "Prueba: quedan 10 días"
    assert vigilancia.aviso.cget("text_color") == COLOR_AVISO
    assert vigilancia.aviso.winfo_manager() == "pack"


def test_el_aviso_va_alineado_a_la_izquierda_en_negrita(app: AppFalsa) -> None:
    vigilancia = _vigilar(app, LicenciaFalsa(DIAS_SIN_URGENCIA))

    empaque = vigilancia.aviso.pack_info()

    assert vigilancia.aviso.cget("font") == ("Roboto", 14, "bold")
    assert (empaque["pady"], empaque["padx"], empaque["anchor"]) == ((0, 10), 20, "w")


def test_los_ultimos_dias_el_aviso_va_en_rojo(app: AppFalsa) -> None:
    vigilancia = _vigilar(app, LicenciaFalsa(DIAS_URGENTES))

    assert vigilancia.aviso.cget("text") == "Prueba: quedan 2 días"
    assert (COLOR_URGENTE, vigilancia.aviso.cget("text_color")) == ("#E74C3C", "#E74C3C")


def test_una_licencia_comercial_no_muestra_el_aviso(app: AppFalsa) -> None:
    licencia = LicenciaFalsa(DIAS_SIN_URGENCIA)
    licencia.prueba = False

    vigilancia = _vigilar(app, licencia)

    assert vigilancia.aviso.winfo_manager() == ""
    assert vigilancia.aviso.cget("text") == ""


def test_al_abrir_se_programa_la_primera_revalidacion_sin_validar_todavia(app: AppFalsa) -> None:
    licencia = LicenciaFalsa(DIAS_SIN_URGENCIA)

    vigilancia = _vigilar(app, licencia)

    assert app.programadas == [(UNA_HORA_MS, vigilancia.revalidar)]
    assert licencia.validaciones == 0


def test_cada_hora_se_revalida_se_actualiza_el_aviso_y_se_programa_la_siguiente(
    app: AppFalsa,
) -> None:
    licencia = LicenciaFalsa(DIAS_SIN_URGENCIA)
    vigilancia = _vigilar(app, licencia)
    licencia.dias = DIAS_URGENTES

    vigilancia.revalidar()

    assert licencia.validaciones == 1
    assert vigilancia.aviso.cget("text") == "Prueba: quedan 2 días"
    assert vigilancia.aviso.cget("text_color") == COLOR_URGENTE
    assert app.programadas == [(UNA_HORA_MS, vigilancia.revalidar)] * 2
    assert app.pasos == []


def test_al_vencer_la_app_se_suspende_pide_licencia_y_se_cierra_si_no_la_recibe(
    app: AppFalsa, ventana_de_activacion: dict[str, Any]
) -> None:
    licencia = LicenciaFalsa(DIAS_URGENTES)
    vigilancia = _vigilar(app, licencia)
    licencia.vigente = False

    vigilancia.revalidar()

    assert app.pasos == ["suspender", "cerrar"]
    assert ventana_de_activacion["pedidas"] == [(app, licencia)]
    assert app.programadas == [(UNA_HORA_MS, vigilancia.revalidar)]


def test_si_se_activa_una_licencia_comercial_la_app_sigue_y_el_aviso_desaparece(
    app: AppFalsa, ventana_de_activacion: dict[str, Any]
) -> None:
    licencia = LicenciaFalsa(DIAS_URGENTES)
    vigilancia = _vigilar(app, licencia)
    licencia.vigente = False
    licencia.prueba = False
    ventana_de_activacion["activa"] = True

    vigilancia.revalidar()

    assert app.pasos == ["suspender", "reanudar"]
    assert vigilancia.aviso.winfo_manager() == ""
    assert app.programadas == [(UNA_HORA_MS, vigilancia.revalidar)] * 2
