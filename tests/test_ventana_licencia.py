"""Ventana de activación de la licencia (SPEC/10 F-03.4, T-05)."""

from collections.abc import Iterator
from typing import Any

import customtkinter as ctk
import pytest

from src.gui.ventana_licencia import ESPERA_AL_ACTIVAR_MS, VentanaDeLicencia, pedir_licencia
from src.security.vigencia_licencia import MotivoDeRechazo
from tests.ficha_tk import ficha_visual

MACHINE_ID = "ab" * 32
LLAVE_BUENA = "llave-buena"
CAMARAS = 4
UN_SEGUNDO_Y_MEDIO_MS = 1500


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
    assert ventana.estado.cget("text_color") == "#E74C3C"
    assert licencia.recibidas == []
    assert ventana.activada is False


def test_una_llave_rechazada_muestra_el_motivo(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    _pegar(ventana, "llave-mala")

    assert ventana.estado.cget("text") == "La fecha del equipo no es correcta."
    assert ventana.estado.cget("text_color") == "#E74C3C"
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
    assert ventana.estado.cget("text_color") == "#2ECC71"
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


FICHA = """\
CTkLabel text='Licencia requerida' font=('Roboto', 22, 'bold') height=28 corner_radius=0 \
justify='center' wraplength=0 fg_color='transparent' | padx=0 pady=(15, 5) fill='none' \
anchor='center'
CTkLabel text='Envíe el Machine ID a su proveedor para recibir la llave de activación.' \
font=('Roboto', 12) height=28 corner_radius=0 justify='center' wraplength=560 \
fg_color='transparent' | padx=0 pady=5 fill='none' anchor='center'
CTkFrame height=200 corner_radius=8 fg_color='#2B2B2B' | padx=20 pady=5 fill='x' anchor='center'
  CTkLabel text='Machine ID de este equipo:' height=28 corner_radius=0 justify='center' \
wraplength=0 fg_color='transparent' | padx=10 pady=(8, 2) fill='none' anchor='w'
  CTkEntry font=('Consolas', 11) height=32 corner_radius=6 justify='center' \
fg_color=['#F9F9FA', '#343638'] | padx=10 pady=(0, 10) fill='x' anchor='center'
  CTkButton text='Copiar Machine ID' height=28 corner_radius=6 fg_color=['#3B8ED0', '#1F6AA5'] \
| padx=0 pady=(0, 10) fill='none' anchor='center'
CTkFrame height=200 corner_radius=8 fg_color='#2B2B2B' | padx=20 pady=10 fill='x' anchor='center'
  CTkLabel text='Pegue la llave de activación:' height=28 corner_radius=0 justify='center' \
wraplength=0 fg_color='transparent' | padx=10 pady=(8, 2) fill='none' anchor='w'
  CTkTextbox font=('Consolas', 10) height=80 corner_radius=6 fg_color='#1E1E1E' | padx=10 \
pady=(0, 10) fill='x' anchor='center'
CTkButton text='Activar' height=40 corner_radius=6 fg_color='#2ECC71' | padx=0 pady=10 \
fill='none' anchor='center'
CTkLabel text='' font=('Roboto', 13) height=28 corner_radius=0 justify='center' wraplength=0 \
fg_color='transparent' | padx=0 pady=5 fill='none' anchor='center'
"""


def test_la_ventana_se_ve_como_se_diseno(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())
    ventana.update_idletasks()

    assert "\n".join(ficha_visual(ventana)) + "\n" == FICHA
    assert ventana.title() == "Activación de la licencia"
    assert ventana.protocol("WM_DELETE_WINDOW") != ""
    assert ESPERA_AL_ACTIVAR_MS == UN_SEGUNDO_Y_MEDIO_MS
    assert ventana.cget("fg_color") == "#1E1E1E"
    assert ventana.geometry().startswith("620x520")


def test_los_textos_secundarios_van_en_gris_y_el_titulo_en_rojo(raiz: ctk.CTk) -> None:
    ventana = VentanaDeLicencia(raiz, LicenciaFalsa())

    colores = [
        str(hijo.cget("text_color")) for hijo in _hijos(ventana) if isinstance(hijo, ctk.CTkLabel)
    ]

    assert colores == ["#E74C3C", "#A0A0A0", "#A0A0A0", "#A0A0A0", "#A0A0A0"]


def test_sin_fecha_de_vencimiento_el_alcance_dice_no_disponible(
    raiz: ctk.CTk, monkeypatch: pytest.MonkeyPatch
) -> None:
    licencia = LicenciaFalsa()
    monkeypatch.setattr(licencia, "get_expiration_date", lambda: None)
    ventana = VentanaDeLicencia(raiz, licencia)
    monkeypatch.setattr(ventana, "after", lambda ms, accion: None)

    _pegar(ventana, LLAVE_BUENA)

    assert ventana.estado.cget("text").endswith("| Vence: N/D")
