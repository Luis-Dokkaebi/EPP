"""Avisos de terceros generados desde pip-licenses y el manifiesto de modelos (SPEC/9 §1.12)."""

import json
from pathlib import Path

import pytest

from scripts.generar_avisos_terceros import (
    SIN_TEXTO,
    aviso_de_modelo,
    aviso_de_paquete,
    generar_avisos,
    main,
)
from tests.utilidades_scripts import ejecutar_script

APACHE = {
    "Name": "onnxruntime",
    "Version": "1.31.0",
    "License": "MIT License",
    "LicenseText": "MIT License\n\nCopyright (c) Microsoft Corporation.\n",
    "NoticeText": "UNKNOWN",
}
CON_NOTICE = {
    "Name": "Pillow",
    "Version": "11.0.0",
    "License": "MIT-CMU",
    "LicenseText": "Texto de la licencia",
    "NoticeText": "Aviso de atribución",
}
MODELO = {
    "nombre": "rf-detr-personas",
    "version": "1.0",
    "archivo": "models/personas.onnx",
    "licencia_pesos": "Apache-2.0",
    "licencia_codigo_entrenamiento": "Apache-2.0",
    "datasets": [{"nombre": "COCO 2017", "licencia": "CC-BY-4.0"}],
    "origen": "Ajuste fino propio sobre RF-DETR.",
}


def test_aviso_de_paquete_incluye_nombre_version_licencia_y_texto() -> None:
    assert aviso_de_paquete(APACHE) == (
        "onnxruntime 1.31.0\n"
        "Licencia: MIT License\n\n"
        "MIT License\n\nCopyright (c) Microsoft Corporation.\n"
    )


def test_aviso_de_paquete_conserva_el_notice_antes_del_texto_de_la_licencia() -> None:
    assert aviso_de_paquete(CON_NOTICE) == (
        "Pillow 11.0.0\nLicencia: MIT-CMU\n\nAviso de atribución\n\nTexto de la licencia\n"
    )


def test_aviso_de_paquete_sin_texto_de_licencia_lo_marca_para_revision() -> None:
    sin_texto = {**APACHE, "LicenseText": "UNKNOWN"}

    assert aviso_de_paquete(sin_texto).endswith(f"\n\n{SIN_TEXTO}\n")


def test_aviso_de_paquete_sin_campos_de_texto_lo_marca_para_revision() -> None:
    """pip-licenses sin --with-license-file ni --with-notice-file no trae esos campos."""
    solo_licencia = {"Name": "idna", "Version": "3.20", "License": "BSD-3-Clause"}

    assert aviso_de_paquete(solo_licencia) == (
        f"idna 3.20\nLicencia: BSD-3-Clause\n\n{SIN_TEXTO}\n"
    )


def test_aviso_de_modelo_declara_licencias_datasets_y_origen() -> None:
    assert aviso_de_modelo(MODELO) == (
        "rf-detr-personas 1.0 (models/personas.onnx)\n"
        "Licencia de los pesos: Apache-2.0\n"
        "Licencia del código de entrenamiento: Apache-2.0\n"
        "Datasets: COCO 2017 (CC-BY-4.0)\n"
        "Origen: Ajuste fino propio sobre RF-DETR.\n"
    )


def test_generar_avisos_ordena_los_paquetes_sin_distinguir_mayusculas() -> None:
    avisos = generar_avisos([APACHE, CON_NOTICE], {"modelos": [MODELO]})

    assert avisos.index("onnxruntime 1.31.0") < avisos.index("Pillow 11.0.0")
    assert avisos.index("Pillow 11.0.0") < avisos.index("rf-detr-personas 1.0")


def test_generar_avisos_advierte_que_no_es_asesoria_legal() -> None:
    avisos = generar_avisos([], {"modelos": []})

    assert avisos.startswith("AVISOS DE TERCEROS\n")
    assert "No es asesoría legal: requiere la revisión de la decisión D9." in avisos


def test_main_escribe_el_archivo_de_avisos(tmp_path: Path) -> None:
    paquetes = tmp_path / "paquetes.json"
    paquetes.write_text(json.dumps([APACHE]), encoding="utf-8")
    manifiesto = tmp_path / "manifest.json"
    manifiesto.write_text(json.dumps({"modelos": [MODELO]}), encoding="utf-8")
    salida = tmp_path / "legal" / "THIRD_PARTY_NOTICES.txt"

    resultado = ejecutar_script(
        "generar_avisos_terceros.py",
        "--paquetes", str(paquetes), "--manifiesto", str(manifiesto), "--salida", str(salida),
    )  # fmt: skip

    assert resultado.returncode == 0, resultado.stderr
    assert salida.read_text(encoding="utf-8") == generar_avisos([APACHE], {"modelos": [MODELO]})


SEGUNDO_DATASET = {"nombre": "Propio", "licencia": "CC-BY-4.0"}


def test_generar_avisos_produce_el_documento_completo() -> None:
    avisos = generar_avisos([APACHE], {"modelos": [MODELO]})

    assert avisos == (
        "AVISOS DE TERCEROS\n"
        "Generado por scripts/generar_avisos_terceros.py; no editar a mano.\n"
        "No es asesoría legal: requiere la revisión de la decisión D9.\n"
        "\n== Paquetes de Python ==\n"
        "\n" + "-" * 72 + "\n" + aviso_de_paquete(APACHE) + "\n"
        "== Modelos ==\n"
        "\n" + "-" * 72 + "\n" + aviso_de_modelo(MODELO)
    )


def test_el_marcador_sin_texto_pide_revision_a_mano() -> None:
    assert SIN_TEXTO == "(El paquete no incluye el texto de su licencia: revisar a mano.)"


def test_aviso_de_paquete_solo_quita_saltos_de_linea_finales() -> None:
    con_x = {**APACHE, "LicenseText": "Licencia X\n\n"}

    assert aviso_de_paquete(con_x).endswith("\n\nLicencia X\n")


def test_aviso_de_modelo_enumera_cada_dataset() -> None:
    modelo = {**MODELO, "datasets": [*MODELO["datasets"], SEGUNDO_DATASET]}

    assert "Datasets: COCO 2017 (CC-BY-4.0), Propio (CC-BY-4.0)\n" in aviso_de_modelo(modelo)


def _paquetes_en(carpeta: Path) -> Path:
    paquetes = carpeta / "paquetes.json"
    paquetes.write_text(json.dumps([APACHE]), encoding="utf-8")
    return paquetes


@pytest.mark.parametrize("falta", ["--paquetes", "--salida"])
def test_main_exige_paquetes_y_salida(tmp_path: Path, falta: str) -> None:
    argumentos = {"--paquetes": str(_paquetes_en(tmp_path)), "--salida": str(tmp_path / "a.txt")}
    del argumentos[falta]

    with pytest.raises(SystemExit):
        main([texto for par in argumentos.items() for texto in par])


def test_main_usa_el_manifiesto_del_directorio_actual_y_crea_carpetas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "manifest.json").write_text(
        json.dumps({"modelos": [MODELO]}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    salida = tmp_path / "a" / "b" / "avisos.txt"

    main(["--paquetes", str(_paquetes_en(tmp_path)), "--salida", str(salida)])

    assert "rf-detr-personas 1.0" in salida.read_text(encoding="utf-8")


def test_main_escribe_en_una_carpeta_que_ya_existe(tmp_path: Path) -> None:
    salida = tmp_path / "avisos.txt"
    manifiesto = tmp_path / "manifest.json"
    manifiesto.write_text(json.dumps({"modelos": []}), encoding="utf-8")

    codigo = main(["--paquetes", str(_paquetes_en(tmp_path)), "--manifiesto", str(manifiesto),
                   "--salida", str(salida)])  # fmt: skip

    assert codigo == 0
    assert salida.exists()
