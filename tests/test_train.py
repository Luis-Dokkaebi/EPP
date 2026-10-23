"""Entrenamiento reproducible y separado del producto (SPEC/9 §3.1; mle-workflow)."""

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ml.manifiesto_dataset import (
    DefinicionDelDataset,
    crear_manifiesto,
    huella_del_manifiesto,
)
from ml.train import (
    ConfigEntrenamiento,
    EntrenamientoInvalidoError,
    ResultadoDelEntrenador,
    campos_de_config,
    entrenar,
    huella_de_config,
    nombre_de_artefacto,
)
from tests.test_manifiesto_dataset import FUENTES, LADO_MINIMO, REGLA, _dataset

# SHA de commit ficticio para las pruebas (40 hexadecimales), no es un secreto.
SHA_CODIGO = "0123456789abcdef0123456789abcdef01234567"  # pragma: allowlist secret
TAXONOMIA = ("persona", "cabeza", "casco", "chaleco")


class EntrenadorFalso:
    """Doble del entrenador: escribe unos pesos falsos y devuelve métricas fijas."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[ConfigEntrenamiento, Path]] = []

    def entrenar(self, config: ConfigEntrenamiento, carpeta: Path) -> ResultadoDelEntrenador:
        self.llamadas.append((config, carpeta))
        pesos = carpeta / "pesos.pth"
        pesos.write_bytes(b"pesos falsos")
        return ResultadoDelEntrenador(pesos=pesos, metricas={"map50_casco": 0.5})


def _config(carpeta: Path, **cambios: Any) -> ConfigEntrenamiento:
    valores = {
        "dataset": carpeta,
        "manifiesto": carpeta / "manifest.json",
        "tamano": "small",
        "resolucion": 512,
        "epocas": 2,
        "lote": 4,
        "tasa_de_aprendizaje": 1e-4,
        "semilla": 7,
    }
    return ConfigEntrenamiento(**{**valores, **cambios})


def _dataset_versionado(carpeta: Path) -> dict[str, Any]:
    definicion = DefinicionDelDataset("v0.1", TAXONOMIA, FUENTES, REGLA, LADO_MINIMO)
    manifiesto = crear_manifiesto(_dataset(carpeta), definicion)
    (carpeta / "manifest.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    return manifiesto


@pytest.mark.parametrize("tamano", ["nano", "small", "medium", "large"])
def test_config_acepta_los_tamanos_apache_de_rf_detr(tmp_path: Path, tamano: str) -> None:
    assert _config(tmp_path, tamano=tamano).tamano == tamano


@pytest.mark.parametrize("tamano", ["atto", "femto", "pico", "xl", "2xl", "base", ""])
def test_config_rechaza_tamanos_sin_licencia_apache(tmp_path: Path, tamano: str) -> None:
    with pytest.raises(EntrenamientoInvalidoError) as error:
        _config(tmp_path, tamano=tamano)

    assert str(error.value) == (
        f'Tamaño "{tamano}" no permitido: solo nano, small, medium y large tienen licencia '
        "Apache-2.0 (los demás son PML 1.0, SPEC/9 §3.1)."
    )


@pytest.mark.parametrize("resolucion", [32, 384, 704])
def test_config_acepta_resoluciones_multiplo_de_32(tmp_path: Path, resolucion: int) -> None:
    assert _config(tmp_path, resolucion=resolucion).resolucion == resolucion


@pytest.mark.parametrize("resolucion", [0, -32, 500, 31])
def test_config_rechaza_resoluciones_que_no_son_multiplo_de_32(
    tmp_path: Path, resolucion: int
) -> None:
    with pytest.raises(EntrenamientoInvalidoError) as error:
        _config(tmp_path, resolucion=resolucion)

    assert str(error.value) == (
        f"Resolución {resolucion} inválida: debe ser un múltiplo positivo de 32 (parche 16 por "
        "2 ventanas en RF-DETR, SPEC/9 §3.6)."
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("epocas", 0),
        ("lote", 0),
        ("tasa_de_aprendizaje", 0.0),
        ("tasa_de_aprendizaje", float("nan")),
        ("semilla", -1),
    ],
)
def test_config_rechaza_hiperparametros_imposibles(
    tmp_path: Path, campo: str, valor: float
) -> None:
    with pytest.raises(EntrenamientoInvalidoError) as error:
        _config(tmp_path, **{campo: valor})

    assert str(error.value) == f'"{campo}" inválido: {valor}.'


def test_config_acepta_los_minimos(tmp_path: Path) -> None:
    config = _config(tmp_path, epocas=1, lote=1, tasa_de_aprendizaje=1e-9, semilla=0)

    assert (config.epocas, config.lote, config.semilla) == (1, 1, 0)


def test_config_es_inmutable(tmp_path: Path) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _config(tmp_path).epocas = 9


def test_huella_de_config_depende_de_hiperparametros_y_dataset_pero_no_de_las_rutas(
    tmp_path: Path,
) -> None:
    base = huella_de_config(_config(tmp_path), "v0.1", "a" * 64)

    assert huella_de_config(_config(tmp_path / "otra"), "v0.1", "a" * 64) == base
    assert huella_de_config(_config(tmp_path, semilla=8), "v0.1", "a" * 64) != base
    assert huella_de_config(_config(tmp_path), "v0.2", "a" * 64) != base
    assert huella_de_config(_config(tmp_path), "v0.1", "b" * 64) != base


def test_huella_de_config_es_el_sha256_de_su_json_canonico(tmp_path: Path) -> None:
    canonico = (
        '{"dataset_huella":"h","dataset_version":"v0.1","epocas":2,"lote":4,"resolucion":512,'
        '"semilla":7,"tamano":"small","tasa_de_aprendizaje":0.0001}'
    )

    assert huella_de_config(_config(tmp_path), "v0.1", "h") == (
        hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    )


def test_nombre_de_artefacto_es_determinista_y_corto() -> None:
    assert nombre_de_artefacto(SHA_CODIGO, "f" * 64) == "epp-0123456789ab-ffffffffffff"


@pytest.mark.parametrize("sha", ["", "abc", "Z" * 40, SHA_CODIGO[:20]])
def test_nombre_de_artefacto_exige_el_sha_completo_del_codigo(sha: str) -> None:
    with pytest.raises(EntrenamientoInvalidoError) as error:
        nombre_de_artefacto(sha, "f" * 64)

    assert str(error.value) == f'SHA de código "{sha}" inválido: se esperan 40 hexadecimales.'


def test_entrenar_registra_codigo_config_dataset_metricas_y_pesos(tmp_path: Path) -> None:
    manifiesto = _dataset_versionado(tmp_path)
    entrenador = EntrenadorFalso()
    config = _config(tmp_path)

    registro = entrenar(config, entrenador, SHA_CODIGO, tmp_path / "salidas")

    huella = huella_de_config(config, "v0.1", huella_del_manifiesto(manifiesto))
    destino = tmp_path / "salidas" / nombre_de_artefacto(SHA_CODIGO, huella)
    assert entrenador.llamadas == [(config, destino)]
    assert registro == json.loads((destino / "registro.json").read_text(encoding="utf-8"))
    assert registro == {
        "artefacto": destino.name,
        "sha_codigo": SHA_CODIGO,
        "huella_config": huella,
        "config": campos_de_config(config),
        "dataset_version": "v0.1",
        "dataset_huella": huella_del_manifiesto(manifiesto),
        "metricas": {"map50_casco": 0.5},
        "pesos": "pesos.pth",
        "pesos_sha256": hashlib.sha256(b"pesos falsos").hexdigest(),
    }


def test_entrenar_se_niega_si_el_dataset_no_coincide_con_su_manifiesto(tmp_path: Path) -> None:
    _dataset_versionado(tmp_path)
    (tmp_path / "cam-01_20261001_083005_0001.jpg").write_bytes(b"editada")
    entrenador = EntrenadorFalso()

    with pytest.raises(EntrenamientoInvalidoError) as error:
        entrenar(_config(tmp_path), entrenador, SHA_CODIGO, tmp_path / "salidas")

    assert str(error.value) == (
        "El dataset no coincide con su manifiesto:\n"
        "cam-01_20261001_083005_0001.jpg: el sha256 no coincide con el manifiesto."
    )
    assert entrenador.llamadas == []


class EntrenadorQueEscribeAfuera(EntrenadorFalso):
    def entrenar(self, config: ConfigEntrenamiento, carpeta: Path) -> ResultadoDelEntrenador:
        afuera = carpeta.parent / "pesos.pth"
        afuera.write_bytes(b"x")
        return ResultadoDelEntrenador(pesos=afuera, metricas={})


class EntrenadorConMetricaAcentuada(EntrenadorFalso):
    def entrenar(self, config: ConfigEntrenamiento, carpeta: Path) -> ResultadoDelEntrenador:
        resultado = super().entrenar(config, carpeta)
        return resultado._replace(metricas={"precisión": 0.5})


def test_entrenar_nunca_sobrescribe_un_artefacto_existente(tmp_path: Path) -> None:
    _dataset_versionado(tmp_path)
    registro = entrenar(_config(tmp_path), EntrenadorFalso(), SHA_CODIGO, tmp_path / "salidas")

    with pytest.raises(EntrenamientoInvalidoError) as error:
        entrenar(_config(tmp_path), EntrenadorFalso(), SHA_CODIGO, tmp_path / "salidas")

    assert str(error.value) == (
        f"{tmp_path / 'salidas' / registro['artefacto']} ya existe: cambia la semilla o la "
        "configuración; nunca se sobrescribe."
    )


def test_entrenar_exige_pesos_dentro_de_la_carpeta_del_artefacto(tmp_path: Path) -> None:
    _dataset_versionado(tmp_path)

    with pytest.raises(EntrenamientoInvalidoError) as error:
        entrenar(_config(tmp_path), EntrenadorQueEscribeAfuera(), SHA_CODIGO, tmp_path / "s")

    afuera = tmp_path / "s" / "pesos.pth"
    assert str(error.value) == (
        f"El entrenador dejó los pesos fuera de la carpeta del artefacto: {afuera}."
    )


def test_entrenar_guarda_un_registro_legible_con_acentos_sin_escapar(tmp_path: Path) -> None:
    _dataset_versionado(tmp_path)
    entrenador = EntrenadorConMetricaAcentuada()

    registro = entrenar(_config(tmp_path), entrenador, SHA_CODIGO, tmp_path / "salidas")

    texto = (tmp_path / "salidas" / registro["artefacto"] / "registro.json").read_text("utf-8")
    assert texto.startswith('{\n  "artefacto"')
    assert '"precisión": 0.5' in texto
