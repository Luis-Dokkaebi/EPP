"""Revalidación de la licencia con la app abierta (SPEC/10 §4.2, regla 3).

Una app que corre 24/7 nunca volvía a mirar su licencia. La guardia la revalida cada vez que
se le pide (la interfaz lo hace cada hora): si dejó de regir, la app se suspende sin borrar nada
y pide una licencia; si el usuario no la activa, la app se cierra.
"""

from typing import Protocol


class LicenciaRevalidable(Protocol):
    def validate_license(self) -> bool: ...


class AppVigilada(Protocol):
    def suspender(self) -> None:
        """Detiene las cámaras y los avisos; conserva rostros, zonas e historial."""

    def pedir_licencia(self) -> bool:
        """Muestra la ventana de activación; True si se activó una licencia."""

    def reanudar(self) -> None: ...

    def cerrar(self) -> None: ...


class GuardiaDeLicencia:
    def __init__(self, licencia: LicenciaRevalidable, app: AppVigilada) -> None:
        self._licencia = licencia
        self._app = app

    def revisar(self) -> bool:
        """True si la app sigue funcionando tras revalidar la licencia."""
        if self._licencia.validate_license():
            return True
        self._app.suspender()
        if self._app.pedir_licencia():
            self._app.reanudar()
            return True
        self._app.cerrar()
        return False


class RevalidacionPeriodica:
    """Para un bucle sin temporizadores (modo sin interfaz): revalida una vez por intervalo."""

    def __init__(self, licencia: LicenciaRevalidable, intervalo_s: float, ahora: float) -> None:
        self._licencia = licencia
        self._intervalo_s = intervalo_s
        self._proxima = ahora + intervalo_s
        self._regia = licencia.validate_license()

    def dejo_de_regir(self, ahora: float) -> bool:
        """True cuando la licencia que regía al empezar ya no rige en la revalidación."""
        if not self._regia or ahora < self._proxima:
            return False
        self._proxima = ahora + self._intervalo_s
        return not self._licencia.validate_license()
