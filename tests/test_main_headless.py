"""Caracterización del modo headless (`src/main.py`) antes de migrar el motor (SPEC/9 §1.3.5).

Mismo criterio que las pruebas de CameraWorker: la fixture cambia de motor, las aserciones no.
"""

import subprocess
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from config.path_utils import ConfigManager
from src import main
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

MODULO_EPP = "modulo-epp"
VERDE = (0, 255, 0)
INDICE_LOCAL = 5
TECLA_Q_CON_MODIFICADOR = 0x100 | ord("q")
CLASE_PERSONA = 0
CLASE_CELULAR = 67
UMBRAL = 0.4
MARCA_TIEMPO = 2_000.0


class CapturaFalsa:
    def __init__(self, frames: list[np.ndarray], abierta: bool = True) -> None:
        self._frames = frames
        self._abierta = abierta
        self.liberada = False

    def isOpened(self) -> bool:  # noqa: N802 - interfaz de cv2.VideoCapture
        return self._abierta

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.liberada = True


@dataclass
class PipelineFalso:
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)

    def __init__(self, pistas: list[dict[str, Any]], **colaboradores: Any) -> None:
        self.colaboradores = colaboradores
        self.llamadas = []
        self.opciones: list[dict[str, Any]] = []
        self._pistas = pistas

    def process(self, *argumentos: Any, **opciones: Any) -> list[dict[str, Any]]:
        self.llamadas.append(argumentos)
        self.opciones.append(opciones)
        return self._pistas


class EstadosFalsos:
    """StateManager falso: todos trabajan y se pintan de verde; anota por quién se preguntó."""

    def __init__(self) -> None:
        self.consultados: list[str] = []

    def get_state(self, nombre: str) -> str:
        self.consultados.append(nombre)
        return "Trabajando"

    def get_color_for_state(self, _estado: str) -> tuple[int, int, int]:
        return VERDE


class LicenciaFalsa:
    def __init__(self, *modulos: str) -> None:
        self._modulos = modulos

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo in self._modulos


class DespachadorFalso:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def iniciar(self) -> None:
        self.eventos.append("iniciar")

    def detener(self, espera_maxima: timedelta) -> None:
        self.eventos.append(f"detener {espera_maxima.total_seconds():.0f} s")


@dataclass
class Corrida:
    pipelines: list[PipelineFalso]
    capturas: list[CapturaFalsa]
    ventanas_cerradas: list[bool]
    despachador: DespachadorFalso = field(default_factory=DespachadorFalso)
    mostrados: list[Any] = field(default_factory=list)
    ventanas: list[str] = field(default_factory=list)
    esperas_ms: list[int] = field(default_factory=list)
    fuentes: list[object] = field(default_factory=list)
    estados: "EstadosFalsos" = field(default_factory=lambda: EstadosFalsos())

    def llamadas(self) -> list[tuple[Any, ...]]:
        [pipeline] = self.pipelines
        return pipeline.llamadas


@pytest.fixture
def licencia() -> LicenciaFalsa:
    """Sin el módulo de EPP por omisión; una prueba la reemplaza parametrizando `licencia`."""
    return LicenciaFalsa()


@pytest.fixture
def camara_elegida() -> str | None:
    """La cámara que la GUI le pasa al modo sin interfaz; None para que la busque sola."""
    return "0"


@pytest.fixture
def tecla() -> int:
    """Lo que devuelve `cv2.waitKey` en cada cuadro: 0 si no se tocó ninguna tecla."""
    return 0


@dataclass(frozen=True)
class EntornoDeCorrida:
    camara_elegida: str | None
    tecla: int


@pytest.fixture
def entorno_de_corrida(camara_elegida: str | None, tecla: int) -> EntornoDeCorrida:
    return EntornoDeCorrida(camara_elegida, tecla)


@pytest.fixture
def correr_headless(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    licencia: LicenciaFalsa,
    entorno_de_corrida: EntornoDeCorrida,
) -> Callable[..., Corrida]:
    def _correr(
        frames: list[np.ndarray],
        detecciones: list[DeteccionCruda],
        pistas: list[dict[str, Any]] | None = None,
    ) -> Corrida:
        modelo = ModeloFalso(detecciones)
        # Paquete `ultralytics` falso: la prueba no importa el motor real ni carga pesos.
        monkeypatch.setitem(
            sys.modules, "ultralytics", types.SimpleNamespace(YOLO=lambda _r: modelo)
        )
        corrida = Corrida(pipelines=[], capturas=[], ventanas_cerradas=[])
        _aislar_entorno(monkeypatch, tmp_path, entorno_de_corrida.camara_elegida)
        monkeypatch.setattr(main, "StateManager", lambda _bd: corrida.estados)
        monkeypatch.setattr(main.time, "time", lambda: MARCA_TIEMPO)
        monkeypatch.setattr(main.cv2, "VideoCapture", _fabrica(corrida, frames))
        monkeypatch.setattr(main.cv2, "imshow", _mostrar_en(corrida))
        _conectar_epp(monkeypatch, licencia, corrida.despachador)
        monkeypatch.setattr(main.cv2, "waitKey", _esperar_en(corrida, entorno_de_corrida.tecla))
        monkeypatch.setattr(
            main.cv2, "destroyAllWindows", lambda: corrida.ventanas_cerradas.append(True)
        )
        monkeypatch.setattr(
            "src.tracking.tracking_pipeline.TrackingPipeline",
            lambda **colaboradores: _registrar(
                corrida.pipelines, PipelineFalso(pistas or [], **colaboradores)
            ),
        )
        main.start_video_stream()
        return corrida

    return _correr


def _conectar_epp(
    monkeypatch: pytest.MonkeyPatch, licencia: LicenciaFalsa, despachador: DespachadorFalso
) -> None:
    """Licencia del equipo, módulo de EPP y avisos falsos: se ve qué arma el modo sin interfaz."""
    monkeypatch.setattr(main, "licencia_del_equipo", lambda: licencia)
    monkeypatch.setattr(
        "src.composicion_epp.crear_integracion_epp_de_la_app",
        lambda _publicador, lic: MODULO_EPP if lic.incluye_modulo("epp") else None,
    )

    def iniciar_avisos() -> DespachadorFalso:
        despachador.iniciar()
        return despachador

    monkeypatch.setattr("src.composicion_avisos.iniciar_avisos_de_la_sucursal", iniciar_avisos)


def _mostrar_en(corrida: Corrida) -> Callable[[str, Any], None]:
    def mostrar(ventana: str, cuadro: Any) -> None:
        corrida.ventanas.append(ventana)
        corrida.mostrados.append(cuadro)

    return mostrar


def _esperar_en(corrida: Corrida, tecla: int) -> Callable[[int], int]:
    def esperar(milisegundos: int) -> int:
        corrida.esperas_ms.append(milisegundos)
        return tecla

    return esperar


def _aislar_entorno(
    monkeypatch: pytest.MonkeyPatch, carpeta: Path, camara_elegida: str | None = "0"
) -> None:
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Prueba_Headless")
    monkeypatch.delenv("OE_TENANT_ID", raising=False)
    monkeypatch.delenv("SELECTED_CAMERA_INDEX", raising=False)
    if camara_elegida is not None:
        monkeypatch.setenv("SELECTED_CAMERA_INDEX", camara_elegida)
    monkeypatch.setattr(main.config, "LOCAL_CAMERA_INDEX", INDICE_LOCAL)
    monkeypatch.setattr(main.config, "get_zonas_file", lambda: str(carpeta / "zonas.json"))
    monkeypatch.setattr(main.config, "get_snapshots_dir", lambda: str(carpeta / "capturas"))
    monkeypatch.setattr(main.config, "get_db_path", lambda: str(carpeta / "bd.sqlite"))
    monkeypatch.setattr(main.config, "CONFIDENCE_THRESHOLD", UMBRAL)
    monkeypatch.setattr(main, "DatabaseManager", lambda db_path: object())
    monkeypatch.setattr(main, "FaceRecognizer", lambda: object())
    monkeypatch.setattr(main, "StateManager", lambda _bd: EstadosFalsos())


def _fabrica(corrida: Corrida, frames: list[np.ndarray]) -> Callable[..., Any]:
    def _abrir(fuente: object) -> CapturaFalsa:
        captura = CapturaFalsa([np.zeros((4, 4, 3), dtype=np.uint8), *frames])
        corrida.fuentes.append(fuente)
        corrida.capturas.append(captura)
        return captura

    return _abrir


def _registrar(pipelines: list[PipelineFalso], pipeline: PipelineFalso) -> PipelineFalso:
    pipelines.append(pipeline)
    return pipeline


def test_headless_procesa_cada_frame_leido_despues_del_frame_de_prueba(
    correr_headless: Callable[..., Corrida],
) -> None:
    frames = [np.full((4, 4, 3), valor, dtype=np.uint8) for valor in (1, 2)]

    corrida = correr_headless(frames=list(frames), detecciones=[])

    assert [llamada[0] for llamada in corrida.llamadas()] == frames
    assert [llamada[3] for llamada in corrida.llamadas()] == [MARCA_TIEMPO] * 2


def test_headless_entrega_personas_y_celulares_por_encima_del_umbral(
    correr_headless: Callable[..., Corrida],
) -> None:
    detecciones = [
        DeteccionCruda(CLASE_PERSONA, (10.0, 20.0, 110.0, 220.0), 0.9),
        DeteccionCruda(CLASE_PERSONA, (1.0, 1.0, 2.0, 2.0), 0.3),
        DeteccionCruda(CLASE_CELULAR, (5.7, 6.2, 30.9, 40.1), 0.8),
        DeteccionCruda(CLASE_CELULAR, (7.0, 7.0, 9.0, 9.0), 0.1),
    ]

    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=detecciones)

    [(_, personas, celulares, _)] = corrida.llamadas()
    assert personas.xyxy.tolist() == [[10.0, 20.0, 110.0, 220.0]]
    assert celulares == [(5, 6, 30, 40)]


def test_headless_libera_la_camara_y_cierra_las_ventanas_al_terminar(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[], detecciones=[])

    assert [captura.liberada for captura in corrida.capturas] == [True]
    assert corrida.ventanas_cerradas == [True]


# --- Módulo de EPP en el modo sin interfaz (SPEC/9 §11, 5.4: un solo camino con la GUI) --------


def test_headless_sin_licencia_de_epp_no_evalua_ni_avisa(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=[])

    [pipeline] = corrida.pipelines
    assert pipeline.colaboradores["epp"] is None
    assert corrida.despachador.eventos == []


@pytest.mark.parametrize("licencia", [LicenciaFalsa("epp")], ids=["con_epp"])
def test_headless_con_licencia_de_epp_evalua_con_todas_las_detecciones(
    correr_headless: Callable[..., Corrida],
) -> None:
    detecciones = [
        DeteccionCruda(CLASE_PERSONA, (10.0, 20.0, 110.0, 220.0), 0.9),
        DeteccionCruda(CLASE_CELULAR, (5.7, 6.2, 30.9, 40.1), 0.8),
    ]

    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=detecciones)

    [pipeline] = corrida.pipelines
    [opciones] = pipeline.opciones
    assert pipeline.colaboradores["epp"] == MODULO_EPP
    assert [d.clase for d in opciones["detecciones"]] == ["persona", "celular"]


@pytest.mark.parametrize("licencia", [LicenciaFalsa("epp")], ids=["con_epp"])
def test_headless_con_licencia_de_epp_arranca_los_avisos_y_los_detiene_al_terminar(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[], detecciones=[])

    assert corrida.despachador.eventos == ["iniciar", "detener 10 s"]


def test_headless_muestra_el_cuadro_con_el_estado_de_epp_dibujado(
    correr_headless: Callable[..., Corrida], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "dibujar_epp", lambda _cuadro, _datos: "cuadro con EPP")

    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=[])

    assert corrida.mostrados == ["cuadro con EPP"]


class ValidadorFalso:
    def __init__(self) -> None:
        self.validada = False

    def validate_license(self) -> bool:
        self.validada = True
        return False


def test_la_licencia_del_equipo_se_valida_antes_de_usarla(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.security.drm.DRMValidator", ValidadorFalso)

    licencia = main.licencia_del_equipo()

    assert isinstance(licencia, ValidadorFalso)
    assert licencia.validada is True


def test_headless_dibuja_a_cada_persona_con_el_color_de_su_estado(
    correr_headless: Callable[..., Corrida],
) -> None:
    pista = {"bbox": (1, 1, 6, 6), "name": "Ana"}
    cuadro = np.zeros((8, 8, 3), dtype=np.uint8)

    corrida = correr_headless(frames=[cuadro], detecciones=[], pistas=[pista])

    [mostrado] = corrida.mostrados
    assert tuple(mostrado[1, 1]) == VERDE


def _no_debe_armarse(**_colaboradores: Any) -> None:
    pytest.fail("sin cámara no se arma el pipeline")


# --- Caracterización del modo sin interfaz heredado (lo que el formato dejó en el diff) ----------


def test_headless_usa_el_tenant_del_entorno_o_el_de_omision(
    correr_headless: Callable[..., Corrida], monkeypatch: pytest.MonkeyPatch
) -> None:
    correr_headless(frames=[], detecciones=[])
    por_omision = ConfigManager.get_active_tenant()
    monkeypatch.setenv("OE_TENANT_ID", "Sucursal_7")

    main.start_video_stream()

    assert (por_omision, ConfigManager.get_active_tenant()) == ("Default", "Sucursal_7")


@pytest.mark.parametrize("camara_elegida", ["3"], ids=["elegida"])
def test_headless_abre_la_camara_que_eligio_la_gui(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[], detecciones=[])

    assert corrida.fuentes == [3]


@pytest.mark.parametrize("camara_elegida", [None], ids=["sin_eleccion"])
@pytest.mark.parametrize(
    ("modo", "fuente"),
    [("local", INDICE_LOCAL), ("remoto", "rtsp://camara/flujo")],
    ids=["local", "remota"],
)
def test_headless_sin_camara_elegida_prueba_primero_la_de_la_configuracion(
    correr_headless: Callable[..., Corrida],
    monkeypatch: pytest.MonkeyPatch,
    modo: str,
    fuente: object,
) -> None:
    monkeypatch.setattr(main.config, "REMOTE_CAMERA_URL", "rtsp://camara/flujo")
    monkeypatch.setattr(main.config, "MODE", modo)

    corrida = correr_headless(frames=[], detecciones=[])

    assert corrida.fuentes[0] == fuente


def test_headless_reconoce_y_escribe_en_cada_cuadro(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[], detecciones=[])

    [pipeline] = corrida.pipelines
    intervalos = (
        pipeline.colaboradores["db_write_interval"],
        pipeline.colaboradores["face_check_interval"],
    )
    assert intervalos == (1, 1)


def test_headless_consulta_el_estado_por_el_nombre_de_cada_persona(
    correr_headless: Callable[..., Corrida],
) -> None:
    pista = {"bbox": (1, 1, 6, 6), "name": "Ana"}
    cuadro = np.zeros((8, 8, 3), dtype=np.uint8)

    corrida = correr_headless(frames=[cuadro], detecciones=[], pistas=[pista])

    assert corrida.estados.consultados == ["Ana"]


def test_headless_muestra_la_ventana_y_espera_un_milisegundo_por_cuadro(
    correr_headless: Callable[..., Corrida],
) -> None:
    corrida = correr_headless(frames=[np.zeros((4, 4, 3), dtype=np.uint8)], detecciones=[])

    assert corrida.ventanas == ["Sistema de Monitoreo Completo"]
    assert corrida.esperas_ms == [1]


@pytest.mark.parametrize("tecla", [TECLA_Q_CON_MODIFICADOR], ids=["q"])
def test_headless_se_detiene_con_la_tecla_q_aunque_venga_con_modificadores(
    correr_headless: Callable[..., Corrida],
) -> None:
    cuadros = [np.zeros((4, 4, 3), dtype=np.uint8) for _ in range(3)]

    corrida = correr_headless(frames=cuadros, detecciones=[])

    assert len(corrida.llamadas()) == 1


def test_headless_sin_camara_avisa_y_no_arma_el_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _aislar_entorno(monkeypatch, tmp_path)
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _fuente: CapturaFalsa([], abierta=False))
    monkeypatch.setattr("src.tracking.tracking_pipeline.TrackingPipeline", _no_debe_armarse)

    main.start_video_stream()

    assert capsys.readouterr().out.splitlines()[-1] == (
        "❌ Error: No se pudo detectar ninguna cámara (ni local ni externa). Revisar conexiones."
    )


def test_el_script_encuentra_el_proyecto_aunque_se_lance_desde_otra_carpeta(
    tmp_path: Path,
) -> None:
    raiz = Path(main.__file__).resolve().parents[1]
    codigo = (
        "import runpy, sys; "
        f"sys.path = [p for p in sys.path if p not in ('', {str(raiz)!r})]; "
        f"runpy.run_path({str(raiz / 'src' / 'main.py')!r}, run_name='prueba')"
    )

    resultado = subprocess.run(
        [sys.executable, "-c", codigo],  # noqa: S603 - intérprete y código fijos de la prueba
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr.decode()
