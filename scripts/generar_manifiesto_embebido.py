"""Genera src/models/manifiesto_aprobado.py desde models/manifest.json (SPEC/9 §1.8).

El ejecutable no lee models/manifest.json: los hashes aprobados viajan en código, que PyArmor
ofusca en producción como hoy el hash fijo de TASK-5.2. Así, editar el manifiesto en disco no
habilita un modelo nuevo; tests/test_model_verifier_manifiesto.py exige que ambos coincidan.

Uso: python scripts/generar_manifiesto_embebido.py
"""

import json
import sys
from pathlib import Path
from typing import Any

MANIFIESTO = Path("models/manifest.json")
DESTINO = Path("src/models/manifiesto_aprobado.py")
ENCABEZADO = '''"""Modelos aprobados (archivo -> sha256), generado desde models/manifest.json.

No editar a mano: python scripts/generar_manifiesto_embebido.py (SPEC/9 §1.8).
"""

MODELOS_APROBADOS: dict[str, str] = {
'''


def generar_modulo(manifiesto: dict[str, Any]) -> str:
    """Código del módulo con una entrada por modelo, ordenadas por archivo."""
    entradas = sorted(manifiesto["modelos"], key=lambda entrada: entrada["archivo"])
    filas = "".join(
        "    # pragma: allowlist nextline secret\n"
        f'    "{entrada["archivo"]}": "{entrada["sha256"]}",\n'
        for entrada in entradas
    )
    return f"{ENCABEZADO}{filas}}}\n"


def main() -> int:
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    DESTINO.write_text(generar_modulo(manifiesto), encoding="utf-8")
    sys.stdout.write(f"{DESTINO} regenerado con {len(manifiesto['modelos'])} modelo(s).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
