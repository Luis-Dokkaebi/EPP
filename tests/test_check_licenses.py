"""Gate de licencias del runtime (SPEC/9 §0.5, AC-001): impide que vuelva la AGPL."""

import json
from pathlib import Path

import pytest

from scripts.check_licenses import (
    Veredicto,
    clasificar_licencia,
    evaluar_paquetes,
    main,
    paquetes_instalados,
)
from tests.utilidades_scripts import RAIZ, ejecutar_script

LICENCIA_TKCALENDAR = "GNU General Public License v3 (GPLv3)"


@pytest.mark.parametrize(
    "licencia",
    [
        "MIT License",
        "MIT-CMU",
        "BSD-3-Clause",
        "Apache Software License",
        "Apache-2.0 OR BSD-3-Clause",
        "ISC License (ISCL)",
        "Python Software Foundation License",
        "PSF-2.0",
        "BSL-1.0",
        "HPND",
        "CC0-1.0",
        "The Unlicense (Unlicense)",
        "zlib/libpng License",
        "Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSL-1.0 AND MIT",
    ],
)
def test_clasificar_licencia_permisiva_es_permitida(licencia: str) -> None:
    assert clasificar_licencia(licencia) is Veredicto.PERMITIDA


@pytest.mark.parametrize(
    "licencia",
    [
        "GNU Affero General Public License v3 or later (AGPLv3+)",
        LICENCIA_TKCALENDAR,
        "GPL-2.0-or-later",
        "Server Side Public License (SSPL)",
        "CC-BY-NC-SA-4.0",
        "PML-1.0",
        "Commercial",
        "MIT AND GPL-3.0",
    ],
)
def test_clasificar_licencia_copyleft_fuerte_o_no_comercial_es_prohibida(licencia: str) -> None:
    assert clasificar_licencia(licencia) is Veredicto.PROHIBIDA


@pytest.mark.parametrize(
    "licencia",
    [
        "GNU Lesser General Public License v3 (LGPLv3)",
        "LGPL-2.1-only",
        "GNU Library General Public License v2",
        "Mozilla Public License 2.0 (MPL 2.0)",
        "MPL-2.0 AND MIT",
        "UNKNOWN",
        "",
        "Public Domain",
        "Apache Software License; BSD License; Public Domain",
    ],
)
def test_clasificar_licencia_debil_o_desconocida_requiere_revision(licencia: str) -> None:
    assert clasificar_licencia(licencia) is Veredicto.REVISION


def test_clasificar_licencia_con_alternativa_permisiva_elige_la_mejor() -> None:
    assert clasificar_licencia("GPL-3.0 OR MIT") is Veredicto.PERMITIDA


def test_evaluar_paquetes_reporta_prohibidos_y_pendientes_de_revision() -> None:
    paquetes = [
        {"Name": "ultralytics", "Version": "8.1.15", "License": "AGPL-3.0"},
        {"Name": "certifi", "Version": "1", "License": "MPL-2.0"},
        {"Name": "numpy", "Version": "1.26.4", "License": "BSD License"},
    ]

    errores = evaluar_paquetes(paquetes, revisadas={})

    assert errores == [
        "ultralytics 8.1.15: licencia prohibida en el runtime (AGPL-3.0). Reemplázalo por una "
        "alternativa Apache/MIT o registra la aprobación legal en docs/legal/.",
        "certifi 1: licencia que exige revisión humana (MPL-2.0). Registra la decisión aprobada "
        "en docs/legal/licencias_revisadas.json.",
    ]


def test_evaluar_paquetes_acepta_una_revision_aprobada_por_un_humano() -> None:
    paquetes = [{"Name": "certifi", "Version": "1", "License": "MPL-2.0"}]
    revisadas = {"certifi": {"licencia_declarada": "MPL-2.0", "aprobado_por": "Asesor legal"}}

    assert evaluar_paquetes(paquetes, revisadas) == []


@pytest.mark.parametrize(
    "revision",
    [
        {"licencia_declarada": "MPL-2.0", "aprobado_por": None},
        {"licencia_declarada": "MPL-1.1", "aprobado_por": "Asesor legal"},
    ],
    ids=["propuesta-sin-aprobar", "licencia-cambio-desde-la-revision"],
)
def test_evaluar_paquetes_revision_sin_aprobar_o_desactualizada_no_alcanza(
    revision: dict[str, str | None],
) -> None:
    paquetes = [{"Name": "certifi", "Version": "1", "License": "MPL-2.0"}]

    assert len(evaluar_paquetes(paquetes, {"certifi": revision})) == 1


def _escribir_json(ruta: Path, contenido: object) -> Path:
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def test_main_con_paquetes_prohibidos_devuelve_uno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paquetes = _escribir_json(
        tmp_path / "p.json",
        [{"Name": "tkcalendar", "Version": "1.6.1", "License": LICENCIA_TKCALENDAR}],
    )
    revisadas = _escribir_json(tmp_path / "r.json", {})

    codigo = main(["--paquetes", str(paquetes), "--revisadas", str(revisadas)])

    assert codigo == 1
    assert capsys.readouterr().out.startswith("tkcalendar 1.6.1: licencia prohibida")


def test_main_con_paquetes_permitidos_devuelve_cero(tmp_path: Path) -> None:
    paquetes = _escribir_json(
        tmp_path / "p.json", [{"Name": "numpy", "Version": "1.26.4", "License": "BSD"}]
    )
    revisadas = _escribir_json(tmp_path / "r.json", {})

    argumentos = ["--paquetes", str(paquetes), "--revisadas", str(revisadas)]

    assert main([*argumentos]) == 0


@pytest.mark.integration
def test_paquetes_instalados_lee_el_entorno_actual_con_pip_licenses() -> None:
    paquetes = paquetes_instalados()

    nombres = {paquete["Name"] for paquete in paquetes}
    assert {"pytest", "radon"} <= nombres
    assert all(set(paquete) >= {"Name", "Version", "License"} for paquete in paquetes)


def test_main_sin_revisadas_usa_el_registro_de_docs_legal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paquetes = _escribir_json(
        tmp_path / "p.json", [{"Name": "numpy", "Version": "1.26.4", "License": "BSD"}]
    )
    monkeypatch.chdir(RAIZ)

    assert main(["--paquetes", str(paquetes)]) == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("licencia", "codigo_esperado"), [("MIT", 0), ("AGPL-3.0", 1)], ids=["verde", "rojo"]
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    tmp_path: Path, licencia: str, codigo_esperado: int
) -> None:
    paquetes = _escribir_json(
        tmp_path / "p.json", [{"Name": "paquete", "Version": "1", "License": licencia}]
    )

    resultado = ejecutar_script("check_licenses.py", "--paquetes", str(paquetes))

    assert resultado.returncode == codigo_esperado, resultado.stdout + resultado.stderr
