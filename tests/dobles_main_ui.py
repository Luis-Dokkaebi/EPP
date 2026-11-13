"""Dobles de la ventana principal (`src/main_ui.py`): escaneo, cámaras, licencia y avisos."""

import queue
import threading
from collections.abc import Callable
from datetime import timedelta

Camaras = list[dict[str, object]]

DIAS_DE_PRUEBA_RESTANTES = 9


class EscaneoEnHiloFalso:
    """Doble de `enumerate_cameras_async`: entrega las cámaras desde un hilo de fondo.

    El hilo espera a que la prueba lo libere, así la entrega ocurre mientras el hilo
    principal no está dentro de Tk y la prueba es determinista.
    """

    def __init__(self, camaras: Camaras) -> None:
        self._camaras = camaras
        self._liberar = threading.Event()
        self._hilo: threading.Thread | None = None
        self.max_index: int | None = None

    def __call__(self, callback: Callable[[Camaras], None], max_index: int) -> threading.Thread:
        def entregar_resultado() -> None:
            self._liberar.wait()
            callback(self._camaras)

        self.max_index = max_index
        self._hilo = threading.Thread(target=entregar_resultado, daemon=True)
        self._hilo.start()
        return self._hilo

    def terminar(self) -> None:
        self._liberar.set()
        assert self._hilo is not None, "AppMain no lanzó el escaneo de cámaras"
        self._hilo.join()


class TrabajadorDeCamaraFalso:
    """Doble de `CameraWorker`: registra la cámara que se le pide sin abrir dispositivos."""

    def __init__(
        self, camara: object, cola: queue.Queue[object], modelo: object, fps_limit: int
    ) -> None:
        self.camara = camara
        self.fps_limit = fps_limit
        self.iniciado = False
        self.modulos_epp: list[object] = []

    def conectar_epp(self, modulo_epp: object) -> None:
        self.modulos_epp.append(modulo_epp)

    def start(self) -> None:
        self.iniciado = True

    def stop(self) -> None:
        self.iniciado = False


class FabricaDeTrabajadoresFalsa:
    """Reemplaza a la clase `CameraWorker` y conserva los trabajadores que creó la app."""

    def __init__(self) -> None:
        self.creados: list[TrabajadorDeCamaraFalso] = []

    def __call__(
        self, camara: object, cola: queue.Queue[object], modelo: object, fps_limit: int
    ) -> TrabajadorDeCamaraFalso:
        trabajador = TrabajadorDeCamaraFalso(camara, cola, modelo, fps_limit)
        self.creados.append(trabajador)
        return trabajador

    def camaras_iniciadas(self) -> list[object]:
        return [trabajador.camara for trabajador in self.creados if trabajador.iniciado]


class LicenciaConEPP:
    """Doble de la licencia DRM: una prueba vigente con el módulo de EPP."""

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo == "epp"

    def es_prueba(self) -> bool:
        return True

    def dias_restantes(self) -> int | None:
        return DIAS_DE_PRUEBA_RESTANTES

    def validate_license(self) -> bool:
        return True


class LicenciaConEficiencia(LicenciaConEPP):
    def incluye_modulo(self, modulo: str) -> bool:
        return modulo == "eficiencia"


class DespachadorFalso:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def iniciar(self) -> None:
        self.eventos.append("iniciar")

    def detener(self, espera_maxima: timedelta) -> None:
        self.eventos.append(f"detener {espera_maxima.total_seconds():.0f} s")
