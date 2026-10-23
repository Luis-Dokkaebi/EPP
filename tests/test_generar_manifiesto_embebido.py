"""Generador de src/models/manifiesto_aprobado.py (SPEC/9 §1.8)."""

import json
from pathlib import Path

import pytest

from scripts.generar_manifiesto_embebido import generar_modulo, main
from tests.utilidades_scripts import ejecutar_script

MANIFIESTO = {
    "modelos": [
        {"archivo": "z.onnx", "sha256": "b" * 64},
        {"archivo": "models/a.onnx", "sha256": "a" * 64},
    ]
}
ESPERADO = (
    '"""Modelos aprobados (archivo -> sha256), generado desde models/manifest.json.\n'
    "\n"
    "No editar a mano: python scripts/generar_manifiesto_embebido.py (SPEC/9 §1.8).\n"
    '"""\n'
    "\n"
    "MODELOS_APROBADOS: dict[str, str] = {\n"
    "    # pragma: allowlist nextline secret\n"
    f'    "models/a.onnx": "{"a" * 64}",\n'
    "    # pragma: allowlist nextline secret\n"
    f'    "z.onnx": "{"b" * 64}",\n'
    "}\n"
)


def _repo(carpeta: Path) -> Path:
    (carpeta / "models").mkdir()
    (carpeta / "src" / "models").mkdir(parents=True)
    (carpeta / "models" / "manifest.json").write_text(json.dumps(MANIFIESTO), encoding="utf-8")
    return carpeta


def test_generar_modulo_ordena_por_archivo_y_marca_los_hashes_para_detect_secrets() -> None:
    assert generar_modulo(MANIFIESTO) == ESPERADO


def test_generar_modulo_sin_modelos_deja_la_tabla_vacia() -> None:
    assert generar_modulo({"modelos": []}).endswith("MODELOS_APROBADOS: dict[str, str] = {\n}\n")


def test_main_escribe_el_modulo_y_lo_informa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_repo(tmp_path))

    codigo = main()

    assert codigo == 0
    assert (tmp_path / "src/models/manifiesto_aprobado.py").read_text(encoding="utf-8") == ESPERADO
    assert capsys.readouterr().out == (
        "src/models/manifiesto_aprobado.py regenerado con 2 modelo(s).\n"
    )


@pytest.mark.integration
def test_script_ejecutado_como_programa_regenera_el_modulo(tmp_path: Path) -> None:
    resultado = ejecutar_script("generar_manifiesto_embebido.py", carpeta=_repo(tmp_path))

    assert resultado.returncode == 0, resultado.stderr
    assert (tmp_path / "src/models/manifiesto_aprobado.py").read_text(encoding="utf-8") == ESPERADO
