"""Presentador del panel "Alertas EPP" (SPEC/9 §8.2): toda la lógica, sin Tk.

La vista solo muestra `filas` y `zonas` y llama a los comandos del presentador.
"""

from datetime import UTC, timedelta, timezone

import pytest

from src.alerts.domain.aviso import EstadoNotificacion
from src.gui.presentador_alertas import (
    TODAS_LAS_ZONAS,
    FilaAlerta,
    PreferenciasPanel,
    PresentadorAlertas,
)
from tests.dobles_alertas import RepositorioAlertasFalso, alerta_registrada
from tests.dobles_ppe import INICIO, RelojFalso

ARGENTINA = timezone(timedelta(hours=-3))
PREFERENCIAS = PreferenciasPanel(usuario="Supervisora", zona_horaria=ARGENTINA, limite=50)


def _presentador(repositorio: RepositorioAlertasFalso) -> PresentadorAlertas:
    presentador = PresentadorAlertas(repositorio, RelojFalso(), PREFERENCIAS)
    presentador.actualizar()
    return presentador


def test_presentador_muestra_cada_alerta_con_sus_datos_en_hora_local() -> None:
    presentador = _presentador(RepositorioAlertasFalso(alerta_registrada(1)))

    assert presentador.filas == [
        FilaAlerta(
            id_infraccion=1,
            miniatura="ev/1.jpg",
            persona="Ana",
            zona="Boca de pozo",
            elemento="casco",
            hora="22/10 05:00:00",
            aviso="Aviso pendiente",
            recibido=None,
        )
    ]


@pytest.mark.parametrize(
    ("estado", "texto"),
    [
        (EstadoNotificacion.PENDIENTE, "Aviso pendiente"),
        (EstadoNotificacion.ENVIADA, "Aviso enviado"),
        (EstadoNotificacion.FALLIDA, "Aviso fallido"),
    ],
)
def test_presentador_traduce_el_estado_del_aviso(estado: EstadoNotificacion, texto: str) -> None:
    presentador = _presentador(RepositorioAlertasFalso(alerta_registrada(1, estado=estado)))

    assert presentador.filas[0].aviso == texto


def test_presentador_nombra_a_la_persona_no_identificada() -> None:
    presentador = _presentador(RepositorioAlertasFalso(alerta_registrada(1, persona=None)))

    assert presentador.filas[0].persona == "persona no identificada"


def test_presentador_consulta_todas_las_zonas_con_el_limite_configurado() -> None:
    repositorio = RepositorioAlertasFalso(alerta_registrada(1))

    _presentador(repositorio)

    assert repositorio.consultas == [(None, 50)]


def test_presentador_ofrece_filtrar_por_cada_zona_con_alertas() -> None:
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1), alerta_registrada(2, zona="Playa de tanques")
    )

    presentador = _presentador(repositorio)

    assert presentador.zonas == [TODAS_LAS_ZONAS, "Boca de pozo", "Playa de tanques"]
    assert TODAS_LAS_ZONAS == "Todas las zonas"


def test_presentador_filtrar_por_zona_muestra_solo_esa_zona() -> None:
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1), alerta_registrada(2, zona="Playa de tanques")
    )
    presentador = _presentador(repositorio)

    presentador.filtrar_por_zona("Playa de tanques")

    assert [fila.id_infraccion for fila in presentador.filas] == [2]
    assert presentador.zona_filtrada == "Playa de tanques"


def test_presentador_volver_a_todas_las_zonas_quita_el_filtro() -> None:
    repositorio = RepositorioAlertasFalso(
        alerta_registrada(1), alerta_registrada(2, zona="Playa de tanques")
    )
    presentador = _presentador(repositorio)
    presentador.filtrar_por_zona("Playa de tanques")

    presentador.filtrar_por_zona(TODAS_LAS_ZONAS)

    assert [fila.id_infraccion for fila in presentador.filas] == [1, 2]
    assert repositorio.consultas[-1] == (None, 50)


def test_presentador_marcar_recibido_guarda_el_acuse_y_lo_muestra() -> None:
    repositorio = RepositorioAlertasFalso(alerta_registrada(1))
    presentador = _presentador(repositorio)

    presentador.marcar_recibido(1)

    assert repositorio.acuses == [(1, "Supervisora", INICIO)]
    assert presentador.filas[0].recibido == "Recibido por Supervisora a las 05:00"
    assert presentador.mensaje is None


def test_presentador_un_acuse_ya_dado_por_otro_se_informa_sin_romper_el_panel() -> None:
    otro = alerta_registrada(1)._replace(
        reconocida_por="Jefe", reconocida_en=INICIO + timedelta(hours=1)
    )
    presentador = _presentador(RepositorioAlertasFalso(otro))

    presentador.marcar_recibido(1)

    assert presentador.mensaje == "La alerta 1 ya tenía acuse de recibo"
    assert presentador.filas[0].recibido == "Recibido por Jefe a las 06:00"


def test_presentador_el_mensaje_se_borra_al_volver_a_actualizar() -> None:
    otro = alerta_registrada(1)._replace(reconocida_por="Jefe", reconocida_en=INICIO)
    presentador = _presentador(RepositorioAlertasFalso(otro))
    presentador.marcar_recibido(1)

    presentador.actualizar()

    assert presentador.mensaje is None


def test_presentador_antes_de_actualizar_no_muestra_nada() -> None:
    presentador = PresentadorAlertas(
        RepositorioAlertasFalso(alerta_registrada(1)), RelojFalso(), PREFERENCIAS
    )

    assert (presentador.filas, presentador.zonas) == ([], [TODAS_LAS_ZONAS])
    assert presentador.mensaje is None


def test_preferencias_rechazan_un_limite_menor_que_uno() -> None:
    preferencias = PREFERENCIAS._replace(limite=0)

    with pytest.raises(ValueError, match=r"^El panel debe mostrar al menos una alerta: 0$"):
        PresentadorAlertas(RepositorioAlertasFalso(), RelojFalso(), preferencias)


def test_preferencias_aceptan_mostrar_una_solaalerta_registrada() -> None:
    repositorio = RepositorioAlertasFalso(alerta_registrada(1), alerta_registrada(2))
    presentador = PresentadorAlertas(repositorio, RelojFalso(), PREFERENCIAS._replace(limite=1))

    presentador.actualizar()

    assert [fila.id_infraccion for fila in presentador.filas] == [1]


def test_la_hora_del_panel_usa_la_zona_horaria_configurada() -> None:
    preferencias = PREFERENCIAS._replace(zona_horaria=UTC)
    presentador = PresentadorAlertas(
        RepositorioAlertasFalso(alerta_registrada(1)), RelojFalso(), preferencias
    )

    presentador.actualizar()

    assert presentador.filas[0].hora == "22/10 08:00:00"
