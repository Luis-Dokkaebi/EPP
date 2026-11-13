"""Revalidación de la licencia con la app abierta (SPEC/10 §4.2 regla 3, T-05)."""

import pytest

from src.security.guardia_licencia import GuardiaDeLicencia, RevalidacionPeriodica


class LicenciaFalsa:
    def __init__(self, *vigencias: bool) -> None:
        self._vigencias = list(vigencias)

    def validate_license(self) -> bool:
        return self._vigencias.pop(0)


class AppFalsa:
    """Anota lo que la guardia le pide; `activa` es si el usuario pega una licencia nueva."""

    def __init__(self, activa: bool) -> None:
        self._activa = activa
        self.pasos: list[str] = []

    def suspender(self) -> None:
        self.pasos.append("suspender")

    def pedir_licencia(self) -> bool:
        self.pasos.append("pedir_licencia")
        return self._activa

    def reanudar(self) -> None:
        self.pasos.append("reanudar")

    def cerrar(self) -> None:
        self.pasos.append("cerrar")


def test_con_la_licencia_vigente_la_app_sigue_sin_interrupciones() -> None:
    app = AppFalsa(activa=False)

    sigue = GuardiaDeLicencia(LicenciaFalsa(True), app).revisar()

    assert sigue is True
    assert app.pasos == []


def test_al_vencer_se_suspende_y_se_pide_una_licencia_antes_de_cerrar() -> None:
    app = AppFalsa(activa=False)

    sigue = GuardiaDeLicencia(LicenciaFalsa(False), app).revisar()

    assert sigue is False
    assert app.pasos == ["suspender", "pedir_licencia", "cerrar"]


def test_si_se_activa_una_licencia_nueva_la_app_se_reanuda() -> None:
    app = AppFalsa(activa=True)

    sigue = GuardiaDeLicencia(LicenciaFalsa(False), app).revisar()

    assert sigue is True
    assert app.pasos == ["suspender", "pedir_licencia", "reanudar"]


@pytest.mark.parametrize("revisiones", [1, 3])
def test_cada_revision_vuelve_a_validar_la_licencia(revisiones: int) -> None:
    app = AppFalsa(activa=False)
    guardia = GuardiaDeLicencia(LicenciaFalsa(*[True] * revisiones, False), app)

    resultados = [guardia.revisar() for _ in range(revisiones + 1)]

    assert resultados == [*[True] * revisiones, False]
    assert app.pasos == ["suspender", "pedir_licencia", "cerrar"]


# --- Revalidación periódica para un bucle sin temporizadores (modo sin interfaz) --------------

HORA = 3_600.0
INICIO = 10_000.0


class LicenciaContada(LicenciaFalsa):
    def __init__(self, *vigencias: bool) -> None:
        super().__init__(*vigencias)
        self.validaciones = 0

    def validate_license(self) -> bool:
        self.validaciones += 1
        return super().validate_license()


def test_antes_de_cumplirse_el_intervalo_no_se_revalida() -> None:
    licencia = LicenciaContada(True)
    periodica = RevalidacionPeriodica(licencia, HORA, INICIO)

    assert periodica.dejo_de_regir(INICIO + HORA - 1) is False
    assert licencia.validaciones == 1


def test_al_cumplirse_el_intervalo_se_revalida_y_sigue_si_rige() -> None:
    licencia = LicenciaContada(True, True)
    periodica = RevalidacionPeriodica(licencia, HORA, INICIO)

    assert periodica.dejo_de_regir(INICIO + HORA) is False
    assert licencia.validaciones == len([True, True])


def test_una_licencia_que_regia_y_vence_se_detecta_en_la_revalidacion() -> None:
    periodica = RevalidacionPeriodica(LicenciaContada(True, False), HORA, INICIO)

    assert periodica.dejo_de_regir(INICIO + HORA) is True


def test_tras_revalidar_el_intervalo_vuelve_a_empezar() -> None:
    licencia = LicenciaContada(True, True, False)
    periodica = RevalidacionPeriodica(licencia, HORA, INICIO)
    periodica.dejo_de_regir(INICIO + HORA + 10)

    antes = periodica.dejo_de_regir(INICIO + 2 * HORA + 9)
    despues = periodica.dejo_de_regir(INICIO + 2 * HORA + 10)

    assert (antes, despues) == (False, True)


def test_sin_licencia_al_empezar_no_hay_nada_que_venza() -> None:
    licencia = LicenciaContada(False)
    periodica = RevalidacionPeriodica(licencia, HORA, INICIO)

    assert periodica.dejo_de_regir(INICIO + 5 * HORA) is False
    assert licencia.validaciones == 1
