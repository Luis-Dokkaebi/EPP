"""Línea de comandos de la captura del dataset (SPEC/9 §2.4; docs/runbooks/captura_dataset.md)."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.test_capturar_dataset_salida import CapturaFalsa
from tests.utilidades_scripts import RAIZ, SEGUNDOS_MAXIMOS
from tools import capturar_dataset
from tools.capturar_dataset import (
    CapturaInvalidaError,
    abrir_fuente,
    main,
    ocultar_credenciales,
)

INICIO = datetime(2026, 10, 21, 8, 0, 0)
CODIGO_DE_ERROR = 2
AYUDAS = (
    "Captura de frames para el dataset EPP del piloto (SPEC/9 §2.4, B-02).",
    "video, URL RTSP o índice de cámara",
    "identificador corto: a-z, 0-9 y -",
    "carpeta cifrada, fuera de git",
    "ID de la autorización del cliente",
    "plazo de borrado (decisión D5)",
    "por ejemplo: manana=6-14,tarde=14-22",
    "casi duplicados a esta distancia dHash o menos (por omisión: 5)",
    "tope de imágenes guardadas",
    "hora del primer fotograma",
    "fecha cada fotograma con el reloj",
)
# Credenciales ficticias: el caso de prueba es justamente una URL con usuario y clave.
URL_CON_CREDENCIALES = "rtsp://admin:clave@10.0.0.5:554/stream"  # pragma: allowlist secret


def _video(carpeta: Path) -> Path:
    ruta = carpeta / "clip.avi"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), 2, (64, 48))
    for semilla in range(4):
        imagen = np.random.default_rng(semilla).integers(0, 256, (48, 64, 3), dtype=np.uint8)
        escritor.write(imagen)
    escritor.release()
    return ruta


def _argumentos(salida: Path, fuente: str, *modo: str) -> list[str]:
    return [
        *("--fuente", fuente, "--camara", "cam-01", "--salida", str(salida)),
        *("--autorizacion", "AUT-2026-001", "--retencion-dias", "30"),
        *("--turnos", "dia=6-18,noche=18-6", "--intervalo-segundos", "1"),
        *(modo or ("--inicio", INICIO.isoformat())),
    ]


def _nombres(salida: Path) -> list[str]:
    lineas = (salida / "metadatos.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linea)["file_name"] for linea in lineas]


def test_main_captura_un_video_grabado_y_resume_el_resultado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    salida = tmp_path / "crudo"

    codigo = main(_argumentos(salida, str(_video(tmp_path))))

    assert codigo == 0
    assert _nombres(salida) == [
        "cam-01_20261021_080000_0001.jpg",
        "cam-01_20261021_080001_0002.jpg",
    ]
    assert "Guardadas: 2; descartadas por casi duplicadas: 0" in capsys.readouterr().out


def test_main_en_vivo_usa_el_reloj_y_libera_la_camara(tmp_path: Path) -> None:
    imagenes = [np.full((48, 64, 3), valor, dtype=np.uint8) for valor in (0, 0)]
    camara = CapturaFalsa(imagenes)
    relojes = iter([INICIO, INICIO + timedelta(seconds=9)])

    codigo = main(
        _argumentos(tmp_path, "0", "--en-vivo"), abrir=lambda _: camara, reloj=relojes.__next__
    )

    assert (codigo, camara.liberada) == (0, True)
    assert _nombres(tmp_path) == ["cam-01_20261021_080000_0001.jpg"]


def test_main_libera_la_camara_aunque_la_captura_falle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "cam-01_20261021_080000_0001.jpg").write_bytes(b"previa")
    camara = CapturaFalsa([np.zeros((48, 64, 3), dtype=np.uint8)])

    codigo = main(_argumentos(tmp_path, "clip.avi"), abrir=lambda _: camara)

    assert (codigo, camara.liberada) == (CODIGO_DE_ERROR, True)
    assert capsys.readouterr().err == (
        "cam-01_20261021_080000_0001.jpg ya existe: la captura nunca sobrescribe imágenes.\n"
    )


def test_main_valida_la_configuracion_antes_de_abrir_la_fuente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argumentos = _argumentos(tmp_path, "clip.avi")
    argumentos[argumentos.index("--retencion-dias") + 1] = "0"

    codigo = main(argumentos, abrir=pytest.fail)

    assert codigo == CODIGO_DE_ERROR
    assert "PENDIENTE (D5)" in capsys.readouterr().err


@pytest.mark.parametrize(
    "falta",
    [
        "--fuente",
        "--camara",
        "--salida",
        "--autorizacion",
        "--retencion-dias",
        "--turnos",
        "--intervalo-segundos",
        "--inicio",
    ],
)
def test_main_exige_cada_parametro_obligatorio(tmp_path: Path, falta: str) -> None:
    argumentos = _argumentos(tmp_path, "clip.avi")
    posicion = argumentos.index(falta)
    del argumentos[posicion : posicion + 2]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == CODIGO_DE_ERROR


def test_main_exige_elegir_entre_video_grabado_y_camara_en_vivo(tmp_path: Path) -> None:
    argumentos = [*_argumentos(tmp_path, "0"), "--en-vivo"]

    with pytest.raises(SystemExit) as salida:
        main(argumentos)

    assert salida.value.code == CODIGO_DE_ERROR


def test_abrir_fuente_abre_un_video_y_falla_ante_uno_inexistente(tmp_path: Path) -> None:
    captura = abrir_fuente(str(_video(tmp_path)))
    leida, _ = captura.read()
    captura.release()

    assert leida is True
    with pytest.raises(CapturaInvalidaError) as error:
        abrir_fuente(str(tmp_path / "no-existe.avi"))
    assert str(error.value) == f"No se pudo abrir la fuente {tmp_path / 'no-existe.avi'}."


def test_main_explica_cada_parametro_en_la_ayuda(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    ayuda = " ".join(capsys.readouterr().out.split())
    assert [texto for texto in AYUDAS if texto not in ayuda] == []


def test_abrir_fuente_usa_el_indice_de_camara_cuando_la_fuente_es_un_numero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidas: list[object] = []

    class CapturaAbierta:
        def __init__(self, fuente: object) -> None:
            pedidas.append(fuente)

        def isOpened(self) -> bool:  # noqa: N802 - interfaz de cv2.VideoCapture
            return True

    monkeypatch.setattr(capturar_dataset.cv2, "VideoCapture", CapturaAbierta)

    abrir_fuente("2")
    abrir_fuente("rtsp://camara/1")

    assert pedidas == [2, "rtsp://camara/1"]


@pytest.mark.parametrize(
    ("fuente", "visible"),
    [
        (URL_CON_CREDENCIALES, "rtsp://***@10.0.0.5:554/stream"),
        ("rtsp://10.0.0.5/stream", "rtsp://10.0.0.5/stream"),
        ("D:/videos/clip.mp4", "D:/videos/clip.mp4"),
    ],
)
def test_ocultar_credenciales_borra_usuario_y_clave_de_la_url(fuente: str, visible: str) -> None:
    assert ocultar_credenciales(fuente) == visible


def test_el_modulo_se_ejecuta_como_programa() -> None:
    # S603: ejecuta el módulo propio con el mismo intérprete; argumentos fijos.
    resultado = subprocess.run(
        [sys.executable, "-m", "tools.capturar_dataset", "--help"],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=SEGUNDOS_MAXIMOS,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0
    assert "--retencion-dias" in resultado.stdout
