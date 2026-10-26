"""Buzón que lleva al hilo de la interfaz lo que piden los hilos de trabajo.

Tk solo admite llamadas desde el hilo que lo creó: dibujar un widget desde otro hilo cierra la
aplicación. El hilo de trabajo publica la acción y el hilo de la interfaz la ejecuta al
revisar el buzón, que se reprograma solo con `widget.after`.
"""

import queue
from collections.abc import Callable


class BuzonHiloUI:
    def __init__(
        self, programar: Callable[[int, Callable[[], None]], object], intervalo_ms: int
    ) -> None:
        if intervalo_ms <= 0:
            raise ValueError(f"El intervalo debe ser positivo: {intervalo_ms} ms.")
        self._programar = programar
        self._intervalo_ms = intervalo_ms
        self._acciones: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()

    def publicar(self, accion: Callable[[], None]) -> None:
        """Seguro desde cualquier hilo: la acción espera a que el hilo de la interfaz atienda."""
        self._acciones.put(accion)

    def pendientes(self) -> int:
        return self._acciones.qsize()

    def atender(self) -> None:
        """Ejecuta, en el hilo que llama, todo lo publicado hasta ahora."""
        while not self._acciones.empty():
            self._acciones.get()()

    def vigilar(self) -> None:
        """Atiende y se vuelve a programar; se reprograma antes por si una acción falla."""
        self._programar(self._intervalo_ms, self.vigilar)
        self.atender()
