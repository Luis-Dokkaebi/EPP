"""Genera THIRD_PARTY_NOTICES.txt desde pip-licenses y models/manifest.json (SPEC/9 §1.12).

Apache-2.0 y otras licencias permisivas exigen conservar sus avisos de atribución. La entrada
debe venir del entorno de runtime (el del ejecutable), no del de desarrollo; en CI la genera el
job `licencias`.

Uso: pip-licenses --from=mixed --format=json --with-license-file --with-notice-file \\
         --no-license-path > paquetes.json
     python scripts/generar_avisos_terceros.py --paquetes paquetes.json \\
         [--manifiesto models/manifest.json] --salida docs/legal/THIRD_PARTY_NOTICES.txt
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

DESCONOCIDO = "UNKNOWN"  # lo que escribe pip-licenses cuando el paquete no trae el archivo
SIN_TEXTO = "(El paquete no incluye el texto de su licencia: revisar a mano.)"
SEPARADOR = "-" * 72
ENCABEZADO = (
    "AVISOS DE TERCEROS\n"
    "Generado por scripts/generar_avisos_terceros.py; no editar a mano.\n"
    "No es asesoría legal: requiere la revisión de la decisión D9.\n"
)


def aviso_de_paquete(paquete: Mapping[str, str]) -> str:
    aviso = paquete.get("NoticeText", DESCONOCIDO)
    licencia = paquete.get("LicenseText", DESCONOCIDO)
    textos = [aviso] if aviso != DESCONOCIDO else []
    textos.append(licencia if licencia != DESCONOCIDO else SIN_TEXTO)
    cuerpo = "\n\n".join(texto.rstrip("\n") for texto in textos)
    return f"{paquete['Name']} {paquete['Version']}\nLicencia: {paquete['License']}\n\n{cuerpo}\n"


def aviso_de_modelo(modelo: Mapping[str, Any]) -> str:
    datasets = ", ".join(f"{d['nombre']} ({d['licencia']})" for d in modelo["datasets"])
    return (
        f"{modelo['nombre']} {modelo['version']} ({modelo['archivo']})\n"
        f"Licencia de los pesos: {modelo['licencia_pesos']}\n"
        f"Licencia del código de entrenamiento: {modelo['licencia_codigo_entrenamiento']}\n"
        f"Datasets: {datasets}\n"
        f"Origen: {modelo['origen']}\n"
    )


def generar_avisos(paquetes: Sequence[Mapping[str, str]], manifiesto: Mapping[str, Any]) -> str:
    ordenados = sorted(paquetes, key=lambda paquete: paquete["Name"].lower())
    secciones = [
        ENCABEZADO,
        "== Paquetes de Python ==\n",
        *(f"{SEPARADOR}\n{aviso_de_paquete(paquete)}" for paquete in ordenados),
        "== Modelos ==\n",
        *(f"{SEPARADOR}\n{aviso_de_modelo(modelo)}" for modelo in manifiesto["modelos"]),
    ]
    return "\n".join(secciones)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paquetes", type=Path, required=True)
    parser.add_argument("--manifiesto", type=Path, default=Path("models/manifest.json"))
    parser.add_argument("--salida", type=Path, required=True)
    argumentos = parser.parse_args(argv)
    paquetes = json.loads(argumentos.paquetes.read_text(encoding="utf-8"))
    manifiesto = json.loads(argumentos.manifiesto.read_text(encoding="utf-8"))
    argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.salida.write_text(generar_avisos(paquetes, manifiesto), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
