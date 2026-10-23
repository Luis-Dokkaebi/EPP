"""Texto del aviso al responsable de seguridad (SPEC/9 §4.6, §7.3).

Si el aviso nombra al empleado lo decide el negocio (D5, pendiente): la redacción lo recibe como
configuración explícita y no tiene un valor por omisión.
"""

import pytest

from src.alerts.domain.mensaje import DatosDeLaPersona, Mensaje, describir_persona, redactar
from tests.dobles_alertas import aviso


@pytest.mark.parametrize(
    ("persona", "datos", "descripcion"),
    [
        ("Ana", DatosDeLaPersona.NOMBRE, "Ana"),
        ("Ana", DatosDeLaPersona.ANONIMO, "persona identificada (nombre omitido)"),
        (None, DatosDeLaPersona.NOMBRE, "persona no identificada"),
        (None, DatosDeLaPersona.ANONIMO, "persona no identificada"),
    ],
    ids=["con-nombre", "nombre-omitido", "no-identificada", "no-identificada-anonimo"],
)
def test_describir_persona_respeta_lo_que_permite_el_negocio(
    persona: str | None, datos: DatosDeLaPersona, descripcion: str
) -> None:
    assert describir_persona(persona, datos) == descripcion


@pytest.mark.parametrize(
    ("texto", "datos"),
    [("incluir", DatosDeLaPersona.NOMBRE), ("omitir", DatosDeLaPersona.ANONIMO)],
)
def test_datos_de_la_persona_se_configuran_por_texto(texto: str, datos: DatosDeLaPersona) -> None:
    assert DatosDeLaPersona(texto) is datos


def test_redactar_arma_asunto_y_cuerpo_con_los_datos_del_aviso() -> None:
    mensaje = redactar(aviso(7, persona="Ana"), DatosDeLaPersona.NOMBRE)

    assert mensaje == Mensaje(
        asunto="EPP: Ana sin casco en Boca de pozo",
        cuerpo=(
            "Persona: Ana\n"
            "Elemento faltante: casco\n"
            "Zona: Boca de pozo\n"
            "Desde: 2026-10-22T08:00:00+00:00\n"
            "Aviso N.º 7"
        ),
    )


def test_redactar_un_aviso_anonimo_no_incluye_el_nombre() -> None:
    mensaje = redactar(aviso(7, persona="Ana"), DatosDeLaPersona.ANONIMO)

    assert "Ana" not in mensaje.asunto + mensaje.cuerpo
    assert mensaje.asunto == "EPP: persona identificada (nombre omitido) sin casco en Boca de pozo"
