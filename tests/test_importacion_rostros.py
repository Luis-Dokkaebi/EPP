"""Carga masiva de rostros con constancia de consentimiento (SPEC/10 §14.5, T-15)."""

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.recognition.importacion_rostros import (
    BitacoraDeImportaciones,
    ImportacionInvalidaError,
    Motivo,
    importar_rostros,
    leer_consentimientos,
    resumen,
)

AHORA = datetime(2026, 11, 13, 9, 30, tzinfo=UTC)
ENCABEZADO = "nombre,id_consentimiento\n"


class RegistroFalso:
    """Empleados de la sucursal: anota qué fotos recibió; `sin_rostro` no se pueden registrar."""

    def __init__(self, ya: tuple[str, ...] = (), sin_rostro: tuple[str, ...] = ()) -> None:
        self._ya = ya
        self._sin_rostro = sin_rostro
        self.registrados: dict[str, list[str]] = {}

    def ya_registrado(self, nombre: str) -> bool:
        return nombre in self._ya

    def registrar(self, nombre: str, fotos: list[Path]) -> int:
        if nombre in self._sin_rostro:
            return 0
        self.registrados[nombre] = [foto.name for foto in fotos]
        return len(fotos)


def _carpeta(raiz: Path, consentimientos: str, **personas: tuple[str, ...]) -> Path:
    carpeta = raiz / "rostros_acme"
    carpeta.mkdir()
    (carpeta / "consentimientos.csv").write_text(consentimientos, encoding="utf-8")
    for nombre, archivos in personas.items():
        (carpeta / nombre.replace("_", " ")).mkdir()
        for archivo in archivos:
            (carpeta / nombre.replace("_", " ") / archivo).write_bytes(b"foto")
    return carpeta


@pytest.fixture
def bitacora(tmp_path: Path) -> BitacoraDeImportaciones:
    return BitacoraDeImportaciones(tmp_path / "datos" / "importaciones.csv", "luis", lambda: AHORA)


def _filas(bitacora: BitacoraDeImportaciones) -> list[dict[str, str]]:
    with bitacora.ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def test_solo_se_cargan_las_personas_con_consentimiento_y_fotos(
    tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    carpeta = _carpeta(
        tmp_path,
        ENCABEZADO + "Ana Lopez,C-001\nJuan Perez,C-002\nSin Carpeta,C-003\nEva Ruiz,\n",
        Ana_Lopez=("b.jpg", "a.JPG", "notas.txt"),
        Juan_Perez=("1.png", "2.jpeg"),
        Pedro_Gil=("1.jpg",),
        Eva_Ruiz=("1.jpg",),
    )
    registro = RegistroFalso()

    resultado = importar_rostros(carpeta, registro, bitacora)

    assert resultado.cargados == {"Ana Lopez": 2, "Juan Perez": 2}
    assert resultado.omitidos == {
        "Eva Ruiz": Motivo.SIN_CONSENTIMIENTO,
        "Pedro Gil": Motivo.SIN_CONSENTIMIENTO,
        "Sin Carpeta": Motivo.SIN_FOTOS,
    }
    assert registro.registrados == {
        "Ana Lopez": ["a.JPG", "b.jpg"],
        "Juan Perez": ["1.png", "2.jpeg"],
    }


def test_cada_carga_queda_en_la_bitacora_con_quien_y_cuando(
    tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    carpeta = _carpeta(tmp_path, ENCABEZADO + "Ana Lopez,C-001\n", Ana_Lopez=("a.jpg", "b.jpg"))

    importar_rostros(carpeta, RegistroFalso(), bitacora)
    importar_rostros(carpeta, RegistroFalso(), bitacora)

    fila = {
        "fecha": "2026-11-13T09:30:00+00:00",
        "operador": "luis",
        "nombre": "Ana Lopez",
        "id_consentimiento": "C-001",
        "fotos": "2",
    }
    assert _filas(bitacora) == [fila, fila]


def test_quien_no_se_carga_no_queda_en_la_bitacora(
    tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    carpeta = _carpeta(
        tmp_path,
        ENCABEZADO + "Ana Lopez,C-001\nJuan Perez,C-002\nLuz Mora,C-004\n",
        Ana_Lopez=("a.jpg",),
        Juan_Perez=("a.jpg",),
        Luz_Mora=("solo.txt",),
        Pedro_Gil=("a.jpg",),
    )
    registro = RegistroFalso(ya=("Ana Lopez",), sin_rostro=("Juan Perez",))

    resultado = importar_rostros(carpeta, registro, bitacora)

    assert resultado.cargados == {}
    assert resultado.omitidos == {
        "Ana Lopez": Motivo.YA_REGISTRADO,
        "Juan Perez": Motivo.SIN_ROSTRO,
        "Luz Mora": Motivo.SIN_FOTOS,
        "Pedro Gil": Motivo.SIN_CONSENTIMIENTO,
    }
    assert not bitacora.ruta.exists()
    assert registro.registrados == {}


def test_los_consentimientos_se_leen_sin_espacios_sobrantes(tmp_path: Path) -> None:
    carpeta = _carpeta(tmp_path, ENCABEZADO + " Ana Lopez , C-001 \nEva Ruiz,  \n\n")

    assert leer_consentimientos(carpeta) == {"Ana Lopez": "C-001"}


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        (None, "Falta consentimientos.csv en la carpeta: sin constancia no se carga a nadie."),
        (
            "empleado,folio\nAna,C-1\n",
            "consentimientos.csv debe tener las columnas nombre e id_consentimiento.",
        ),
        ("", "consentimientos.csv debe tener las columnas nombre e id_consentimiento."),
    ],
    ids=["sin_archivo", "otras_columnas", "vacio"],
)
def test_sin_constancia_valida_no_se_carga_a_nadie(
    contenido: str | None, mensaje: str, tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    carpeta = _carpeta(tmp_path, contenido or "", Ana_Lopez=("a.jpg",))
    if contenido is None:
        (carpeta / "consentimientos.csv").unlink()
    registro = RegistroFalso()

    with pytest.raises(ImportacionInvalidaError) as error:
        importar_rostros(carpeta, registro, bitacora)

    assert str(error.value) == mensaje
    assert registro.registrados == {}


def test_el_resumen_dice_a_quien_se_cargo_y_por_que_se_omitio_al_resto(
    tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    carpeta = _carpeta(
        tmp_path,
        ENCABEZADO + "Ana Lopez,C-001\nJuan Perez,C-002\n",
        Ana_Lopez=("a.jpg",),
        Juan_Perez=("a.jpg",),
        Pedro_Gil=("a.jpg",),
    )
    resultado = importar_rostros(carpeta, RegistroFalso(sin_rostro=("Juan Perez",)), bitacora)

    assert resumen(resultado) == (
        "Cargados: 1 (Ana Lopez). Omitidos: Juan Perez (sin rostro detectable en sus fotos), "
        "Pedro Gil (sin consentimiento registrado)."
    )


def test_el_resumen_de_una_carpeta_sin_nadie_que_cargar(
    tmp_path: Path, bitacora: BitacoraDeImportaciones
) -> None:
    resultado = importar_rostros(_carpeta(tmp_path, ENCABEZADO), RegistroFalso(), bitacora)

    assert resumen(resultado) == "Cargados: 0. Omitidos: ninguno."


def test_cada_motivo_se_explica_al_operador() -> None:
    assert {motivo.name: motivo.value for motivo in Motivo} == {
        "SIN_CONSENTIMIENTO": "sin consentimiento registrado",
        "SIN_FOTOS": "sin fotos en su carpeta",
        "YA_REGISTRADO": "ya estaba registrado",
        "SIN_ROSTRO": "sin rostro detectable en sus fotos",
    }
