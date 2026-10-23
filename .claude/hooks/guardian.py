"""Hooks de Claude Code del repositorio (SPEC/9 §0.6, CLAUDE.md §12 y §14).

Subcomandos (el JSON del evento llega por stdin):
  bash      PreToolUse/Bash: bloquea `git commit --no-verify` y `git push --force`.
  archivos  PreToolUse/Edit|Write: bloquea archivos de build y binarios salvo autorización.

Un bloqueo sale con código 2 y explica por stderr cómo seguir (Claude Code se lo muestra al
agente). Sin dependencias fuera de la biblioteca estándar: corre con cualquier python3.
"""

import argparse
import json
import os
import re
import shlex
import sys
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

CODIGO_BLOQUEO = 2
VARIABLE_AUTORIZACION = "EPP_AUTORIZA_ARCHIVOS_PROTEGIDOS"
ARCHIVOS_PROTEGIDOS = frozenset(
    {"gui_app.spec", "compilar_exe.bat", "obfuscate.py", "setup_oficina.iss"}
)
EXTENSIONES_PROTEGIDAS = frozenset({".pt", ".onnx", ".xlsx", ".whl"})
SEPARADOR_DE_COMANDOS = re.compile(r"&&|\|\||[;|&\n]")
# Opciones largas de `git commit` cuyo valor es el siguiente token (el mensaje no se analiza).
OPCIONES_LARGAS_COMMIT_CON_VALOR = frozenset(
    {"--message", "--file", "--template", "--author", "--date"}
)
# Letras de opciones cortas de `git commit` que toman un valor (-m, -F, -C, -c, -t).
LETRAS_COMMIT_CON_VALOR = frozenset("mFCct")


def _segmentos(comando: str) -> Iterator[list[str]]:
    """Subcomandos simples (separados por ;, &&, ||, |, & o salto de línea), ya tokenizados."""
    for texto in SEPARADOR_DE_COMANDOS.split(comando):
        try:
            yield shlex.split(texto, posix=True)
        except ValueError:
            yield texto.split()


def _argumentos_tras(segmento: list[str], programa: str, accion: str) -> list[str] | None:
    """Tokens que siguen a `programa accion` (p. ej. "git commit") dentro del segmento."""
    for indice, par in enumerate(pairwise(segmento)):
        if par == (programa, accion):
            return segmento[indice + 2 :]
    return None


def _primera_letra_con_valor(bandera: str) -> int | None:
    """Posición de la primera letra que toma un valor en un `-abc`, o None si no hay."""
    posiciones = (i for i, letra in enumerate(bandera) if letra in LETRAS_COMMIT_CON_VALOR)
    return next(posiciones, None)


def _bandera_corta_incluye_n(bandera: str) -> bool:
    """`-anm` incluye -n; en `-mn` la n es el texto del mensaje, no una opción."""
    hasta = _primera_letra_con_valor(bandera)
    return "n" in bandera[1:hasta]


def _bandera_corta_toma_el_siguiente(bandera: str) -> bool:
    """`-am` toma el siguiente token como valor; `-mtexto` lo lleva pegado."""
    return _primera_letra_con_valor(bandera) == len(bandera) - 1


def _commit_sin_verificar(argumentos: list[str]) -> bool:
    restantes = iter(argumentos)
    for argumento in restantes:
        es_corta = argumento.startswith("-") and not argumento.startswith("--")
        if argumento == "--no-verify" or (es_corta and _bandera_corta_incluye_n(argumento)):
            return True
        if argumento in OPCIONES_LARGAS_COMMIT_CON_VALOR or (
            es_corta and _bandera_corta_toma_el_siguiente(argumento)
        ):
            next(restantes, None)
    return False


def _motivo_de_segmento(segmento: list[str]) -> str | None:
    commit = _argumentos_tras(segmento, "git", "commit")
    if commit is not None and _commit_sin_verificar(commit):
        return "`git commit --no-verify` está prohibido (CLAUDE.md §12 y §14.9): corrige el hook."
    push = _argumentos_tras(segmento, "git", "push")
    if push is not None and {"--force", "-f"} & set(push):
        return (
            "`git push --force` está prohibido (CLAUDE.md §12): usa --force-with-lease y decláralo."
        )
    return None


def motivo_de_bloqueo_bash(comando: str) -> str | None:
    """Explicación del bloqueo, o None si el comando está permitido."""
    motivos = (_motivo_de_segmento(segmento) for segmento in _segmentos(comando))
    return next((motivo for motivo in motivos if motivo), None)


def motivo_de_bloqueo_archivo(ruta: str) -> str | None:
    """Explicación del bloqueo de un archivo de build o binario, o None si se puede editar."""
    archivo = Path(ruta)
    if archivo.name not in ARCHIVOS_PROTEGIDOS and archivo.suffix not in EXTENSIONES_PROTEGIDAS:
        return None
    return (
        f"{archivo.name} es un archivo de build o binario protegido (CLAUDE.md §14.12 y §16). "
        f"Necesita la autorización humana D8; con ella, exporta {VARIABLE_AUTORIZACION}=1."
    )


def _bloquear_si(motivo: str | None) -> int:
    if motivo is None:
        return 0
    sys.stderr.write(f"{motivo}\n")
    return CODIGO_BLOQUEO


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subcomando", choices=["bash", "archivos"])
    subcomando = parser.parse_args(argv).subcomando
    evento = json.load(sys.stdin)
    entrada = evento["tool_input"]
    if subcomando == "bash":
        return _bloquear_si(motivo_de_bloqueo_bash(entrada["command"]))
    if os.environ.get(VARIABLE_AUTORIZACION) == "1":
        return 0
    return _bloquear_si(motivo_de_bloqueo_archivo(entrada["file_path"]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
