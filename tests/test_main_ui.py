"""Regresión: el resultado del escaneo de cámaras llega a la UI por el hilo de Tk.

El escaneo corre en un hilo de fondo. Si ese hilo llama a Tk (p. ej. `after`), el intérprete
Tcl se usa desde dos hilos a la vez: con Tcl 9, _tkinter no detecta `tcl_platform(threaded)`
y no serializa la llamada, y la suite abortaba con Segmentation fault / Illegal instruction.
Refs: SPEC/9_PLAN_EPP_Y_LICENCIA.md §0.3.
"""

import contextlib
import tkinter
from collections.abc import Callable, Iterator
from pathlib import Path

import customtkinter as ctk
import numpy as np
import pytest

from config.path_utils import ConfigManager
from src.composicion_epp import PublicadorEnMemoria
from src.main_ui import AppMain
from tests.dobles_main_ui import (
    Camaras,
    DespachadorFalso,
    EscaneoEnHiloFalso,
    FabricaDeTrabajadoresFalsa,
    LicenciaConEficiencia,
    LicenciaConEPP,
)
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

INDICES_DE_CAMARA_A_REVISAR = 10
FPS_DE_LA_GUI = 15
CONFIANZA_BAJA = 0.125
# Solo se agota si la condición esperada nunca se cumple, es decir, si la prueba va a fallar.
PLAZO_BUCLE_TK_MS = 5000
INTERVALO_REVISION_MS = 10
CAMARA_3: dict[str, object] = {
    "index": 3,
    "name": "Cámara 3",
    "width": 640,
    "height": 480,
    "backend": "V4L2",
    "label": "Cámara 3 (640x480, V4L2)",
}


def modelo_yolo_falso(_ruta_modelo: str) -> ModeloFalso:
    """Doble de `ultralytics.YOLO`: la prueba no carga pesos reales (CLAUDE.md §16)."""
    return ModeloFalso([DeteccionCruda(0, (1.0, 2.0, 3.0, 4.0), CONFIANZA_BAJA)])


def modelo_que_no_carga(_ruta_modelo: str) -> ModeloFalso:
    raise RuntimeError("pesos corruptos")


@pytest.fixture
def camaras_detectadas() -> Camaras:
    return []


@pytest.fixture
def escaneo(monkeypatch: pytest.MonkeyPatch, camaras_detectadas: Camaras) -> EscaneoEnHiloFalso:
    escaneo_falso = EscaneoEnHiloFalso(camaras_detectadas)
    monkeypatch.setattr("src.acquisition.camera_enumerator.enumerate_cameras_async", escaneo_falso)
    return escaneo_falso


@pytest.fixture
def trabajadores(monkeypatch: pytest.MonkeyPatch) -> FabricaDeTrabajadoresFalsa:
    fabrica = FabricaDeTrabajadoresFalsa()
    monkeypatch.setattr("src.tracking.camera_worker.CameraWorker", fabrica)
    return fabrica


@pytest.fixture
def motor() -> Callable[[str], ModeloFalso]:
    return modelo_yolo_falso


@pytest.fixture
def licencia() -> object | None:
    """Sin licencia por omisión; una prueba la reemplaza parametrizando `licencia`."""
    return None


@pytest.fixture
def entorno(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, motor: Callable[[str], ModeloFalso]
) -> None:
    """Tenant en tmp_path, motor falso y diálogos de error mudos."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Prueba_Escaneo")
    monkeypatch.setattr("ultralytics.YOLO", motor)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_argumentos: None)


@pytest.fixture
def app(
    entorno: None,
    escaneo: EscaneoEnHiloFalso,
    trabajadores: FabricaDeTrabajadoresFalsa,
    licencia: object | None,
) -> Iterator[AppMain]:
    aplicacion = AppMain(licencia=licencia)
    yield aplicacion
    escaneo.terminar()
    # Una prueba puede haber cerrado la ventana con on_closing: entonces ya no hay qué destruir.
    with contextlib.suppress(tkinter.TclError):
        aplicacion.destroy()


def correr_bucle_de_tk_hasta(app: AppMain, condicion: Callable[[], bool]) -> None:
    """Procesa los eventos de Tk (temporizadores incluidos) hasta que `condicion()` se cumpla."""

    def revisar() -> None:
        if condicion():
            app.quit()
            return
        app.after(INTERVALO_REVISION_MS, revisar)

    plazo = app.after(PLAZO_BUCLE_TK_MS, app.quit)
    app.after(0, revisar)
    app.mainloop()
    app.after_cancel(plazo)


def texto_de_estado(app: AppMain) -> str:
    return str(app._cam_status_label.cget("text"))


@pytest.mark.integration
def test_escaneo_sin_camaras_se_refleja_en_el_selector_desde_el_hilo_de_tk(
    app: AppMain, escaneo: EscaneoEnHiloFalso
) -> None:
    # Arrange
    escaneo.terminar()

    # Act
    correr_bucle_de_tk_hasta(app, lambda: app._cam_combo.get() == "Sin cámaras detectadas")

    # Assert
    assert app._cam_combo.get() == "Sin cámaras detectadas"
    assert texto_de_estado(app) == "❌ No se detectaron cámaras"


@pytest.mark.integration
@pytest.mark.parametrize("camaras_detectadas", [[CAMARA_3]], ids=["una_camara"])
def test_escaneo_con_una_camara_la_conecta_automaticamente(
    app: AppMain, escaneo: EscaneoEnHiloFalso, trabajadores: FabricaDeTrabajadoresFalsa
) -> None:
    # Arrange
    escaneo.terminar()

    # Act
    correr_bucle_de_tk_hasta(app, lambda: texto_de_estado(app).startswith("✅"))

    # Assert
    assert texto_de_estado(app) == "✅ Activa: índice 3"
    assert trabajadores.camaras_iniciadas() == [3]
    assert [trabajador.fps_limit for trabajador in trabajadores.creados] == [FPS_DE_LA_GUI]


@pytest.mark.integration
def test_la_app_no_agrega_un_filtro_de_confianza_al_del_motor(app: AppMain) -> None:
    detecciones = app.detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8))

    assert [deteccion.confianza for deteccion in detecciones] == [pytest.approx(CONFIANZA_BAJA)]


@pytest.mark.integration
@pytest.mark.parametrize("motor", [modelo_que_no_carga], ids=["motor_que_no_carga"])
def test_sin_motor_no_inicia_ninguna_camara(
    app: AppMain, trabajadores: FabricaDeTrabajadoresFalsa
) -> None:
    app._start_local_camera(3)

    assert app.detector is None
    assert trabajadores.creados == []


@pytest.mark.integration
def test_escaneo_inicial_revisa_los_primeros_diez_indices_de_camara(
    app: AppMain, escaneo: EscaneoEnHiloFalso
) -> None:
    assert escaneo.max_index == INDICES_DE_CAMARA_A_REVISAR


@pytest.mark.integration
def test_sin_licencia_la_camara_no_recibe_modulo_de_epp(
    app: AppMain, trabajadores: FabricaDeTrabajadoresFalsa
) -> None:
    app._start_local_camera(3)

    assert [trabajador.modulos_epp for trabajador in trabajadores.creados] == [[]]


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["con_epp"])
def test_con_licencia_cada_camara_recibe_su_modulo_de_epp(
    app: AppMain, trabajadores: FabricaDeTrabajadoresFalsa, monkeypatch: pytest.MonkeyPatch
) -> None:
    pedidos: list[tuple[object, object]] = []

    def fabrica(publicador: object, licencia: object) -> object:
        pedidos.append((publicador, licencia))
        return f"modulo-{len(pedidos)}"

    monkeypatch.setattr("src.composicion_epp.crear_integracion_epp_de_la_app", fabrica)

    app._start_local_camera(3)
    app._start_local_camera(4)

    assert [trabajador.modulos_epp for trabajador in trabajadores.creados] == [
        ["modulo-1"],
        ["modulo-2"],
    ]
    assert isinstance(app.publicador_epp, PublicadorEnMemoria)
    assert pedidos == [(app.publicador_epp, app.licencia)] * 2


@pytest.fixture
def despachador(monkeypatch: pytest.MonkeyPatch) -> tuple[DespachadorFalso, list[object]]:
    """Reemplaza a preparar_avisos: anota con qué entorno y conexión se lo pidió."""
    falso, pedidos = DespachadorFalso(), []

    def preparar(entorno: object, conectar: object, carpeta: Path, reloj: object) -> object:
        pedidos.append((entorno, carpeta))
        return falso

    monkeypatch.setattr("src.composicion_avisos.preparar_avisos", preparar)
    return falso, pedidos


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["con_epp"])
def test_con_licencia_de_epp_los_avisos_arrancan_al_abrir_y_paran_al_cerrar(
    despachador: tuple[DespachadorFalso, list[object]], app: AppMain, tmp_path: Path
) -> None:
    falso, pedidos = despachador

    app.on_closing()

    assert falso.eventos == ["iniciar", "detener 10 s"]
    assert [carpeta for _entorno, carpeta in pedidos] == [
        tmp_path / "OficinaEficiencia" / "Tenants" / "Prueba_Escaneo" / "snapshots"
    ]


@pytest.mark.integration
def test_sin_licencia_no_se_preparan_avisos(
    despachador: tuple[DespachadorFalso, list[object]], app: AppMain
) -> None:
    falso, pedidos = despachador

    app.on_closing()

    assert (falso.eventos, pedidos) == ([], [])


def _botones_del_menu(app: AppMain) -> list[str]:
    return [
        str(hijo.cget("text"))
        for hijo in app.sidebar_frame.winfo_children()
        if isinstance(hijo, ctk.CTkButton)
    ]


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["con_epp"])
def test_con_licencia_de_epp_el_menu_suma_alertas_y_cumplimiento_sin_eficiencia(
    app: AppMain,
) -> None:
    assert _botones_del_menu(app) == [
        "Monitoreo en Vivo",
        "Gestión de Empleados",
        "Configuración de Zonas",
        "Alertas EPP",
        "Cumplimiento EPP",
        "Cambiar Sucursal",
    ]
    assert "Reportes" not in app.view_manager.views


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEficiencia()], ids=["con_eficiencia"])
def test_con_el_modulo_de_eficiencia_el_menu_ofrece_los_reportes_historicos(
    app: AppMain,
) -> None:
    assert _botones_del_menu(app) == [
        "Monitoreo en Vivo",
        "Gestión de Empleados",
        "Configuración de Zonas",
        "Reportes Históricos",
        "Cambiar Sucursal",
    ]
    assert app.view_manager.views["Reportes"] is app.view_reportes
    assert isinstance(app.view_reportes, ctk.CTkFrame)


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["con_epp"])
@pytest.mark.parametrize(
    ("boton", "vista"),
    [("Alertas EPP", "AlertasEPP"), ("Cumplimiento EPP", "CumplimientoEPP")],
    ids=["alertas", "cumplimiento"],
)
def test_cada_boton_del_modulo_abre_su_vista(app: AppMain, boton: str, vista: str) -> None:
    (elegido,) = (
        hijo
        for hijo in app.sidebar_frame.winfo_children()
        if isinstance(hijo, ctk.CTkButton) and hijo.cget("text") == boton
    )

    elegido.invoke()

    assert app.view_manager.current_view is app.view_manager.views[vista]


@pytest.mark.integration
def test_sin_licencia_de_epp_el_menu_no_muestra_el_modulo(app: AppMain) -> None:
    assert {"Alertas EPP", "Cumplimiento EPP"}.isdisjoint(_botones_del_menu(app))
    assert {"AlertasEPP", "CumplimientoEPP"}.isdisjoint(app.view_manager.views)


# --- Licencia con la app abierta (SPEC/10 T-05) -----------------------------------------------


def _avisos_de_la_barra(app: AppMain) -> list[str]:
    return [
        str(hijo.cget("text"))
        for hijo in app.sidebar_frame.winfo_children()
        if isinstance(hijo, ctk.CTkLabel) and str(hijo.cget("text")).startswith("Prueba")
    ]


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["prueba"])
def test_con_licencia_de_prueba_la_barra_avisa_los_dias_restantes_bajo_el_titulo(
    despachador: tuple[DespachadorFalso, list[object]], app: AppMain
) -> None:
    hijos = app.sidebar_frame.pack_slaves()

    assert _avisos_de_la_barra(app) == ["Prueba: quedan 9 días"]
    assert [str(hijo.cget("text")) for hijo in hijos[:2]] == ["VMS Panel", "Prueba: quedan 9 días"]


@pytest.mark.integration
def test_sin_licencia_la_barra_no_muestra_aviso_de_prueba(app: AppMain) -> None:
    assert _avisos_de_la_barra(app) == []


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["prueba"])
@pytest.mark.parametrize("camaras_detectadas", [[CAMARA_3]], ids=["una_camara"])
def test_suspender_por_licencia_detiene_camaras_y_avisos_y_reanudar_los_devuelve(
    despachador: tuple[DespachadorFalso, list[object]],
    app: AppMain,
    escaneo: EscaneoEnHiloFalso,
    trabajadores: FabricaDeTrabajadoresFalsa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    falso, _pedidos = despachador
    monkeypatch.setattr("src.composicion_epp.crear_integracion_epp_de_la_app", lambda *_: None)
    escaneo.terminar()
    correr_bucle_de_tk_hasta(app, lambda: trabajadores.camaras_iniciadas() == [3])

    app.suspender_por_licencia()
    suspendida = (trabajadores.camaras_iniciadas(), list(falso.eventos))
    app.reanudar_con_licencia()

    assert suspendida == ([], ["iniciar", "detener 10 s"])
    assert trabajadores.camaras_iniciadas() == [3]
    assert falso.eventos == ["iniciar", "detener 10 s", "iniciar"]


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["prueba"])
def test_cerrar_tras_suspender_no_detiene_los_avisos_dos_veces_ni_arranca_camaras(
    despachador: tuple[DespachadorFalso, list[object]],
    app: AppMain,
    trabajadores: FabricaDeTrabajadoresFalsa,
) -> None:
    falso, _pedidos = despachador

    app.suspender_por_licencia()
    app.on_closing()

    assert falso.eventos == ["iniciar", "detener 10 s"]
    assert trabajadores.camaras_iniciadas() == []


@pytest.mark.integration
@pytest.mark.parametrize("licencia", [LicenciaConEPP()], ids=["prueba"])
def test_reanudar_sin_camara_elegida_solo_devuelve_los_avisos(
    despachador: tuple[DespachadorFalso, list[object]],
    app: AppMain,
    trabajadores: FabricaDeTrabajadoresFalsa,
) -> None:
    falso, _pedidos = despachador
    app.suspender_por_licencia()

    app.reanudar_con_licencia()

    assert trabajadores.creados == []
    assert falso.eventos == ["iniciar", "detener 10 s", "iniciar"]
