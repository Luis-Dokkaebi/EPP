"""Presentador del dibujo de zonas dentro de la aplicación (SPEC/9 §8.3): toda la lógica, sin Tk.

El usuario toma una foto de la cámara activa, la ve reducida para que entre en la pantalla y
marca las esquinas con clics. Los puntos se guardan en píxeles de la cámara (los que usa
ZoneChecker): cada clic se divide por la escala de la vista y se ajusta al borde de la foto. Al
guardar o borrar una zona avisa con `al_cambiar_zonas`, para que la vista del EPP exigido se
recargue.
"""

from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np

from src.ppe.domain.errores import ZonaSinPoligonoError
from src.ppe.domain.reglas import VERTICES_MINIMOS, ReglaZona
from src.zones.edicion_zonas import (
    NombreDeZonaInvalidoError,
    PoligonoInvalidoError,
    ZonaInexistenteError,
    borrar_zona,
    guardar_poligono,
)
from src.zones.formato_zonas import FormatoZonasError, leer_zonas

Punto = tuple[int, int]
PuntoEnVista = tuple[float, float]

SIN_IMAGEN = "Todavía no hay imagen de la cámara: conéctela y espere a ver el video"
SIN_FOTO = "Primero tome una foto de la cámara"
MARCAR = "Haga clic en cada esquina de la zona"
FALTAN_ESQUINAS = f"Marque al menos {VERTICES_MINIMOS} esquinas antes de guardar"


class PresentadorDibujoZonas:
    """Estado y comandos del dibujo de zonas sobre una foto de la cámara."""

    foto: np.ndarray | None
    puntos: list[Punto]
    mensaje: str | None
    _zonas: tuple[ReglaZona, ...]

    def __init__(
        self,
        ruta: Path,
        tomar_cuadro: Callable[[], np.ndarray | None],
        vista_maxima: tuple[int, int],
        al_cambiar_zonas: Callable[[], None],
    ) -> None:
        if min(vista_maxima) < 1:
            raise ValueError(f"La vista debe medir al menos 1 x 1 píxeles: {vista_maxima}")
        self._ruta = ruta
        self._tomar_cuadro = tomar_cuadro
        self._vista_maxima = vista_maxima
        self._al_cambiar_zonas = al_cambiar_zonas
        self.foto = None
        self.puntos = []
        self.mensaje = None
        self._zonas = ()

    @property
    def escala(self) -> float:
        """Cuánto se reduce la foto para entrar en la vista; nunca se agranda."""
        if self.foto is None:
            return 1.0
        alto, ancho = self.foto.shape[:2]
        ancho_maximo, alto_maximo = self._vista_maxima
        return min(ancho_maximo / ancho, alto_maximo / alto, 1.0)

    @property
    def tamano_vista(self) -> tuple[int, int]:
        if self.foto is None:
            return self._vista_maxima
        alto, ancho = self.foto.shape[:2]
        return round(ancho * self.escala), round(alto * self.escala)

    @property
    def zonas(self) -> list[str]:
        return [zona.nombre for zona in self._zonas]

    @property
    def puntos_en_vista(self) -> list[PuntoEnVista]:
        return self._en_vista(self.puntos)

    @property
    def poligonos_en_vista(self) -> dict[str, list[PuntoEnVista]]:
        return {zona.nombre: self._en_vista(zona.poligono) for zona in self._zonas}

    def cargar(self) -> None:
        """Lee las zonas guardadas para listarlas y dibujarlas sobre la foto."""
        try:
            self._zonas = leer_zonas(self._ruta)
        except FormatoZonasError as error:
            self._zonas = ()
            self.mensaje = f"No se pudo leer el archivo de zonas: {error}"

    def tomar_foto(self) -> None:
        cuadro = self._tomar_cuadro()
        if cuadro is None:
            self.mensaje = SIN_IMAGEN
            return
        self.foto = cuadro
        self.puntos = []
        self.mensaje = MARCAR

    def agregar_punto(self, x_vista: float, y_vista: float) -> None:
        if self.foto is None:
            self.mensaje = SIN_FOTO
            return
        alto, ancho = self.foto.shape[:2]
        x = _ajustar(round(x_vista / self.escala), ancho - 1)
        y = _ajustar(round(y_vista / self.escala), alto - 1)
        self.puntos.append((x, y))

    def deshacer(self) -> None:
        if self.puntos:
            self.puntos.pop()

    def limpiar(self) -> None:
        self.puntos = []

    def guardar(self, nombre: str) -> None:
        nombre = nombre.strip()
        if len(self.puntos) < VERTICES_MINIMOS:
            self.mensaje = FALTAN_ESQUINAS
            return
        try:
            guardar_poligono(self._ruta, nombre, self.puntos)
        except (NombreDeZonaInvalidoError, PoligonoInvalidoError, ZonaSinPoligonoError) as error:
            self.mensaje = str(error)
            return
        except (FormatoZonasError, OSError) as error:
            self.mensaje = f"No se pudo guardar la zona: {error}"
            return
        self.puntos = []
        self._recargar(
            f"Zona '{nombre}' guardada. Marque su EPP abajo; rige al reconectar la cámara."
        )

    def borrar(self, nombre: str) -> None:
        try:
            borrar_zona(self._ruta, nombre)
        except (ZonaInexistenteError, FormatoZonasError, OSError) as error:
            self.mensaje = f"No se pudo borrar la zona: {error}"
            return
        self._recargar(f"Zona '{nombre}' borrada")

    def _recargar(self, mensaje: str) -> None:
        self.cargar()
        self.mensaje = mensaje
        self._al_cambiar_zonas()

    def _en_vista(self, puntos: Iterable[tuple[float, float]]) -> list[PuntoEnVista]:
        escala = self.escala
        return [(x * escala, y * escala) for x, y in puntos]


def _ajustar(valor: int, maximo: int) -> int:
    return max(0, min(valor, maximo))
