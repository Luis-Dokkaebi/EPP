"""Captura del dataset: imágenes, metadatos, privacidad y fuentes de video (SPEC/9 §2.4 y §2.6)."""

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from ml.contrato_datos import TAXONOMIA_V1, categorias, validar_anotaciones
from tests.utilidades_scripts import RAIZ
from tools import capturar_dataset
from tools.capturar_dataset import (
    CapturaInvalidaError,
    ConfiguracionDeCaptura,
    Fotograma,
    TablaDeTurnos,
    capturar,
    fotogramas_de_archivo,
    fotogramas_en_vivo,
)

INICIO = datetime(2026, 10, 21, 13, 59, 58)
LADO_MINIMO = 10.0
MAXIMO = 2


def _imagen(semilla: int) -> np.ndarray:
    return np.random.default_rng(semilla).integers(0, 256, (48, 64, 3), dtype=np.uint8)


def _fotogramas(*semillas: int) -> list[Fotograma]:
    return [
        Fotograma(INICIO + timedelta(seconds=segundo), _imagen(semilla))
        for segundo, semilla in enumerate(semillas)
    ]


def _configuracion(salida: Path, **cambios: Any) -> ConfiguracionDeCaptura:
    valores = {
        "camara": "cam-01",
        "salida": salida,
        "autorizacion": "AUT-2026-001",
        "retencion_dias": 30,
        "turnos": TablaDeTurnos.desde_texto("manana=6-14,tarde=14-22,noche=22-6"),
        "intervalo": timedelta(seconds=1),
        "distancia_maxima": 5,
        "maximo_de_imagenes": None,
    }
    return ConfiguracionDeCaptura(**{**valores, **cambios})


def _metadatos(salida: Path) -> list[dict[str, Any]]:
    lineas = (salida / "metadatos.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linea) for linea in lineas]


def test_capturar_guarda_cada_imagen_con_su_linea_de_metadatos(tmp_path: Path) -> None:
    resumen = capturar(_fotogramas(1, 2, 3), _configuracion(tmp_path))

    assert (resumen.guardadas, resumen.duplicadas) == (3, 0)
    assert [registro["file_name"] for registro in _metadatos(tmp_path)] == [
        "cam-01_20261021_135958_0001.jpg",
        "cam-01_20261021_135959_0002.jpg",
        "cam-01_20261021_140000_0003.jpg",
    ]


def test_capturar_registra_turno_hash_tamano_y_fecha_de_borrado(tmp_path: Path) -> None:
    capturar(_fotogramas(1, 2, 3), _configuracion(tmp_path))

    primero, _, tercero = _metadatos(tmp_path)
    contenido = (tmp_path / primero["file_name"]).read_bytes()
    assert primero["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert (primero["turno"], tercero["turno"]) == ("manana", "tarde")
    assert (primero["width"], primero["height"]) == (64, 48)
    assert primero["autorizacion"] == "AUT-2026-001"
    assert primero["eliminar_despues_de"] == (date(2026, 10, 21) + timedelta(days=30)).isoformat()


def test_capturar_produce_metadatos_que_cumplen_el_contrato_de_datos(tmp_path: Path) -> None:
    capturar(_fotogramas(1, 2), _configuracion(tmp_path))
    imagenes = [{"id": indice, **registro} for indice, registro in enumerate(_metadatos(tmp_path))]

    coco = {"images": imagenes, "annotations": [], "categories": categorias(TAXONOMIA_V1)}

    validar_anotaciones(coco, TAXONOMIA_V1, LADO_MINIMO)


def test_capturar_descarta_los_casi_duplicados(tmp_path: Path) -> None:
    resumen = capturar(_fotogramas(1, 1, 2, 1), _configuracion(tmp_path))

    assert (resumen.guardadas, resumen.duplicadas) == (2, 2)
    assert len(list(tmp_path.glob("*.jpg"))) == resumen.guardadas


def test_capturar_respeta_el_intervalo_de_muestreo(tmp_path: Path) -> None:
    resumen = capturar(_fotogramas(1, 2, 3, 4), _configuracion(tmp_path, intervalo=timedelta(2)))

    assert resumen.guardadas == 1


def test_capturar_se_detiene_en_el_maximo_de_imagenes(tmp_path: Path) -> None:
    resumen = capturar(_fotogramas(1, 2, 3, 4), _configuracion(tmp_path, maximo_de_imagenes=MAXIMO))

    assert resumen.guardadas == len(_metadatos(tmp_path)) == MAXIMO


def test_capturar_nunca_sobrescribe_una_imagen_existente(tmp_path: Path) -> None:
    (tmp_path / "cam-01_20261021_135958_0001.jpg").write_bytes(b"previa")

    with pytest.raises(CapturaInvalidaError, match="ya existe"):
        capturar(_fotogramas(1), _configuracion(tmp_path))

    assert (tmp_path / "cam-01_20261021_135958_0001.jpg").read_bytes() == b"previa"


def test_capturar_agrega_al_archivo_de_metadatos_existente(tmp_path: Path) -> None:
    capturar(_fotogramas(1), _configuracion(tmp_path, camara="cam-01"))

    capturar(_fotogramas(2), _configuracion(tmp_path, camara="cam-02"))

    assert [registro["camara"] for registro in _metadatos(tmp_path)] == ["cam-01", "cam-02"]


@pytest.mark.parametrize("autorizacion", ["", "   "])
def test_configuracion_exige_la_autorizacion_escrita_del_cliente(
    tmp_path: Path, autorizacion: str
) -> None:
    with pytest.raises(CapturaInvalidaError, match="autorización escrita"):
        _configuracion(tmp_path, autorizacion=autorizacion)


@pytest.mark.parametrize("dias", [0, -1])
def test_configuracion_exige_un_plazo_de_retencion_positivo(tmp_path: Path, dias: int) -> None:
    with pytest.raises(CapturaInvalidaError, match=r"PENDIENTE \(D5\)"):
        _configuracion(tmp_path, retencion_dias=dias)


@pytest.mark.parametrize("maximo", [0, -3])
def test_configuracion_exige_un_maximo_positivo(tmp_path: Path, maximo: int) -> None:
    with pytest.raises(CapturaInvalidaError, match="máximo de imágenes debe ser positivo"):
        _configuracion(tmp_path, maximo_de_imagenes=maximo)


@pytest.mark.parametrize("dentro", [RAIZ, RAIZ / "data" / "dataset"])
def test_configuracion_se_niega_a_guardar_imagenes_dentro_del_repositorio(dentro: Path) -> None:
    with pytest.raises(CapturaInvalidaError, match="nunca van a git"):
        _configuracion(dentro)


class CapturaFalsa:
    """Doble de cv2.VideoCapture: entrega las imágenes dadas y luego informa el fin."""

    def __init__(self, imagenes: list[np.ndarray], fps: float = 5.0) -> None:
        self._pendientes = list(imagenes)
        self._fps = fps
        self.liberada = False

    def read(self) -> tuple[bool, np.ndarray | None]:
        return (True, self._pendientes.pop(0)) if self._pendientes else (False, None)

    def get(self, propiedad: int) -> float:
        assert propiedad == cv2.CAP_PROP_FPS
        return self._fps

    def release(self) -> None:
        self.liberada = True


def test_fotogramas_de_archivo_fecha_cada_fotograma_segun_los_fps() -> None:
    captura = CapturaFalsa([_imagen(1), _imagen(2), _imagen(3)], fps=4.0)

    momentos = [fotograma.momento for fotograma in fotogramas_de_archivo(captura, INICIO)]

    assert momentos == [INICIO + timedelta(seconds=segundos) for segundos in (0, 0.25, 0.5)]


@pytest.mark.parametrize("fps", [0.0, -1.0, float("nan")])
def test_fotogramas_de_archivo_falla_si_la_fuente_no_informa_fps(fps: float) -> None:
    with pytest.raises(CapturaInvalidaError, match="no informa sus FPS"):
        list(fotogramas_de_archivo(CapturaFalsa([_imagen(1)], fps=fps), INICIO))


def test_fotogramas_en_vivo_usa_el_reloj_y_termina_cuando_la_camara_deja_de_entregar() -> None:
    relojes = iter([INICIO, INICIO + timedelta(seconds=7)])

    fotogramas = list(fotogramas_en_vivo(CapturaFalsa([_imagen(1), _imagen(2)]), relojes.__next__))

    assert [fotograma.momento for fotograma in fotogramas] == [
        INICIO,
        INICIO + timedelta(seconds=7),
    ]


def test_fotogramas_de_un_video_sintetico_real_se_leen_en_orden(tmp_path: Path) -> None:
    ruta = tmp_path / "clip.avi"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), 2, (32, 24))
    for valor in (0, 100, 200):
        escritor.write(np.full((24, 32, 3), valor, dtype=np.uint8))
    escritor.release()
    captura = cv2.VideoCapture(str(ruta))

    fotogramas = list(fotogramas_de_archivo(captura, INICIO))
    captura.release()

    assert [int(fotograma.imagen.mean() // 50) for fotograma in fotogramas] == [0, 2, 4]
    assert fotogramas[-1].momento == INICIO + timedelta(seconds=1)


def test_capturar_falla_ruidosamente_si_opencv_no_codifica_el_jpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capturar_dataset.cv2, "imencode", lambda *_: (False, None))

    with pytest.raises(CapturaInvalidaError, match="no pudo codificar"):
        capturar(_fotogramas(1), _configuracion(tmp_path))

    assert list(tmp_path.glob("*.jpg")) == []
