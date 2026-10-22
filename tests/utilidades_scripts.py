"""Ayudas compartidas para probar los scripts del harness como programas."""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SEGUNDOS_MAXIMOS = 60


def ejecutar_script(
    nombre: str, *argumentos: str, carpeta: Path = RAIZ
) -> subprocess.CompletedProcess[str]:
    """Corre scripts/<nombre> con el mismo intérprete de la suite, desde `carpeta`."""
    # S603: ejecuta un script propio del repositorio; los argumentos no vienen de fuera.
    return subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / nombre), *argumentos],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=carpeta,
    )
