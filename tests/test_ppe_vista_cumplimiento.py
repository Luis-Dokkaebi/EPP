"""Cómo se muestra el cumplimiento de cada persona en el video (SPEC/9 §8.1).

Verde si cumple, rojo si le falta un elemento exigido (ausencia ya confirmada por la ventana
temporal) y gris si algo exigido no se puede verificar. Una etiqueta por elemento exigido.
"""

import pytest

from src.ppe.application.evaluar_cumplimiento import EstadoCumplimiento
from src.ppe.application.vista_cumplimiento import SituacionVisual, VistaPersona, vista_de
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento

CASCO = ElementoEPP.CASCO
CHALECO = ElementoEPP.CHALECO
PRESENTE = EstadoElemento.PRESENTE
AUSENTE = EstadoElemento.AUSENTE
NO_VERIFICABLE = EstadoElemento.NO_VERIFICABLE


def _estado(
    estados: dict[ElementoEPP, EstadoElemento], exigidos: frozenset[ElementoEPP]
) -> EstadoCumplimiento:
    return EstadoCumplimiento(track_id=1, estados=estados, exigidos=exigidos)


@pytest.mark.parametrize(
    ("estados", "situacion", "etiquetas"),
    [
        ({CASCO: PRESENTE, CHALECO: PRESENTE}, SituacionVisual.CUMPLE, ("Casco", "Chaleco")),
        (
            {CASCO: AUSENTE, CHALECO: PRESENTE},
            SituacionVisual.INFRACCION,
            ("Sin casco", "Chaleco"),
        ),
        (
            {CASCO: NO_VERIFICABLE, CHALECO: PRESENTE},
            SituacionVisual.NO_VERIFICABLE,
            ("Casco ?", "Chaleco"),
        ),
        (
            {CASCO: NO_VERIFICABLE, CHALECO: AUSENTE},
            SituacionVisual.INFRACCION,
            ("Casco ?", "Sin chaleco"),
        ),
    ],
    ids=["cumple", "falta-uno", "no-verificable", "falta-uno-y-otro-no-verificable"],
)
def test_vista_colorea_y_rotula_segun_lo_exigido(
    estados: dict[ElementoEPP, EstadoElemento],
    situacion: SituacionVisual,
    etiquetas: tuple[str, ...],
) -> None:
    vista = vista_de(_estado(estados, frozenset({CASCO, CHALECO})))

    assert vista == VistaPersona(situacion, etiquetas)


def test_vista_ignora_lo_que_no_se_exige() -> None:
    estados = {CASCO: PRESENTE, CHALECO: AUSENTE, ElementoEPP.GUANTES: NO_VERIFICABLE}

    vista = vista_de(_estado(estados, frozenset({CASCO})))

    assert vista == VistaPersona(SituacionVisual.CUMPLE, ("Casco",))


def test_vista_sin_nada_exigido_cumple_y_no_lleva_etiquetas() -> None:
    vista = vista_de(_estado({CASCO: AUSENTE}, frozenset()))

    assert vista == VistaPersona(SituacionVisual.CUMPLE, ())


def test_vista_ordena_las_etiquetas_como_la_lista_de_elementos() -> None:
    exigidos = frozenset(ElementoEPP)
    estados = dict.fromkeys(ElementoEPP, PRESENTE)

    vista = vista_de(_estado(estados, exigidos))

    assert vista.etiquetas == ("Casco", "Chaleco", "Guantes", "Gafas", "Barbijo")


@pytest.mark.parametrize(
    ("situacion", "texto"),
    [
        (SituacionVisual.CUMPLE, "cumple"),
        (SituacionVisual.INFRACCION, "infracción"),
        (SituacionVisual.NO_VERIFICABLE, "no verificable"),
    ],
)
def test_situacion_visual_tiene_texto_para_el_usuario(
    situacion: SituacionVisual, texto: str
) -> None:
    assert SituacionVisual(texto) is situacion
