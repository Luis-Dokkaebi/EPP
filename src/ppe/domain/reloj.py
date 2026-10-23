"""Puerto del reloj (SPEC/9 §4.2): el dominio nunca lee la hora del sistema por su cuenta."""

from datetime import datetime
from typing import Protocol


class RelojPort(Protocol):
    """Fuente del instante actual; en producción, un adaptador; en las pruebas, un reloj falso."""

    def ahora(self) -> datetime:
        """Instante actual. Debe ser monótono: retroceder es un error del reloj."""
        ...
