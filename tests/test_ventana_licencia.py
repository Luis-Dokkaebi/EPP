"""Ventana de activación de la licencia (SPEC/10 F-03.4, T-05)."""

from collections.abc import Iterator
from typing import Any

import customtkinter as ctk
import pytest

from src.gui.ventana_licencia import ESPERA_AL_ACTIVAR_MS, VentanaDeLicencia, pedir_licencia
from src.security.vigencia_licencia import MotivoDeRechazo

MACHINE_ID = "ab" * 32
LLAVE_BUENA = "llave-buena"
CAMARAS = 4


class LicenciaFalsa:
    """Doble del DRM: acepta solo LLAVE_BUENA y explica el rechazo de las demás."""

    def __init__(self, motivo: MotivoDeRechazo | None = None) -> None:
        self.machine_id = MACHINE_ID
        self.motivo_de_rechazo = motivo
        self.recibidas: list[str] = []

    def activate_license(self, llave: str) -> bool:
        self.recibidas.append(llave)
        self.motivo_de_rechazo = None if llave == LLAVE_BUENA else MotivoDeRechazo.FECHA_INCORRECTA
        return llave == LLAVE_BUENA

    def get_tier(self) -> str:
        return "prueba"

    def get_max_cameras(self) -> int:
        return CAMARAS

    def get_expiration_date(self) -> str | None:
        return "2026-11-26"


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


def _hijos(widget: Any) -> list[Any]:
    hijos = []
    for hijo in widget.winfo_children():
        hijos.append(hijo)
        hijos.extend(_hijos(hijo))
    return hijos


def _textos(widget: Any) -> list[str]:
    return [str(h.cget("text")) for h in _hijos(widget) if isinstance(h, ctk.CTkLabel)]


def _pegar(ventana: VentanaDeLicencia, llave: str) -> None:
    ventana.campo_de_llave.insert("1.0", llave)
    ventana.activar()


def test_la_ventana_muestra_el_machine_id_para_enviarlo_al_proveedor(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    assert ventana.campo_machine_id.get() == MACHINE_ID
    assert _textos(ventana)[:2] == [
        "Licencia requerida",
        "Envíe el Machine ID a su proveedor para recibir la llave de activación.",
    ]
    assert ventana.activada is False
    assert ventana.estado.cget("text") == ""


def test_el_machine_id_no_se_puede_editar(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    ventana.campo_machine_id.insert(0, "zz")

    assert ventana.campo_machine_id.get() == MACHINE_ID


def test_el_boton_copia_el_machine_id_al_portapapeles(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())
    raiz.clipboard_clear()
    raiz.clipboard_append("otra cosa")

    ventana.copiar_machine_id()

    assert raiz.clipboard_get() == MACHINE_ID


def test_una_licencia_vencida_invita_a_contratar_y_avisa_que_nada_se_pierde(
    raiz: ctk.CTk,
) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa(MotivoDeRechazo.VENCIDA))

    assert _textos(ventana)[:2] == [
        "Su licencia venció",
        "Contrate para continuar: lo aprendido se conserva (rostros, zonas e historial).",
    ]


def test_un_reloj_atrasado_se_explica_al_abrir(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa(MotivoDeRechazo.FECHA_INCORRECTA))

    assert _textos(ventana)[:2] == [
        "Licencia requerida",
        "La fecha del equipo no es correcta. Corríjala y vuelva a abrir la aplicación.",
    ]


def test_activar_sin_pegar_la_llave_lo_pide_sin_consultar_al_drm(raiz: ctk.CTk) -> None:
    licencia = LicenciaFalsa()
    ventana = VentanaDeLicencia(raiz, licencia)

    _pegar(ventana, "  \n")

    assert ventana.estado.cget("text") == "Pegue la llave de activación en el campo de texto."
    assert licencia.recibidas == []
    assert ventana.activada is False


def test_una_llave_rechazada_muestra_el_motivo(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    _pegar(ventana, "llave-mala")

    assert ventana.estado.cget("text") == "La fecha del equipo no es correcta."
    assert ventana.activada is False
    assert ventana.winfo_exists()


def test_una_llave_valida_activa_muestra_el_alcance_y_cierra_la_ventana(
    raiz: ctk.CTk, monkeypatch: pytest.MonkeyPatch
) -> None:
    licencia = LicenciaFalsa()
    ventana = VentanaDeLicencia(raiz, licencia)
    programadas: list[tuple[int, Any]] = []
    monkeypatch.setattr(ventana, "after", lambda ms, accion: programadas.append((ms, accion)))

    _pegar(ventana, f"  {LLAVE_BUENA}\n")

    assert licencia.recibidas == [LLAVE_BUENA]
    assert ventana.activada is True
    assert ventana.estado.cget("text") == (
        "Licencia activada | Tipo: PRUEBA | Cámaras: 4 | Vence: 2026-11-26"
    )
    assert programadas == [(ESPERA_AL_ACTIVAR_MS, ventana.destroy)]


def test_cerrar_la_ventana_sin_activar_la_destruye(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    ventana.cerrar()

    assert not ventana.winfo_exists()
    assert ventana.activada is False


def test_la_ventana_es_modal(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    assert raiz.grab_current() is ventana


@pytest.mark.parametrize(("llave", "activada"), [(LLAVE_BUENA, True), ("llave-mala", False)])
def test_pedir_licencia_espera_la_ventana_y_dice_si_se_activo(
    llave: str, activada: bool, raiz: ctk.CTk, monkeypatch: pytest.MonkeyPatch
) -> None:
    licencia = LicenciaFalsa()
    esperadas: list[VentanaDeLicencia] = []

    def usuario_pega_la_llave(ventana: VentanaDeLicencia) -> None:
        esperadas.append(ventana)
        _pegar(ventana, llave)

    monkeypatch.setattr(raiz, "wait_window", usuario_pega_la_llave)

    assert pedir_licencia(raiz, licencia) is activada
    assert licencia.recibidas == [llave]
    assert [ventana.master for ventana in esperadas] == [raiz]
