"""Presentador del dibujo de zonas dentro de la aplicación (SPEC/9 §8.3): toda la lógica, sin Tk.

El usuario toma una foto de la cámara activa, marca las esquinas con clics sobre la foto
reducida a la vista y guarda la zona con un nombre. Los puntos se guardan en píxeles de la
cámara, que es lo que usa ZoneChecker.
"""

from pathlib import Path

import numpy as np
import pytest

from src.gui.presentador_dibujo_zonas import PresentadorDibujoZonas
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.reglas import ReglaZona
from src.zones.formato_zonas import escribir_zonas, leer_zonas

CASCO = frozenset({ElementoEPP.CASCO})
CUADRADO = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
VISTA_MAXIMA = (800, 450)
SIN_IMAGEN = "Todavía no hay imagen de la cámara: conéctela y espere a ver el video"


def _cuadro(ancho: int, alto: int) -> np.ndarray:
    return np.zeros((alto, ancho, 3), dtype=np.uint8)


class Avisos:
    """Cuenta las veces que el presentador avisa que cambiaron las zonas."""

    def __init__(self) -> None:
        self.cantidad = 0

    def __call__(self) -> None:
        self.cantidad += 1


@pytest.fixture
def ruta(tmp_path: Path) -> Path:
    return tmp_path / "zonas" / "zonas_config.json"


@pytest.fixture
def avisos() -> Avisos:
    return Avisos()


def _presentador(
    ruta: Path, avisos: Avisos, cuadro: np.ndarray | None = None
) -> PresentadorDibujoZonas:
    def tomar() -> np.ndarray | None:
        return cuadro

    presentador = PresentadorDibujoZonas(ruta, tomar, VISTA_MAXIMA, avisos)
    presentador.cargar()
    return presentador


def _con_foto(
    ruta: Path, avisos: Avisos, ancho: int = 1600, alto: int = 900
) -> PresentadorDibujoZonas:
    presentador = _presentador(ruta, avisos, _cuadro(ancho, alto))
    presentador.tomar_foto()
    return presentador


def _marcar(presentador: PresentadorDibujoZonas, *puntos: tuple[float, float]) -> None:
    for x, y in puntos:
        presentador.agregar_punto(x, y)


# --- Foto de la cámara ---------------------------------------------------------------------------


def test_sin_imagen_de_la_camara_avisa_como_conseguirla(ruta: Path, avisos: Avisos) -> None:
    presentador = _presentador(ruta, avisos, None)

    presentador.tomar_foto()

    assert presentador.foto is None
    assert presentador.mensaje == SIN_IMAGEN


@pytest.mark.parametrize(
    ("camara", "vista", "escala"),
    [
        ((1600, 900), (800, 450), 0.5),
        ((640, 480), (600, 450), 0.9375),
        ((400, 200), (400, 200), 1.0),
        ((2000, 500), (800, 200), 0.4),
    ],
    ids=[
        "full_hd_se_reduce_a_la_mitad",
        "vga_limitada_por_el_alto",
        "chica_no_se_agranda",
        "panoramica_limitada_por_el_ancho",
    ],
)
def test_la_foto_se_reduce_para_entrar_en_la_vista_sin_deformarse(
    ruta: Path, avisos: Avisos, camara: tuple[int, int], vista: tuple[int, int], escala: float
) -> None:
    presentador = _con_foto(ruta, avisos, *camara)

    assert presentador.tamano_vista == vista
    assert presentador.escala == escala
    assert presentador.mensaje == "Haga clic en cada esquina de la zona"


def test_tomar_otra_foto_descarta_los_puntos_marcados(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (10, 10), (20, 10))

    presentador.tomar_foto()

    assert presentador.puntos == []


def test_sin_foto_el_tamano_de_la_vista_es_el_maximo(ruta: Path, avisos: Avisos) -> None:
    presentador = _presentador(ruta, avisos, None)

    assert presentador.tamano_vista == VISTA_MAXIMA


# --- Esquinas ------------------------------------------------------------------------------------


def test_cada_clic_se_guarda_en_pixeles_de_la_camara(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)

    _marcar(presentador, (10, 20), (400.4, 0), (799.9, 449.9))

    assert presentador.puntos == [(20, 40), (801, 0), (1599, 899)]
    assert presentador.puntos_en_vista == [(10.0, 20.0), (400.5, 0.0), (799.5, 449.5)]


def test_un_clic_fuera_de_la_foto_se_ajusta_al_borde(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)

    _marcar(presentador, (-5, 900), (2000, -1))

    assert presentador.puntos == [(0, 899), (1599, 0)]


def test_sin_foto_los_clics_se_ignoran_y_se_explica_por_que(ruta: Path, avisos: Avisos) -> None:
    presentador = _presentador(ruta, avisos, None)

    presentador.agregar_punto(10, 10)

    assert presentador.puntos == []
    assert presentador.mensaje == "Primero tome una foto de la cámara"


def test_deshacer_quita_la_ultima_esquina(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (10, 10), (20, 10))

    presentador.deshacer()

    assert presentador.puntos == [(20, 20)]


def test_deshacer_sin_esquinas_no_hace_nada(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)

    presentador.deshacer()

    assert presentador.puntos == []


def test_limpiar_quita_todas_las_esquinas(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (10, 10), (20, 10), (20, 20))

    presentador.limpiar()

    assert presentador.puntos == []


# --- Guardar -------------------------------------------------------------------------------------


def test_guardar_escribe_la_zona_en_pixeles_de_la_camara_y_avisa(
    ruta: Path, avisos: Avisos
) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (0, 0), (100, 0), (100, 50))

    presentador.guardar("Taller")

    assert leer_zonas(ruta) == (
        ReglaZona("Taller", ((0.0, 0.0), (200.0, 0.0), (200.0, 100.0)), frozenset()),
    )
    assert presentador.zonas == ["Taller"]
    assert presentador.puntos == []
    assert avisos.cantidad == 1
    assert presentador.mensaje == (
        "Zona 'Taller' guardada. Marque su EPP abajo; rige al reconectar la cámara."
    )


def test_redibujar_una_zona_conserva_su_epp(ruta: Path, avisos: Avisos) -> None:
    escribir_zonas(ruta, [ReglaZona("Taller", CUADRADO, CASCO)])
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (0, 0), (100, 0), (100, 50))

    presentador.guardar("Taller")

    assert leer_zonas(ruta)[0].exigidos == CASCO


def test_guardar_quita_los_espacios_del_nombre(ruta: Path, avisos: Avisos) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (0, 0), (100, 0), (100, 50))

    presentador.guardar("  Taller  ")

    assert presentador.zonas == ["Taller"]


@pytest.mark.parametrize(
    ("esquinas", "mensaje"),
    [
        ((), "Marque al menos 3 esquinas antes de guardar"),
        (((0, 0), (10, 0)), "Marque al menos 3 esquinas antes de guardar"),
        (
            ((0, 0), (10, 10), (10, 0), (0, 10)),
            "Las esquinas de la zona 'Taller' se cruzan o están alineadas: márquelas en orden "
            "alrededor de la zona",
        ),
    ],
    ids=["sin_esquinas", "dos_esquinas", "cruzadas"],
)
def test_guardar_una_zona_incompleta_explica_que_falta_sin_tocar_el_archivo(
    ruta: Path, avisos: Avisos, esquinas: tuple[tuple[int, int], ...], mensaje: str
) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, *esquinas)

    presentador.guardar("Taller")

    assert presentador.mensaje == mensaje
    assert not ruta.exists()
    assert avisos.cantidad == 0


@pytest.mark.parametrize("nombre", ["", "   ", "../afuera", 'Zona "A"'])
def test_guardar_con_un_nombre_invalido_lo_explica(ruta: Path, avisos: Avisos, nombre: str) -> None:
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (0, 0), (100, 0), (100, 50))

    presentador.guardar(nombre)

    assert presentador.mensaje is not None
    assert presentador.mensaje.startswith("El nombre de zona solo admite letras")
    assert presentador.puntos == [(0, 0), (200, 0), (200, 100)]
    assert not ruta.exists()


def test_guardar_sobre_un_archivo_corrupto_lo_explica_sin_pisarlo(
    ruta: Path, avisos: Avisos
) -> None:
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{corrupto", encoding="utf-8")
    presentador = _con_foto(ruta, avisos)
    _marcar(presentador, (0, 0), (100, 0), (100, 50))

    presentador.guardar("Taller")

    assert presentador.mensaje is not None
    assert presentador.mensaje.startswith("No se pudo guardar la zona: ")
    assert ruta.read_text(encoding="utf-8") == "{corrupto"


# --- Zonas existentes ----------------------------------------------------------------------------


def test_al_cargar_lista_las_zonas_y_sus_poligonos_en_la_vista(ruta: Path, avisos: Avisos) -> None:
    escribir_zonas(ruta, [ReglaZona("Boca de pozo", CUADRADO, CASCO)])

    presentador = _con_foto(ruta, avisos)

    assert presentador.zonas == ["Boca de pozo"]
    assert presentador.poligonos_en_vista == {
        "Boca de pozo": [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
    }


def test_al_cargar_un_archivo_corrupto_lo_explica(ruta: Path, avisos: Avisos) -> None:
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{corrupto", encoding="utf-8")

    presentador = _presentador(ruta, avisos)

    assert presentador.zonas == []
    assert presentador.mensaje is not None
    assert presentador.mensaje.startswith("No se pudo leer el archivo de zonas: ")


def test_borrar_una_zona_la_quita_y_avisa(ruta: Path, avisos: Avisos) -> None:
    escribir_zonas(
        ruta, [ReglaZona("Boca de pozo", CUADRADO, CASCO), ReglaZona("Taller", CUADRADO, CASCO)]
    )
    presentador = _presentador(ruta, avisos)

    presentador.borrar("Taller")

    assert [zona.nombre for zona in leer_zonas(ruta)] == ["Boca de pozo"]
    assert presentador.zonas == ["Boca de pozo"]
    assert presentador.mensaje == "Zona 'Taller' borrada"
    assert avisos.cantidad == 1


def test_borrar_una_zona_que_ya_no_existe_lo_explica(ruta: Path, avisos: Avisos) -> None:
    escribir_zonas(ruta, [ReglaZona("Boca de pozo", CUADRADO, CASCO)])
    presentador = _presentador(ruta, avisos)

    presentador.borrar("Taller")

    assert presentador.mensaje == "No se pudo borrar la zona: No existe la zona 'Taller'"
    assert avisos.cantidad == 0


def test_la_vista_maxima_debe_tener_tamano(ruta: Path, avisos: Avisos) -> None:
    with pytest.raises(
        ValueError, match=r"^La vista debe medir al menos 1 x 1 píxeles: \(0, 450\)$"
    ):
        PresentadorDibujoZonas(ruta, lambda: None, (0, 450), avisos)


def test_una_vista_de_un_pixel_es_valida(ruta: Path, avisos: Avisos) -> None:
    presentador = PresentadorDibujoZonas(ruta, lambda: None, (1, 1), avisos)

    assert presentador.tamano_vista == (1, 1)


def test_antes_de_cargar_no_hay_zonas_ni_mensaje(ruta: Path, avisos: Avisos) -> None:
    presentador = PresentadorDibujoZonas(ruta, lambda: None, VISTA_MAXIMA, avisos)

    assert presentador.zonas == []
    assert presentador.mensaje is None


def test_sin_foto_las_zonas_se_dibujan_en_tamano_real(ruta: Path, avisos: Avisos) -> None:
    escribir_zonas(ruta, [ReglaZona("Boca de pozo", CUADRADO, CASCO)])

    presentador = _presentador(ruta, avisos)

    assert presentador.escala == 1.0
    assert presentador.poligonos_en_vista == {"Boca de pozo": list(CUADRADO)}
