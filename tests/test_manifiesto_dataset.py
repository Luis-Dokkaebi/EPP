"""Manifiesto versionado del dataset EPP con hashes (SPEC/9 §2.6; docs/ml/contrato_datos.md §7)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ml.contrato_datos import TAXONOMIA_V1, ContratoDeDatosError, categorias
from ml.manifiesto_dataset import (
    ARCHIVO_DE_ANOTACIONES,
    DefinicionDelDataset,
    Fuente,
    ReglaDeSplit,
    crear_manifiesto,
    huella_del_manifiesto,
    verificar_manifiesto,
)
from tests.coco_sintetico import imagen

LADO_MINIMO = 10.0
FUENTES = (Fuente("Piloto planta 1", "propia-con-autorizacion"),)
REGLA = ReglaDeSplit(camaras_de_test=frozenset({"cam-03"}), dias_de_valid=frozenset({"2026-10-02"}))
CAPTURAS = (
    ("cam-01", "20261001", "2026-10-01"),
    ("cam-01", "20261002", "2026-10-02"),
    ("cam-02", "20261001", "2026-10-01"),
    ("cam-03", "20261002", "2026-10-02"),
)


def _sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _dataset(carpeta: Path) -> Path:
    imagenes = []
    for indice, (camara, dia, fecha) in enumerate(CAPTURAS, start=1):
        nombre = f"{camara}_{dia}_083005_0001.jpg"
        contenido = f"imagen {indice}".encode()
        (carpeta / nombre).write_bytes(contenido)
        imagenes.append(
            imagen(
                id=indice, file_name=nombre, camara=camara, fecha=fecha, sha256=_sha256(contenido)
            )
        )
    coco = {"images": imagenes, "annotations": [], "categories": categorias(TAXONOMIA_V1)}
    (carpeta / ARCHIVO_DE_ANOTACIONES).write_text(json.dumps(coco), encoding="utf-8")
    return carpeta


def _crear(carpeta: Path, **cambios: Any) -> dict[str, Any]:
    argumentos = {
        "version": "v0.1",
        "taxonomia": TAXONOMIA_V1,
        "fuentes": FUENTES,
        "regla": REGLA,
        "lado_minimo_px": LADO_MINIMO,
    }
    return crear_manifiesto(carpeta, DefinicionDelDataset(**{**argumentos, **cambios}))


def test_crear_manifiesto_asigna_el_split_por_camara_y_dia(tmp_path: Path) -> None:
    manifiesto = _crear(_dataset(tmp_path))

    assert [(item["file_name"][:15], item["split"]) for item in manifiesto["imagenes"]] == [
        ("cam-01_20261001", "train"),
        ("cam-01_20261002", "valid"),
        ("cam-02_20261001", "train"),
        ("cam-03_20261002", "test"),
    ]
    assert manifiesto["conteo_por_split"] == {"train": 2, "valid": 1, "test": 1}


def test_crear_manifiesto_registra_version_taxonomia_fuentes_y_hashes(tmp_path: Path) -> None:
    carpeta = _dataset(tmp_path)

    manifiesto = _crear(carpeta)

    anotaciones = (carpeta / ARCHIVO_DE_ANOTACIONES).read_bytes()
    assert manifiesto["version"] == "v0.1"
    assert manifiesto["taxonomia"] == list(TAXONOMIA_V1)
    assert manifiesto["lado_minimo_px"] == LADO_MINIMO
    assert manifiesto["fuentes"] == [
        {"nombre": "Piloto planta 1", "licencia": "propia-con-autorizacion"}
    ]
    assert manifiesto["anotaciones"] == {
        "archivo": ARCHIVO_DE_ANOTACIONES,
        "sha256": _sha256(anotaciones),
    }
    assert manifiesto["imagenes"][0]["sha256"] == _sha256(b"imagen 1")
    assert manifiesto["regla_de_split"] == {
        "camaras_de_test": ["cam-03"],
        "dias_de_valid": ["2026-10-02"],
    }


@pytest.mark.parametrize("version", ["0.1", "v1", "v0.1-beta", "V0.1", ""])
def test_crear_manifiesto_exige_una_version_mayor_menor(tmp_path: Path, version: str) -> None:
    with pytest.raises(ContratoDeDatosError, match="vMAYOR.MENOR"):
        _crear(_dataset(tmp_path), version=version)


def test_crear_manifiesto_rechaza_fuentes_con_licencia_prohibida(tmp_path: Path) -> None:
    with pytest.raises(ContratoDeDatosError, match="SH17 no es apto"):
        _crear(_dataset(tmp_path), fuentes=(*FUENTES, Fuente("SH17", "CC-BY-4.0")))


def test_crear_manifiesto_exige_al_menos_una_fuente(tmp_path: Path) -> None:
    with pytest.raises(ContratoDeDatosError, match="al menos una fuente"):
        _crear(_dataset(tmp_path), fuentes=())


def test_crear_manifiesto_valida_las_anotaciones_contra_el_contrato(tmp_path: Path) -> None:
    with pytest.raises(ContratoDeDatosError, match="categorías no son las de la taxonomía"):
        _crear(_dataset(tmp_path), taxonomia=("persona", "casco"))


def test_crear_manifiesto_detecta_imagenes_faltantes_o_editadas(tmp_path: Path) -> None:
    carpeta = _dataset(tmp_path)
    (carpeta / "cam-01_20261001_083005_0001.jpg").unlink()
    (carpeta / "cam-02_20261001_083005_0001.jpg").write_bytes(b"retocada")

    with pytest.raises(ContratoDeDatosError) as error:
        _crear(carpeta)

    assert error.value.violaciones == [
        "cam-01_20261001_083005_0001.jpg: falta el archivo de la imagen.",
        "cam-02_20261001_083005_0001.jpg: el sha256 no coincide con el de la captura "
        "(la imagen se editó).",
    ]


def test_crear_manifiesto_rechaza_un_split_con_fuga(tmp_path: Path) -> None:
    sin_test = ReglaDeSplit(camaras_de_test=frozenset(), dias_de_valid=frozenset({"2026-10-02"}))

    with pytest.raises(ContratoDeDatosError, match="reservada solo para test"):
        _crear(_dataset(tmp_path), regla=sin_test)


def test_verificar_manifiesto_sin_cambios_no_informa_nada(tmp_path: Path) -> None:
    carpeta = _dataset(tmp_path)

    assert verificar_manifiesto(carpeta, _crear(carpeta)) == []


def test_verificar_manifiesto_informa_cada_diferencia(tmp_path: Path) -> None:
    carpeta = _dataset(tmp_path)
    manifiesto = _crear(carpeta)
    (carpeta / "cam-01_20261001_083005_0001.jpg").unlink()
    (carpeta / "cam-02_20261001_083005_0001.jpg").write_bytes(b"cambiada")
    (carpeta / "cam-09_20261003_083005_0001.jpg").write_bytes(b"nueva")
    (carpeta / ARCHIVO_DE_ANOTACIONES).write_text("{}", encoding="utf-8")

    assert verificar_manifiesto(carpeta, manifiesto) == [
        f"{ARCHIVO_DE_ANOTACIONES}: el sha256 no coincide con el manifiesto.",
        "cam-01_20261001_083005_0001.jpg: falta el archivo.",
        "cam-02_20261001_083005_0001.jpg: el sha256 no coincide con el manifiesto.",
        "cam-09_20261003_083005_0001.jpg: está en la carpeta pero no en el manifiesto.",
    ]


def test_huella_del_manifiesto_no_depende_del_orden_de_las_claves(tmp_path: Path) -> None:
    manifiesto = _crear(_dataset(tmp_path))
    reordenado = dict(reversed(list(manifiesto.items())))

    assert huella_del_manifiesto(reordenado) == huella_del_manifiesto(manifiesto)
    assert huella_del_manifiesto({**manifiesto, "version": "v0.2"}) != huella_del_manifiesto(
        manifiesto
    )
