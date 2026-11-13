"""Arranque de la app en el equipo del cliente con los avisos configurados (SPEC/10 F-08, T-13)."""

import re
import ssl

from src.alerts.configuracion import (
    configuracion_email,
    configuracion_webhook,
    datos_de_la_persona,
)
from src.alerts.domain.mensaje import DatosDeLaPersona
from tests.utilidades_scripts import RAIZ

ARRANQUE = RAIZ / "scripts" / "arranque_cliente.bat"
VARIABLE_EN_CODIGO = re.compile(r'"(EPP_[A-Z_]+)"')
ASIGNACION = re.compile(r'^(?:rem )?set "(EPP_[A-Z_]+)=(.*)"$', re.MULTILINE)
EJECUTABLE = "OficinaEficiencia_VMS.exe"
PUERTO_STARTTLS = 587


def _variables_que_lee_la_app() -> set[str]:
    return {
        variable
        for archivo in RAIZ.glob("src/**/*.py")
        for variable in VARIABLE_EN_CODIGO.findall(archivo.read_text(encoding="utf-8"))
    }


def test_el_arranque_nombra_exactamente_las_variables_que_lee_la_app() -> None:
    asignadas = {nombre for nombre, _valor in ASIGNACION.findall(ARRANQUE.read_text("utf-8"))}

    assert asignadas == _variables_que_lee_la_app()


def test_la_plantilla_no_trae_secretos_ni_destinatarios_reales() -> None:
    valores = dict(ASIGNACION.findall(ARRANQUE.read_text("utf-8")))

    assert valores["EPP_ALERTAS_SMTP_CONTRASENA"] == ""
    assert valores["EPP_ALERTAS_WEBHOOK_SECRETO"] == ""
    assert "@" not in valores["EPP_ALERTAS_SMTP_DESTINATARIOS"].replace("@ejemplo.com", "")


def test_el_arranque_abre_el_ejecutable_instalado_junto_a_el() -> None:
    lineas = ARRANQUE.read_text("utf-8").splitlines()

    assert lineas[-1] == f'start "" "%~dp0{EJECUTABLE}"'
    assert f'#define MyAppExeName "{EJECUTABLE}"' in (RAIZ / "setup_oficina.iss").read_text("utf-8")


def test_el_modo_sombra_viene_encendido_para_los_primeros_dias() -> None:
    valores = dict(ASIGNACION.findall(ARRANQUE.read_text("utf-8")))

    assert valores["EPP_MODO_SOMBRA"] == "1"


def test_al_completar_el_servidor_la_plantilla_ya_es_una_configuracion_de_correo_valida() -> None:
    valores = dict(ASIGNACION.findall(ARRANQUE.read_text("utf-8")))
    entorno = {**valores, "EPP_ALERTAS_SMTP_SERVIDOR": "smtp.ejemplo.com"}

    correo = configuracion_email(entorno, ssl.create_default_context())

    assert correo is not None
    assert (correo.servidor, correo.puerto) == ("smtp.ejemplo.com", PUERTO_STARTTLS)
    assert correo.destinatarios == ("seguridad@ejemplo.com",)
    assert datos_de_la_persona(entorno) is DatosDeLaPersona.NOMBRE


def test_sin_completar_nada_no_hay_canales_de_aviso() -> None:
    valores = dict(ASIGNACION.findall(ARRANQUE.read_text("utf-8")))

    assert configuracion_email(valores, ssl.create_default_context()) is None
    assert configuracion_webhook(valores, ssl.create_default_context()) is None
