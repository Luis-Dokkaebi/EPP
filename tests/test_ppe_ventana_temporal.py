"""Confirmación temporal de la ausencia con histéresis (SPEC/9 §4.2, AC-012).

Cada letra es un frame, uno por segundo: P presente, A ausente, N no verificable. La salida usa
las mismas letras para el estado filtrado. Configuración de las pruebas: P = 80 %, T = 4 s (la
ventana abarca 5 frames, bordes incluidos), M = 3 frames y limpieza a los 10 s.
"""

import dataclasses
from datetime import timedelta

import pytest

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.ppe.domain.errores import ConfiguracionInvalidaError, RelojRetrocedioError
from src.ppe.domain.ventana_temporal import ConfiguracionVentana, VentanaTemporal
from tests.dobles_ppe import RelojFalso

UN_SEGUNDO = timedelta(seconds=1)
CONFIGURACION = ConfiguracionVentana(
    fraccion_ausente_minima=0.8,
    tiempo_confirmacion=timedelta(seconds=4),
    presentes_para_recuperar=3,
    tiempo_limpieza=timedelta(seconds=10),
)
ESTADOS = {
    "P": EstadoElemento.PRESENTE,
    "A": EstadoElemento.AUSENTE,
    "N": EstadoElemento.NO_VERIFICABLE,
}
LETRAS = {estado: letra for letra, estado in ESTADOS.items()}
CASCO = ElementoEPP.CASCO
CHALECO = ElementoEPP.CHALECO


def _paso(ventana: VentanaTemporal, reloj: RelojFalso, letra: str) -> str:
    estado = ventana.actualizar({1: {CASCO: ESTADOS[letra]}})[1][CASCO]
    reloj.avanzar(UN_SEGUNDO)
    return LETRAS[estado]


def _filtrar_con(ventana: VentanaTemporal, reloj: RelojFalso, secuencia: str) -> str:
    return "".join(_paso(ventana, reloj, letra) for letra in secuencia)


def _filtrar(secuencia: str, configuracion: ConfiguracionVentana = CONFIGURACION) -> str:
    reloj = RelojFalso()
    return _filtrar_con(VentanaTemporal(configuracion, reloj), reloj, secuencia)


@pytest.mark.parametrize(
    ("observado", "filtrado"),
    [
        ("PPAAAAA", "PPPPPPA"),
        ("AAAAAA", "PPPPAA"),
        ("PPAAAPPPAAAA", "PPPPPPPPPPPP"),
        ("APAAA", "PPPPA"),
        ("APPAAAA", "PPPPPPA"),
        ("AAAAAPPPA", "PPPPAAAPP"),
        ("AAAAAPPAPPP", "PPPPAAAAAAP"),
    ],
    ids=[
        "ausencia_sostenida_confirma_exactamente_en_t",
        "track_nuevo_sin_casco_confirma_en_t",
        "oclusion_breve_no_confirma",
        "frame_en_el_borde_de_la_ventana_cuenta",
        "confirma_cuando_la_fraccion_llega_a_p",
        "recupera_tras_m_presentes_seguidos",
        "presentes_interrumpidos_no_recuperan",
    ],
)
def test_ventana_temporal_confirma_y_recupera_con_histeresis(observado: str, filtrado: str) -> None:
    assert _filtrar(observado) == filtrado


@pytest.mark.parametrize(
    ("fraccion", "filtrado"),
    [(0.8, "PPPPPPPPPP"), (0.5, "PPPPAAAAAA")],
    ids=["p_80_no_confirma", "p_50_confirma"],
)
def test_ventana_temporal_parpadeo_alternado_confirma_segun_p(
    fraccion: float, filtrado: str
) -> None:
    configuracion = dataclasses.replace(CONFIGURACION, fraccion_ausente_minima=fraccion)

    assert _filtrar("APAPAPAPAP", configuracion) == filtrado


@pytest.mark.parametrize(
    ("observado", "filtrado"),
    [("AANNNAA", "PPNNNAA"), ("AAAAANNN", "PPPPAAAA"), ("AAAAAPNPP", "PPPPAAAAP")],
    ids=[
        "no_cuentan_en_la_fraccion",
        "mantienen_la_confirmacion",
        "no_cortan_la_racha_de_presentes",
    ],
)
def test_ventana_temporal_ignora_los_frames_no_verificables(observado: str, filtrado: str) -> None:
    assert _filtrar(observado) == filtrado


def test_ventana_temporal_cada_track_y_elemento_tiene_su_propia_ventana() -> None:
    reloj = RelojFalso()
    ventana = VentanaTemporal(CONFIGURACION, reloj)
    ausente, presente = EstadoElemento.AUSENTE, EstadoElemento.PRESENTE
    observados = {1: {CASCO: ausente, CHALECO: presente}, 2: {CASCO: presente}}
    ventana.actualizar(observados)
    reloj.avanzar(timedelta(seconds=4))

    filtrados = ventana.actualizar(observados)

    assert filtrados == {1: {CASCO: ausente, CHALECO: presente}, 2: {CASCO: presente}}


@pytest.mark.parametrize(
    ("ausencia_del_track", "filtrado_al_volver"),
    [(timedelta(seconds=10), "A"), (timedelta(seconds=11), "P")],
    ids=["vuelve_en_el_limite_y_conserva_la_confirmacion", "vuelve_despues_y_empieza_de_cero"],
)
def test_ventana_temporal_olvida_los_tracks_inactivos(
    ausencia_del_track: timedelta, filtrado_al_volver: str
) -> None:
    reloj = RelojFalso()
    ventana = VentanaTemporal(CONFIGURACION, reloj)
    _filtrar_con(ventana, reloj, "AAAAA")
    reloj.avanzar(ausencia_del_track - UN_SEGUNDO)

    assert _filtrar_con(ventana, reloj, "A") == filtrado_al_volver


def test_ventana_temporal_admite_dos_frames_en_el_mismo_instante() -> None:
    reloj = RelojFalso()
    ventana = VentanaTemporal(CONFIGURACION, reloj)
    ventana.actualizar({1: {CASCO: EstadoElemento.PRESENTE}})

    filtrados = ventana.actualizar({1: {CASCO: EstadoElemento.AUSENTE}})

    assert filtrados == {1: {CASCO: EstadoElemento.PRESENTE}}


def test_ventana_temporal_rechaza_un_salto_del_reloj_hacia_atras() -> None:
    reloj = RelojFalso()
    ventana = VentanaTemporal(CONFIGURACION, reloj)
    ventana.actualizar({})
    reloj.avanzar(-UN_SEGUNDO)

    with pytest.raises(
        RelojRetrocedioError,
        match=r"^El reloj retrocedió de 2026-10-22 08:00:00\+00:00 a 2026-10-22 07:59:59\+00:00$",
    ):
        ventana.actualizar({})


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("fraccion_ausente_minima", 0.0),
        ("tiempo_confirmacion", timedelta(0)),
        ("presentes_para_recuperar", 0),
        ("tiempo_limpieza", timedelta(0)),
    ],
)
def test_configuracion_ventana_valida_cada_umbral(campo: str, valor: object) -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=f"^{campo} debe "):
        dataclasses.replace(CONFIGURACION, **{campo: valor})


def test_configuracion_ventana_es_inmutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        CONFIGURACION.presentes_para_recuperar = 1
