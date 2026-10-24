"""Caracterización de CameraWorker.run() antes de migrar el motor (SPEC/9 §1.3.1, A-09).

Fijan lo que hoy hace el worker con dobles de sus colaboradores (cámara, modelo, reloj, pipeline y
reconocedor facial). Deben pasar antes y después de cada paso de la migración: desde A-11 el worker
recibe un DetectorPort y solo cambió la fixture `crear_worker`, no las aserciones.
"""

import queue
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.types import CATALOGO_COCO, ClaseObjeto
from src.ppe.application.evaluar_cumplimiento import EstadoCumplimiento
from src.ppe.domain.elementos import ElementoEPP, EstadoElemento
from src.tracking import camera_worker as modulo_worker
from src.tracking.camera_worker import CameraWorker
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

CLASE_PERSONA = 0
CLASE_AUTO = 2
CLASE_CELULAR = 67
ALTO, ANCHO = 120, 640
BLANCO = 255
MARCA_TIEMPO = 1_000.0
FRAMES_ENTRE_RECARGAS = 60
ESPERA_RECONEXION_S = 2.0
FPS_POR_OMISION = 15


def frame_blanco() -> np.ndarray:
    return np.full((ALTO, ANCHO, 3), BLANCO, dtype=np.uint8)


class CapturaFalsa:
    """Entrega los frames dados y, al entregar el último, detiene el worker."""

    def __init__(self, frames: list[np.ndarray | None], al_agotarse: Callable[[], None]) -> None:
        self._frames = frames
        self._al_agotarse = al_agotarse
        self.abierta = True
        self.liberada = False

    def isOpened(self) -> bool:  # noqa: N802 - interfaz de cv2.VideoCapture
        return self.abierta

    def read(self) -> tuple[bool, np.ndarray | None]:
        frame = self._frames.pop(0)
        if not self._frames:
            self._al_agotarse()
        return frame is not None, frame

    def release(self) -> None:
        self.liberada = True


@dataclass
class RelojFalso:
    """Reemplaza al módulo `time` del worker: el tiempo solo avanza al dormir."""

    ahora: float = MARCA_TIEMPO
    esperas: list[float] = field(default_factory=list)

    def time(self) -> float:
        return self.ahora

    def sleep(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += segundos


@dataclass
class PipelineFalso:
    nombres: tuple[str, ...] = ()
    error: Exception | None = None
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)
    opciones: list[dict[str, Any]] = field(default_factory=list)
    filas: list[dict[str, Any]] | None = None

    def process(self, *argumentos: Any, **opciones: Any) -> list[dict[str, Any]]:
        self.llamadas.append(argumentos)
        self.opciones.append(opciones)
        if self.error is not None:
            raise self.error
        if self.filas is not None:
            return self.filas
        return [{"name": nombre} for nombre in self.nombres]


class ReconocedorFalso:
    def __init__(self, faces_dir: str) -> None:
        self.faces_dir = faces_dir
        self.known_face_names: list[str] = []
        self.recargas = 0

    def check_reload(self) -> None:
        self.recargas += 1


@dataclass
class Escenario:
    worker: CameraWorker
    cola: queue.Queue[tuple[int | str, np.ndarray]]
    modelo: ModeloFalso
    reloj: RelojFalso
    capturas: list[tuple[tuple[Any, ...], CapturaFalsa]]

    def encolados(self) -> list[tuple[int | str, np.ndarray]]:
        return [self.cola.get_nowait() for _ in range(self.cola.qsize())]


@pytest.fixture
def crear_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Callable[..., Escenario]:
    def _crear(  # noqa: PLR0913 - cada argumento es una perilla del escenario
        frames: list[np.ndarray | None],
        detecciones: list[DeteccionCruda] | None = None,
        camara: int | str = 0,
        verificacion: Callable[[str], bool] = lambda _ruta: True,
        tamano_cola: int = 0,
        camaras_caidas: frozenset[Any] = frozenset(),
    ) -> Escenario:
        monkeypatch.setattr("config.config.get_faces_dir", lambda: str(tmp_path))
        monkeypatch.setattr("config.config.get_db_path", _sin_tenant)
        monkeypatch.setattr("src.models.model_verifier.verify_model", verificacion)
        monkeypatch.setattr(modulo_worker, "FaceRecognizer", ReconocedorFalso)
        reloj = RelojFalso()
        monkeypatch.setattr(modulo_worker, "time", reloj)
        cola: queue.Queue[tuple[int | str, np.ndarray]] = queue.Queue(maxsize=tamano_cola)
        modelo = ModeloFalso(detecciones or [])
        detector = DetectorUltralytics(modelo, CATALOGO_COCO, confianza_minima=0.0)
        worker = CameraWorker(camera_id=camara, frame_queue=cola, detector=detector, fps_limit=10)
        capturas: list[tuple[tuple[Any, ...], CapturaFalsa]] = []

        def _abrir(*argumentos: Any) -> CapturaFalsa:
            captura = CapturaFalsa(frames, worker.stop)
            captura.abierta = argumentos[0] not in camaras_caidas
            capturas.append((argumentos, captura))
            return captura

        monkeypatch.setattr(modulo_worker.cv2, "VideoCapture", _abrir)
        return Escenario(worker, cola, modelo, reloj, capturas)

    return _crear


def _sin_tenant() -> str:
    raise RuntimeError("Tenant no montado")


def test_camera_worker_encola_un_frame_anotado_por_frame_leido(
    crear_worker: Callable[..., Escenario],
) -> None:
    frames = [frame_blanco() for _ in range(3)]
    escenario = crear_worker(frames=list(frames))

    escenario.worker.run()

    encolados = escenario.encolados()
    assert [camara for camara, _ in encolados] == [0, 0, 0]
    assert [anotado.shape for _, anotado in encolados] == [(ALTO, ANCHO, 3)] * 3
    assert escenario.modelo.frames_recibidos == frames


def test_camera_worker_pasa_al_pipeline_personas_de_clase_0_y_celulares_de_clase_67(
    crear_worker: Callable[..., Escenario],
) -> None:
    frame = frame_blanco()
    escenario = crear_worker(
        frames=[frame],
        detecciones=[
            DeteccionCruda(CLASE_PERSONA, (10.0, 20.0, 110.0, 220.0)),
            DeteccionCruda(CLASE_CELULAR, (5.7, 6.2, 30.9, 40.1)),
            DeteccionCruda(CLASE_AUTO, (1.0, 1.0, 2.0, 2.0)),
        ],
    )
    pipeline = PipelineFalso()
    escenario.worker.pipeline = pipeline

    escenario.worker.run()

    [(frame_recibido, personas, celulares, marca)] = pipeline.llamadas
    assert frame_recibido is frame
    assert personas.xyxy.tolist() == [[10.0, 20.0, 110.0, 220.0]]
    assert personas.class_id.tolist() == [CLASE_PERSONA]
    assert celulares == [(5, 6, 30, 40)]
    assert marca == MARCA_TIEMPO


def test_camera_worker_descarta_frames_cuando_la_cola_esta_llena(
    crear_worker: Callable[..., Escenario],
) -> None:
    frames = [np.full((ALTO, ANCHO, 3), valor, dtype=np.uint8) for valor in range(5)]
    escenario = crear_worker(frames=frames, tamano_cola=2)

    escenario.worker.run()

    encolados = escenario.encolados()
    assert [int(anotado[50, 50, 0]) for _, anotado in encolados] == [0, 1]


@pytest.mark.parametrize(
    "verificacion",
    [lambda _ruta: False, lambda ruta: (_ for _ in ()).throw(FileNotFoundError(ruta))],
    ids=["modelo-manipulado", "modelo-ausente"],
)
def test_camera_worker_no_inicia_si_el_modelo_no_paso_la_verificacion(
    crear_worker: Callable[..., Escenario], verificacion: Callable[[str], bool]
) -> None:
    escenario = crear_worker(frames=[frame_blanco()], verificacion=verificacion)

    escenario.worker.run()

    assert escenario.capturas == []
    assert escenario.cola.empty()
    assert escenario.worker.running is False


def test_camera_worker_sin_persistencia_sigue_mostrando_video(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])

    escenario.worker.run()

    assert escenario.worker.pipeline is None
    assert len(escenario.encolados()) == 1


def test_camera_worker_falla_del_pipeline_no_detiene_el_video(
    crear_worker: Callable[..., Escenario],
) -> None:
    frames = [frame_blanco(), frame_blanco()]
    escenario = crear_worker(frames=list(frames))
    escenario.worker.pipeline = PipelineFalso(error=RuntimeError("disco lleno"))

    escenario.worker.run()

    assert len(escenario.encolados()) == len(frames)


def test_camera_worker_muestra_el_nombre_reconocido_en_un_cartel(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])
    escenario.worker.pipeline = PipelineFalso(nombres=("Unknown", "Ana"))

    escenario.worker.run()

    [(_, anotado)] = escenario.encolados()
    assert escenario.worker.last_name == "Ana"
    assert anotado[12, 12].tolist() == [0, 0, 0]
    assert anotado[100, 600].tolist() == [BLANCO] * 3


def test_camera_worker_sin_nombre_reconocido_no_dibuja_cartel(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])
    escenario.worker.pipeline = PipelineFalso(nombres=("Unknown",))

    escenario.worker.run()

    [(_, anotado)] = escenario.encolados()
    assert escenario.worker.last_name == "Unknown"
    assert anotado[12, 12].tolist() == [BLANCO] * 3


@pytest.mark.parametrize(
    ("cantidad", "recargas"),
    [(FRAMES_ENTRE_RECARGAS - 1, 0), (FRAMES_ENTRE_RECARGAS, 1), (2 * FRAMES_ENTRE_RECARGAS, 2)],
)
def test_camera_worker_recarga_los_rostros_cada_60_frames(
    crear_worker: Callable[..., Escenario], cantidad: int, recargas: int
) -> None:
    pequeno = np.zeros((2, 2, 3), dtype=np.uint8)
    escenario = crear_worker(frames=[pequeno] * cantidad)

    escenario.worker.run()

    assert escenario.worker.face_rec.recargas == recargas


def test_camera_worker_limita_los_fps_durmiendo_el_resto_del_periodo(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco(), frame_blanco()])

    escenario.worker.run()

    assert escenario.reloj.esperas == [pytest.approx(0.1)] * 2


def test_camera_worker_reconecta_tras_una_lectura_fallida(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[None, frame_blanco()])

    escenario.worker.run()

    assert escenario.reloj.esperas[0] == ESPERA_RECONEXION_S
    assert [argumentos for argumentos, _ in escenario.capturas] == [
        (0, modulo_worker.cv2.CAP_DSHOW),
        (0, modulo_worker.cv2.CAP_DSHOW),
    ]


def test_camera_worker_abre_una_url_sin_backend_de_directshow(
    crear_worker: Callable[..., Escenario],
) -> None:
    url = "rtsp://camara.local/flujo"
    escenario = crear_worker(frames=[frame_blanco()], camara=url)

    escenario.worker.run()

    assert [argumentos for argumentos, _ in escenario.capturas] == [(url,)]
    assert [camara for camara, _ in escenario.encolados()] == [url]


def test_camera_worker_busca_una_camara_de_respaldo_si_la_pedida_falla(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()], camara=5, camaras_caidas=frozenset({5, 0}))

    escenario.worker.run()

    assert escenario.worker.camera_id == 1
    assert [camara for camara, _ in escenario.encolados()] == [1]


def test_camera_worker_por_omision_limita_a_15_fps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr("config.config.get_faces_dir", lambda: str(tmp_path))
    monkeypatch.setattr("config.config.get_db_path", _sin_tenant)
    monkeypatch.setattr(modulo_worker, "FaceRecognizer", ReconocedorFalso)

    worker = CameraWorker(0, queue.Queue(), DetectorUltralytics(ModeloFalso([]), CATALOGO_COCO, 0))

    assert worker.fps_limit == FPS_POR_OMISION


def test_camera_worker_libera_la_captura_al_detenerse(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])

    escenario.worker.run()

    assert [captura.liberada for _, captura in escenario.capturas] == [True]


# --- SPEC/9 §5.1 y §8.1: el módulo de EPP en el worker ---

ROJO = [0, 0, 255]


def test_camera_worker_pasa_al_pipeline_todas_las_detecciones_del_frame(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(
        frames=[frame_blanco()],
        detecciones=[
            DeteccionCruda(CLASE_PERSONA, (10.0, 20.0, 110.0, 100.0)),
            DeteccionCruda(CLASE_CELULAR, (5.0, 6.0, 30.0, 40.0)),
        ],
    )
    pipeline = PipelineFalso()
    escenario.worker.pipeline = pipeline

    escenario.worker.run()

    [opciones] = pipeline.opciones
    assert [d.clase for d in opciones["detecciones"]] == [ClaseObjeto.PERSONA, ClaseObjeto.CELULAR]


def test_camera_worker_dibuja_en_rojo_a_quien_tiene_una_infraccion_de_epp(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])
    estado = EstadoCumplimiento(1, {ElementoEPP.CASCO: EstadoElemento.AUSENTE},
                                frozenset({ElementoEPP.CASCO}))  # fmt: skip
    escenario.worker.pipeline = PipelineFalso(
        filas=[{"name": "Unknown", "bbox": (10, 20, 110, 100), "epp": estado}]
    )

    escenario.worker.run()

    [(_, anotado)] = escenario.encolados()
    assert anotado[20, 60].tolist() == ROJO


def test_camera_worker_sin_estado_de_epp_no_dibuja_el_overlay(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])
    escenario.worker.pipeline = PipelineFalso(
        filas=[{"name": "Unknown", "bbox": (10, 20, 110, 100), "epp": None}]
    )

    escenario.worker.run()

    [(_, anotado)] = escenario.encolados()
    assert anotado[20, 60].tolist() == [BLANCO] * 3


def test_camera_worker_entrega_el_modulo_de_epp_al_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr("config.config.get_faces_dir", lambda: str(tmp_path))
    monkeypatch.setattr("config.config.get_db_path", lambda: str(tmp_path / "db" / "t.db"))
    monkeypatch.setattr("config.config.get_zonas_file", lambda: str(tmp_path / "zonas.json"))
    monkeypatch.setattr("config.config.get_snapshots_dir", lambda: str(tmp_path / "snapshots"))
    monkeypatch.setattr(modulo_worker, "FaceRecognizer", ReconocedorFalso)
    modulo_epp = object()
    detector = DetectorUltralytics(ModeloFalso([]), CATALOGO_COCO, 0)

    worker = CameraWorker(0, queue.Queue(), detector)

    worker.conectar_epp(modulo_epp)

    assert worker.pipeline.epp is modulo_epp


def test_camera_worker_sin_sucursal_no_conecta_el_modulo_de_epp(
    crear_worker: Callable[..., Escenario],
) -> None:
    escenario = crear_worker(frames=[frame_blanco()])

    escenario.worker.conectar_epp(object())

    assert escenario.worker.pipeline is None
