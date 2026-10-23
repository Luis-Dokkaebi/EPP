"""Aviso por varios canales a la vez (D1: email y webhook; SPEC/9 §7.1).

Si un canal falla, el aviso cuenta como no entregado y el despachador lo reintenta; en el
reintento solo se vuelve a usar el canal que falló, para no duplicar el aviso en el otro.
"""

import pytest

from src.alerts.canales import CanalesDeAviso
from src.alerts.domain.errores import ConfiguracionAlertasError, NotificacionFallidaError
from tests.dobles_alertas import CanalFalso, aviso


def test_canales_entregan_el_aviso_por_todos() -> None:
    email, webhook = CanalFalso([True]), CanalFalso([True])
    canales = CanalesDeAviso({"email": email, "webhook": webhook})

    canales.enviar(aviso(7))

    assert (email.intentos, webhook.intentos) == ([7], [7])


def test_canales_informan_sus_nombres_en_orden_de_uso() -> None:
    canales = CanalesDeAviso({"email": CanalFalso([]), "webhook": CanalFalso([])})

    assert canales.nombres == ("email", "webhook")


def test_canales_una_falla_parcial_se_informa_con_el_canal_que_fallo() -> None:
    canales = CanalesDeAviso({"email": CanalFalso([True]), "webhook": CanalFalso([False])})

    with pytest.raises(
        NotificacionFallidaError, match=r"^webhook: canal caído al enviar el aviso 7$"
    ):
        canales.enviar(aviso(7))


def test_canales_todas_las_fallas_se_informan_juntas() -> None:
    canales = CanalesDeAviso({"email": CanalFalso([False]), "webhook": CanalFalso([False])})

    with pytest.raises(
        NotificacionFallidaError,
        match=r"^email: canal caído al enviar el aviso 7; "
        r"webhook: canal caído al enviar el aviso 7$",
    ):
        canales.enviar(aviso(7))


def test_canales_el_reintento_solo_usa_los_canales_que_fallaron() -> None:
    email, webhook = CanalFalso([True]), CanalFalso([False, True])
    canales = CanalesDeAviso({"email": email, "webhook": webhook})
    with pytest.raises(NotificacionFallidaError):
        canales.enviar(aviso(7))

    canales.enviar(aviso(7, intentos=1))

    assert (email.intentos, webhook.intentos) == ([7], [7, 7])


def test_canales_un_aviso_entregado_se_olvida_y_otro_aviso_usa_todos() -> None:
    email, webhook = CanalFalso([True, True]), CanalFalso([False, True, True])
    canales = CanalesDeAviso({"email": email, "webhook": webhook})
    with pytest.raises(NotificacionFallidaError):
        canales.enviar(aviso(7))
    canales.enviar(aviso(7, intentos=1))

    canales.enviar(aviso(8))

    assert (email.intentos, webhook.intentos) == ([7, 8], [7, 7, 8])
    assert canales.entregas_parciales == {}


def test_canales_recuerda_que_canal_ya_entrego_un_aviso_pendiente() -> None:
    canales = CanalesDeAviso({"email": CanalFalso([True]), "webhook": CanalFalso([False])})
    with pytest.raises(NotificacionFallidaError):
        canales.enviar(aviso(7))

    assert canales.entregas_parciales == {7: frozenset({"email"})}


def test_canales_sin_ningun_canal_es_un_error_de_configuracion() -> None:
    with pytest.raises(
        ConfiguracionAlertasError,
        match=r"^No hay ningún canal de aviso configurado \(D1: email y webhook\)$",
    ):
        CanalesDeAviso({})
