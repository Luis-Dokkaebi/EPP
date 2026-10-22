"""Hooks de Claude Code del repositorio (SPEC/9 §0.6, CLAUDE.md §12 y §14).

Subcomandos (el JSON del evento llega por stdin):
  bash      PreToolUse/Bash: bloquea `git commit --no-verify`, `git push --force` y
            `pip install` de paquetes sin versión fijada.
  archivos  PreToolUse/Edit|Write: bloquea archivos de build y binarios salvo autorización.
  formato   PostToolUse/Edit|Write: `ruff format` + `ruff check --fix` sobre el .py editado.
  cierre    Stop: gemelos CLAUDE.md/Agents.md idénticos y pruebas unitarias rápidas.

Un bloqueo sale con código 2 y explica por stderr cómo seguir (Claude Code se lo muestra al
agente). Sin dependencias fuera de la biblioteca estándar: corre con cualquier python3.
"""

import argparse
import filecmp
import json
import os
import re
import shlex
import shutil
import subprocess
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
OPCIONES_PIP_CON_VALOR = frozenset(
    {
        "-r", "--requirement", "-c", "--constraint", "-e", "--editable", "-i", "--index-url",
        "--extra-index-url", "-f", "--find-links", "-t", "--target", "--python", "-p",
        "--index-strategy", "--prefix", "--root",
    }
)  # fmt: skip
PLAZO_PRUEBAS_RAPIDAS_S = 50
CODIGOS_PYTEST_ACEPTABLES = frozenset({0, 5})  # 5: no hay pruebas que coincidan con el filtro
CARACTERES_DE_SALIDA_DE_PRUEBAS = 2000


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


def _paquetes_sin_version(argumentos: list[str]) -> list[str]:
    restantes = iter(argumentos)
    paquetes = []
    for argumento in restantes:
        if argumento in OPCIONES_PIP_CON_VALOR:
            next(restantes, None)
        elif not argumento.startswith("-") and not _es_ruta_local(argumento):
            paquetes.append(argumento)
    return [paquete for paquete in paquetes if "==" not in paquete]


def _es_ruta_local(argumento: str) -> bool:
    return argumento.startswith((".", "/")) or argumento.endswith((".whl", ".tar.gz"))


def _motivo_de_segmento(segmento: list[str]) -> str | None:
    commit = _argumentos_tras(segmento, "git", "commit")
    if commit is not None and _commit_sin_verificar(commit):
        return "`git commit --no-verify` está prohibido (CLAUDE.md §12 y §14.9): corrige el hook."
    push = _argumentos_tras(segmento, "git", "push")
    if push is not None and {"--force", "-f"} & set(push):
        return (
            "`git push --force` está prohibido (CLAUDE.md §12): usa --force-with-lease y decláralo."
        )
    pip = _argumentos_tras(segmento, "pip", "install") or _argumentos_tras(
        segmento, "pip3", "install"
    )
    if pip and (sin_version := _paquetes_sin_version(pip)):
        return (
            f"pip install sin versión fijada ({', '.join(sin_version)}) está prohibido "
            "(CLAUDE.md §14.11): usa paquete==versión y corre pip-audit."
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


def _proyecto() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def herramienta(nombre: str) -> str | None:
    """Ejecutable del entorno del proyecto: .venv del proyecto, el del intérprete o el PATH."""
    candidatos = [_proyecto() / ".venv" / "bin" / nombre, Path(sys.executable).parent / nombre]
    encontrada = next((str(candidato) for candidato in candidatos if candidato.is_file()), None)
    return encontrada or shutil.which(nombre)


def _correr(argumentos: list[str], carpeta: Path | None = None) -> subprocess.CompletedProcess[str]:
    # S603: solo ejecuta herramientas del entorno del proyecto (ruff, pytest) con argumentos fijos.
    return subprocess.run(
        argumentos,  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        cwd=carpeta,
        timeout=PLAZO_PRUEBAS_RAPIDAS_S,
    )


def _es_python_del_proyecto(ruta: str) -> bool:
    archivo = Path(ruta).resolve()
    return (
        archivo.suffix == ".py"
        and archivo.is_file()
        and archivo.is_relative_to(_proyecto().resolve())
    )


def _formatear(ruta: str) -> int:
    if not _es_python_del_proyecto(ruta):
        return 0
    ruff = herramienta("ruff")
    if ruff is None:
        sys.stderr.write("ruff no está instalado: corre .claude/hooks/session-start.sh.\n")
        return 1
    # --force-exclude respeta las exclusiones heredadas (WAIVER-#2/#3) aunque se pase la ruta.
    _correr([ruff, "format", "--force-exclude", ruta])
    revision = _correr([ruff, "check", "--fix", "--force-exclude", ruta])
    if revision.returncode == 0:
        return 0
    sys.stderr.write(f"ruff encontró problemas que no puede arreglar solo:\n{revision.stdout}")
    return CODIGO_BLOQUEO


def _problemas_al_cerrar() -> list[str]:
    proyecto = _proyecto()
    problemas = []
    if not filecmp.cmp(proyecto / "CLAUDE.md", proyecto / "Agents.md", shallow=False):
        problemas.append("CLAUDE.md y Agents.md difieren: copia uno sobre el otro (§14.13).")
    python = herramienta("python") or sys.executable
    pruebas = _correr(
        [python, "-m", "pytest", "-q", "-x", "-m", "unit and not slow", "-p", "no:cacheprovider"],
        carpeta=proyecto,
    )
    if pruebas.returncode not in CODIGOS_PYTEST_ACEPTABLES:
        salida = pruebas.stdout[-CARACTERES_DE_SALIDA_DE_PRUEBAS:]
        problemas.append(f"Las pruebas unitarias rápidas fallan (Ley Cero):\n{salida}")
    return problemas


def _cierre(evento: dict[str, object]) -> int:
    if evento.get("stop_hook_active"):
        return 0
    if problemas := _problemas_al_cerrar():
        sys.stdout.write(json.dumps({"decision": "block", "reason": "\n".join(problemas)}))
    return 0


def _bloquear_si(motivo: str | None) -> int:
    if motivo is None:
        return 0
    sys.stderr.write(f"{motivo}\n")
    return CODIGO_BLOQUEO


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subcomando", choices=["bash", "archivos", "formato", "cierre"])
    subcomando = parser.parse_args(argv).subcomando
    evento = json.load(sys.stdin)
    if subcomando == "cierre":
        return _cierre(evento)
    entrada = evento["tool_input"]
    if subcomando == "bash":
        return _bloquear_si(motivo_de_bloqueo_bash(entrada["command"]))
    if subcomando == "formato":
        return _formatear(entrada["file_path"])
    if os.environ.get(VARIABLE_AUTORIZACION) == "1":
        return 0
    return _bloquear_si(motivo_de_bloqueo_archivo(entrada["file_path"]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
