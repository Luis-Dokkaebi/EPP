"""El repositorio como sistema de registro (SPEC/9 §0.9, principio H1)."""

import re
from pathlib import Path

import pytest

from tests.utilidades_scripts import RAIZ

DOCS = RAIZ / "docs"
INDICE = DOCS / "README.md"
ENLACE_RELATIVO = re.compile(r"\]\((?!https?://|#)([^)#]+)(?:#[^)]*)?\)")
SECCIONES_DE_ADR = ("## Estado", "## Contexto", "## Opciones", "## Decisión", "## Consecuencias")


def _enlaces(documento: Path) -> list[Path]:
    texto = documento.read_text(encoding="utf-8")
    return [(documento.parent / destino).resolve() for destino in ENLACE_RELATIVO.findall(texto)]


def _adrs() -> list[Path]:
    return sorted((DOCS / "adr").glob("[0-9][0-9][0-9]-*.md"))


def test_indice_de_docs_no_tiene_enlaces_rotos() -> None:
    rotos = [enlace for enlace in _enlaces(INDICE) if not enlace.exists()]

    assert rotos == []


def test_indice_de_docs_enlaza_cada_adr_y_cada_documento_de_calidad() -> None:
    enlazados = set(_enlaces(INDICE))
    documentos = [*_adrs(), *(DOCS / "quality").glob("*.md")]

    assert [documento for documento in documentos if documento.resolve() not in enlazados] == []


def test_indice_de_docs_enlaza_cada_documento_de_ml_y_cada_runbook() -> None:
    enlazados = set(_enlaces(INDICE))
    documentos = [*(DOCS / "ml").glob("*.md"), *(DOCS / "runbooks").glob("*.md")]

    assert [documento for documento in documentos if documento.resolve() not in enlazados] == []


def test_hay_al_menos_una_adr_numerada() -> None:
    assert _adrs()


@pytest.mark.parametrize("adr", _adrs(), ids=lambda adr: adr.name)
def test_cada_adr_tiene_las_secciones_de_la_plantilla(adr: Path) -> None:
    texto = adr.read_text(encoding="utf-8")

    assert [seccion for seccion in SECCIONES_DE_ADR if seccion not in texto] == []


def test_cada_leccion_de_agentes_nombra_el_mecanismo_que_la_hace_cumplir() -> None:
    filas = [
        fila
        for fila in (DOCS / "quality" / "lecciones_agentes.md").read_text("utf-8").splitlines()
        if fila.startswith("| L-")
    ]

    assert filas
    assert [fila for fila in filas if "`" not in fila.split("|")[4]] == []
