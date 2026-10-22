"""Taxonomía de EPP, anclas corporales y estados de verificación (SPEC/9 §2.2 y §4.1)."""

import pytest

from src.ppe.domain.elementos import ElementoEPP, EstadoElemento, TipoAncla


@pytest.mark.parametrize(
    ("texto", "elemento"),
    [
        ("casco", ElementoEPP.CASCO),
        ("chaleco", ElementoEPP.CHALECO),
        ("guantes", ElementoEPP.GUANTES),
        ("gafas", ElementoEPP.GAFAS),
        ("barbijo", ElementoEPP.BARBIJO),
    ],
)
def test_elemento_epp_se_identifica_por_su_nombre_de_negocio(
    texto: str, elemento: ElementoEPP
) -> None:
    assert ElementoEPP(texto) is elemento


@pytest.mark.parametrize(
    ("elemento", "ancla"),
    [
        (ElementoEPP.CASCO, TipoAncla.CABEZA),
        (ElementoEPP.GAFAS, TipoAncla.CABEZA),
        (ElementoEPP.BARBIJO, TipoAncla.CABEZA),
        (ElementoEPP.GUANTES, TipoAncla.MANOS),
        (ElementoEPP.CHALECO, TipoAncla.TORSO),
    ],
)
def test_elemento_epp_se_verifica_sobre_su_ancla_corporal(
    elemento: ElementoEPP, ancla: TipoAncla
) -> None:
    assert elemento.ancla is ancla


@pytest.mark.parametrize(
    ("clase_del_detector", "ancla"),
    [("cabeza", TipoAncla.CABEZA), ("manos", TipoAncla.MANOS), ("torso", TipoAncla.TORSO)],
)
def test_tipo_ancla_se_identifica_por_la_clase_de_la_taxonomia(
    clase_del_detector: str, ancla: TipoAncla
) -> None:
    assert TipoAncla(clase_del_detector) is ancla


@pytest.mark.parametrize(
    ("texto", "estado"),
    [
        ("presente", EstadoElemento.PRESENTE),
        ("ausente", EstadoElemento.AUSENTE),
        ("no verificable", EstadoElemento.NO_VERIFICABLE),
    ],
)
def test_estado_elemento_se_identifica_por_su_texto_de_negocio(
    texto: str, estado: EstadoElemento
) -> None:
    assert EstadoElemento(texto) is estado


def test_estado_elemento_tiene_exactamente_los_tres_estados_del_plan() -> None:
    nombres = {estado.name for estado in EstadoElemento}

    assert nombres == {"PRESENTE", "AUSENTE", "NO_VERIFICABLE"}
