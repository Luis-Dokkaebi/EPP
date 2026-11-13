"""El producto no usa el modelo de 68 puntos faciales (SPEC/10 F-12, T-14).

`face_recognition.face_landmarks` carga el predictor de 68 puntos de dlib, entrenado con el
dataset iBUG 300-W, que no permite uso comercial (docs/legal/revision_d9.md §3). El
reconocimiento de rostros usa solo el modelo de 5 puntos y el de huellas.
"""

import ast

from tests.utilidades_scripts import RAIZ

LLAMADAS_PROHIBIDAS = frozenset({"face_landmarks", "raw_face_landmarks"})


def _llamadas_prohibidas(codigo: str) -> set[str]:
    nombres = {
        nodo.attr for nodo in ast.walk(ast.parse(codigo)) if isinstance(nodo, ast.Attribute)
    } | {nodo.id for nodo in ast.walk(ast.parse(codigo)) if isinstance(nodo, ast.Name)}
    return nombres & LLAMADAS_PROHIBIDAS


def test_ningun_modulo_del_producto_pide_los_puntos_faciales() -> None:
    culpables = {
        str(archivo.relative_to(RAIZ)): sorted(_llamadas_prohibidas(archivo.read_text("utf-8")))
        for archivo in [*RAIZ.glob("src/**/*.py"), *RAIZ.glob("utils/**/*.py")]
        if _llamadas_prohibidas(archivo.read_text("utf-8"))
    }

    assert culpables == {}


def test_el_detector_de_llamadas_reconoce_el_uso_por_atributo_y_por_nombre() -> None:
    por_atributo = "import face_recognition\nface_recognition.face_landmarks(imagen)\n"
    por_nombre = "from face_recognition import face_landmarks\nface_landmarks(imagen)\n"

    assert _llamadas_prohibidas(por_atributo) == {"face_landmarks"}
    assert _llamadas_prohibidas(por_nombre) == {"face_landmarks"}
    assert _llamadas_prohibidas("face_recognition.face_encodings(imagen)\n") == set()
