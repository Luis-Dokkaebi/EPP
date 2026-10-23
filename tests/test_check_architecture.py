"""Arquitectura verificada por máquina con mensajes que enseñan la corrección (SPEC/9 §0.4, H3)."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_architecture import PISTA_GENERICA, main, traducir
from tests.utilidades_scripts import RAIZ, ejecutar_script

SALIDA_ROTA = textwrap.dedent(
    """
    El dominio no importa GUI, visión ni motores de IA
    --------------------------------------------------

    src.zones is not allowed to import cv2:

    -   src.zones.zona -> cv2 (l.3)

    src.ppe is not allowed to import src.gui:

    -   src.ppe.domain.reglas -> src.gui.views (l.12)
    """
)


def test_traducir_explica_como_corregir_cada_import_prohibido() -> None:
    mensajes = traducir(SALIDA_ROTA)

    assert mensajes == [
        "src.zones.zona importa cv2 (línea 3): recibe la imagen o el dibujo a través de un "
        "puerto (por ejemplo AlmacenEvidenciasPort) y deja cv2 en la capa de adaptadores.",
        "src.ppe.domain.reglas importa src.gui.views (línea 12): la GUI depende del dominio, "
        "nunca al revés; expón un presentador o publica un evento.",
    ]


def test_traducir_customtkinter_en_el_dominio_sugiere_un_presentador() -> None:
    mensajes = traducir("-   src.ppe.domain.x -> customtkinter (l.2)")

    assert mensajes == [
        "src.ppe.domain.x importa customtkinter (línea 2): la GUI depende del dominio, nunca al "
        "revés; expón un presentador o publica un evento."
    ]


@pytest.mark.parametrize("motor", ["ultralytics", "torch", "onnxruntime", "rfdetr"])
def test_traducir_motor_de_ia_sugiere_el_puerto_de_deteccion(motor: str) -> None:
    mensajes = traducir(f"-   src.ppe.domain.x -> {motor}.algo (l.1)")

    assert mensajes == [
        f"src.ppe.domain.x importa {motor}.algo (línea 1): depende de DetectorPort "
        "(src/inference/ports.py) y deja el motor en src/inference/adapters/."
    ]


def test_traducir_capa_sin_pista_especifica_usa_la_generica() -> None:
    mensajes = traducir("-   src.ppe.domain.x -> src.tracking.y (l.7)")

    assert mensajes == [
        "src.ppe.domain.x importa src.tracking.y (línea 7): las dependencias apuntan hacia "
        "adentro: recibe el dato por parámetro o define un puerto en la capa de aplicación y "
        "deja el detalle en un adaptador."
    ]


def test_traducir_salida_sin_violaciones_no_devuelve_mensajes() -> None:
    assert traducir("Contracts: 2 kept, 0 broken.") == []


def _crear_proyecto_que_viola(raiz: Path) -> Path:
    paquete = raiz / "paquete_falso"
    (paquete / "dominio").mkdir(parents=True)
    (paquete / "__init__.py").write_text("", encoding="utf-8")
    (paquete / "dominio" / "__init__.py").write_text("", encoding="utf-8")
    (paquete / "dominio" / "regla.py").write_text("import json\n", encoding="utf-8")
    configuracion = raiz / ".importlinter"
    configuracion.write_text(
        "[importlinter]\nroot_packages =\n    paquete_falso\ninclude_external_packages = True\n\n"
        "[importlinter:contract:prueba]\nname = prueba\ntype = forbidden\n"
        "source_modules =\n    paquete_falso.dominio\nforbidden_modules =\n    json\n",
        encoding="utf-8",
    )
    return configuracion


def test_main_falla_e_imprime_la_correccion_si_se_rompe_un_contrato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    configuracion = _crear_proyecto_que_viola(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    codigo = main([str(configuracion)])

    assert codigo == 1
    assert capsys.readouterr().out.endswith(
        f"paquete_falso.dominio.regla importa json (línea 1): {PISTA_GENERICA}\n"
    )


def test_main_no_deja_cache_de_import_linter_en_el_directorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuracion = _crear_proyecto_que_viola(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    main([str(configuracion)])

    assert not (tmp_path / ".import_linter_cache").exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("configuracion", "codigo_esperado"),
    [(".importlinter", 0), ("no_existe.ini", 1)],
    ids=["verde", "rojo"],
)
def test_script_ejecutado_como_programa_devuelve_el_codigo_de_main(
    configuracion: str, codigo_esperado: int
) -> None:
    resultado = ejecutar_script("check_architecture.py", configuracion)

    assert resultado.returncode == codigo_esperado, resultado.stdout + resultado.stderr


def test_main_sin_argumentos_valida_la_arquitectura_real(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(RAIZ)

    assert main([]) == 0
