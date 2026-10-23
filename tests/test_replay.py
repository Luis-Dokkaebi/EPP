"""Replay de regresión sin cámara ni modelo (SPEC/9 §0.10 y §5.5, C-07).

El clip es sintético y se genera en la prueba (los clips reales dependen del modelo EPP, B-06):
un operario en "Pozo Ñandú" sin casco de t=0 a t=3 s y con casco de t=4 a t=15 s, un frame por
segundo. Los eventos esperados están en tests/fixtures/replay/*.expected.jsonl para revisarlos.
"""

import json
from pathlib import Path

import pytest

from tests.utilidades_scripts import ejecutar_modulo
from tools.replay import ConfiguracionReplayError, main

DORADOS = Path(__file__).parent / "fixtures" / "replay"
CONFIGURACION = {
    "ioa_minimo_ancla": 0.5,
    "ioa_minimo_epp": 0.5,
    "fraccion_ausente_minima": 0.8,
    "tiempo_confirmacion_s": 2.0,
    "presentes_para_recuperar": 2,
    "tiempo_limpieza_s": 10.0,
    "enfriamiento_s": 300.0,
    "version_modelo": "replay-sintetico",
    "epp_global": [],
    "cada_n_frames": 1,
}
ZONAS = {
    "version": 2,
    "zonas": {
        "Pozo Ñandú": {
            "poligono": [[0, 0], [640, 0], [640, 480], [0, 480]],
            "epp_requerido": ["casco"],
        }
    },
}
PERSONA = {"clase": "persona", "confianza": 0.9, "caja": [100, 50, 200, 350]}
CABEZA = {"clase": "cabeza", "confianza": 0.9, "caja": [135, 55, 165, 90]}
CASCO = {"clase": "casco", "confianza": 0.9, "caja": [133, 50, 167, 70]}


def _clip_casco(tmp_path: Path) -> Path:
    sin_casco = [{"t": float(t), "detecciones": [PERSONA, CABEZA]} for t in range(4)]
    con_casco = [{"t": float(t), "detecciones": [PERSONA, CABEZA, CASCO]} for t in range(4, 16)]
    ruta = tmp_path / "casco_sintetico.jsonl"
    ruta.write_text("\n".join(json.dumps(f) for f in sin_casco + con_casco), encoding="utf-8")
    return ruta


def _escribir(ruta: Path, contenido: object) -> Path:
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def _argumentos(tmp_path: Path, configuracion: object = CONFIGURACION) -> list[str]:
    return [
        str(_clip_casco(tmp_path)),
        str(_escribir(tmp_path / "zonas.json", ZONAS)),
        str(_escribir(tmp_path / "configuracion.json", configuracion)),
        str(tmp_path / "eventos.jsonl"),
    ]


def test_replay_del_clip_sintetico_emite_los_eventos_dorados(tmp_path: Path) -> None:
    codigo = main(_argumentos(tmp_path))

    eventos = (tmp_path / "eventos.jsonl").read_text(encoding="utf-8")
    esperados = (DORADOS / "casco_sintetico.expected.jsonl").read_text(encoding="utf-8")
    assert (codigo, eventos) == (0, esperados)


def test_replay_numera_los_tracks_por_orden_de_aparicion_en_el_clip(tmp_path: Path) -> None:
    # ByteTrack (supervision) numera con un contador global del proceso: sin renumerar, una
    # segunda corrida en el mismo proceso cambiaría los track_id de los eventos dorados.
    primera, segunda = tmp_path / "primera", tmp_path / "segunda"
    primera.mkdir()
    segunda.mkdir()
    main(_argumentos(primera))

    main(_argumentos(segunda))

    esperados = (DORADOS / "casco_sintetico.expected.jsonl").read_text(encoding="utf-8")
    assert (segunda / "eventos.jsonl").read_text(encoding="utf-8") == esperados


def test_replay_fuera_de_las_zonas_que_exigen_casco_no_emite_eventos(tmp_path: Path) -> None:
    argumentos = _argumentos(tmp_path)
    _escribir(Path(argumentos[1]), {"version": 2, "zonas": {}})

    main(argumentos)

    assert (tmp_path / "eventos.jsonl").read_text(encoding="utf-8") == ""


def test_replay_sin_un_umbral_falla_con_un_error_claro(tmp_path: Path) -> None:
    incompleta = {
        clave: valor for clave, valor in CONFIGURACION.items() if clave != "enfriamiento_s"
    }

    with pytest.raises(
        ConfiguracionReplayError, match=r"^Falta enfriamiento_s en la configuración"
    ):
        main(_argumentos(tmp_path, incompleta))


@pytest.mark.integration
def test_replay_como_programa_escribe_los_eventos(tmp_path: Path) -> None:
    resultado = ejecutar_modulo("tools.replay", *_argumentos(tmp_path))

    esperados = (DORADOS / "casco_sintetico.expected.jsonl").read_text(encoding="utf-8")
    eventos = (tmp_path / "eventos.jsonl").read_text(encoding="utf-8")
    assert (resultado.returncode, eventos) == (0, esperados), resultado.stderr


def test_replay_distingue_los_tracks_de_cada_operario(tmp_path: Path) -> None:
    otro = {"clase": "persona", "confianza": 0.9, "caja": [400, 50, 500, 350]}
    su_cabeza = {"clase": "cabeza", "confianza": 0.9, "caja": [435, 55, 465, 90]}
    dos = [{"t": float(t), "detecciones": [PERSONA, CABEZA, otro, su_cabeza]} for t in range(3)]
    argumentos = _argumentos(tmp_path)
    Path(argumentos[0]).write_text("\n".join(json.dumps(f) for f in dos), encoding="utf-8")

    main(argumentos)

    lineas = (tmp_path / "eventos.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(linea)["track_id"] for linea in lineas) == [1, 2]
