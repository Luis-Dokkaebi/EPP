"""FaceRecognizer sobre MotorFacialPort: registro, reconocimiento y archivo de vectores."""

import hashlib
import hmac
import io
import logging
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.recognition import face_recognizer as modulo
from src.recognition.face_recognizer import NOMBRE_DESCONOCIDO, FaceRecognizer
from tests.dobles_motor_facial import MotorFacialFalso, escribir_imagen

ROJO = (0, 0, 200)
VERDE = (0, 200, 0)
NEGRO = (0, 0, 0)


@pytest.fixture
def motor() -> MotorFacialFalso:
    return MotorFacialFalso()


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    caras = tmp_path / "faces"
    caras.mkdir()
    return caras


def _reconocedor(carpeta: Path, motor: MotorFacialFalso) -> FaceRecognizer:
    return FaceRecognizer(faces_dir=str(carpeta), motor=motor)


def _cuadro(color: tuple[int, int, int]) -> np.ndarray:
    return np.full((20, 20, 3), color, dtype=np.uint8)


def test_sin_archivo_de_vectores_codifica_las_fotos_de_cada_persona(carpeta, motor) -> None:
    (carpeta / "Ana").mkdir()
    escribir_imagen(str(carpeta / "Ana" / "1.jpg"), ROJO)
    (carpeta / "Ana" / "notas.txt").write_text("no es imagen", encoding="utf-8")
    (carpeta / "suelto.jpg").write_bytes(b"fuera de una carpeta de persona")

    reconocedor = _reconocedor(carpeta, motor)

    assert reconocedor.known_face_names == ["Ana"]
    assert os.path.exists(reconocedor.encodings_file)


def test_una_foto_sin_cara_no_se_registra_al_codificar_la_carpeta(carpeta, motor) -> None:
    (carpeta / "Ana").mkdir()
    escribir_imagen(str(carpeta / "Ana" / "1.png"), NEGRO)

    assert _reconocedor(carpeta, motor).known_face_names == []


def test_una_foto_ilegible_se_omite_sin_romper_la_carga(carpeta, motor) -> None:
    (carpeta / "Ana").mkdir()
    (carpeta / "Ana" / "rota.jpg").write_bytes(b"no es un jpg")

    assert _reconocedor(carpeta, motor).known_face_names == []


def test_registrar_una_foto_copia_la_imagen_y_guarda_el_vector(tmp_path, carpeta, motor) -> None:
    foto = escribir_imagen(str(tmp_path / "ana.png"), ROJO)
    reconocedor = _reconocedor(carpeta, motor)

    registrada = reconocedor.register_face(foto, "Ana")

    assert registrada is True
    assert (carpeta / "Ana" / "ana.png").exists()
    assert _reconocedor(carpeta, MotorFacialFalso()).known_face_names == ["Ana"]


def test_registrar_admite_nombres_y_rutas_con_acentos(tmp_path, carpeta, motor) -> None:
    foto = escribir_imagen(str(tmp_path / "josé.png"), VERDE)

    assert _reconocedor(carpeta, motor).register_face(foto, "José Núñez") is True
    assert _reconocedor(carpeta, MotorFacialFalso()).known_face_names == ["José Núñez"]


def test_registrar_una_foto_sin_cara_no_registra_nada(tmp_path, carpeta, motor) -> None:
    foto = escribir_imagen(str(tmp_path / "vacia.png"), NEGRO)
    reconocedor = _reconocedor(carpeta, motor)

    assert reconocedor.register_face(foto, "Ana") is False
    assert reconocedor.known_face_names == []
    assert not (carpeta / "Ana").exists()


def test_registrar_una_ruta_inexistente_devuelve_falso(tmp_path, carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)

    assert reconocedor.register_face(str(tmp_path / "no-existe.png"), "Ana") is False


def test_reconocer_devuelve_el_nombre_mas_parecido_sobre_el_umbral(tmp_path, carpeta, motor):
    reconocedor = _reconocedor(carpeta, motor)
    reconocedor.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")
    reconocedor.register_face(escribir_imagen(str(tmp_path / "b.png"), VERDE), "Beto")

    assert reconocedor.recognize_face(_cuadro(VERDE)) == "Beto"


def test_reconocer_una_cara_parecida_pero_bajo_el_umbral_es_desconocida(tmp_path, carpeta, motor):
    reconocedor = _reconocedor(carpeta, motor)
    reconocedor.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")

    assert reconocedor.recognize_face(_cuadro((0, 0, 201))) == "Ana"
    assert reconocedor.recognize_face(_cuadro((0, 0, 202))) == NOMBRE_DESCONOCIDO


def test_reconocer_sin_caras_conocidas_es_desconocido(carpeta, motor) -> None:
    assert _reconocedor(carpeta, motor).recognize_face(_cuadro(ROJO)) == NOMBRE_DESCONOCIDO


def test_reconocer_un_cuadro_sin_cara_es_desconocido(tmp_path, carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    reconocedor.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")

    assert reconocedor.recognize_face(_cuadro(NEGRO)) == NOMBRE_DESCONOCIDO


def test_reconocer_con_caja_recorta_y_ajusta_la_caja_al_cuadro(carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    cuadro = _cuadro(ROJO)

    reconocedor.recognize_face(cuadro, bbox=(-5.0, 2.0, 50.0, 8.5))

    assert motor.imagenes_codificadas[-1].shape == (6, 20, 3)


def test_reconocer_con_caja_vacia_es_desconocido(carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)

    assert reconocedor.recognize_face(_cuadro(ROJO), bbox=(30, 30, 40, 40)) == NOMBRE_DESCONOCIDO


def test_registro_en_rafaga_cuenta_solo_las_fotos_con_cara(tmp_path, carpeta, motor) -> None:
    fotos = [
        escribir_imagen(str(tmp_path / "1.png"), ROJO),
        escribir_imagen(str(tmp_path / "2.png"), NEGRO),
        str(tmp_path / "no-existe.png"),
        escribir_imagen(str(tmp_path / "3.png"), (0, 0, 199)),
    ]
    reconocedor = _reconocedor(carpeta, motor)

    registradas = reconocedor.register_face_burst(fotos, "Ana")

    assert registradas == len(reconocedor.known_face_names)
    assert reconocedor.known_face_names == ["Ana", "Ana"]
    assert sorted(p.name for p in (carpeta / "Ana").iterdir()) == ["burst_0.jpg", "burst_3.jpg"]


def test_registro_en_rafaga_sin_caras_no_guarda_el_archivo(tmp_path, carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    os.remove(reconocedor.encodings_file)

    registradas = reconocedor.register_face_burst([str(tmp_path / "x.png")], "Ana")

    assert registradas == 0
    assert not os.path.exists(reconocedor.encodings_file)


def test_eliminar_borra_los_vectores_y_la_carpeta_de_la_persona(tmp_path, carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    reconocedor.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")
    reconocedor.register_face(escribir_imagen(str(tmp_path / "b.png"), VERDE), "Beto")

    eliminada = reconocedor.delete_face("Ana")

    assert eliminada is True
    assert reconocedor.known_face_names == ["Beto"]
    assert len(reconocedor.known_face_encodings) == 1
    assert not (carpeta / "Ana").exists()
    assert _reconocedor(carpeta, MotorFacialFalso()).known_face_names == ["Beto"]


def test_eliminar_a_alguien_desconocido_devuelve_falso(carpeta, motor) -> None:
    assert _reconocedor(carpeta, motor).delete_face("Nadie") is False


def test_vectores_de_otro_motor_se_descartan_y_se_recodifican(carpeta, motor) -> None:
    (carpeta / "Ana").mkdir()
    escribir_imagen(str(carpeta / "Ana" / "1.png"), ROJO)
    viejo = _reconocedor(carpeta, motor)
    viejo.known_face_names = ["Fantasma"]
    viejo.save_encodings()
    otro_motor = MotorFacialFalso()
    otro_motor.identificador = "motor-falso-v2"

    nuevo = _reconocedor(carpeta, otro_motor)

    assert nuevo.known_face_names == ["Ana"]


def test_el_formato_pickle_heredado_no_se_carga(carpeta, motor) -> None:
    """Los .pkl de dlib no son comparables con SFace y pickle no es seguro: se ignoran."""
    (carpeta / "encodings.pkl").write_bytes(b"\x80\x04cualquier cosa")

    assert _reconocedor(carpeta, motor).known_face_names == []


def test_recarga_en_caliente_si_otro_proceso_actualizo_el_archivo(tmp_path, carpeta, motor):
    camara = _reconocedor(carpeta, motor)
    registro = _reconocedor(carpeta, MotorFacialFalso())
    registro.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")
    marca = os.path.getmtime(registro.encodings_file) + 10
    os.utime(registro.encodings_file, (marca, marca))

    camara.check_reload()

    assert camara.known_face_names == ["Ana"]


def test_recarga_en_caliente_sin_cambios_no_vuelve_a_leer(carpeta, motor, monkeypatch) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    monkeypatch.setattr(reconocedor, "load_known_faces", lambda: pytest.fail("no debía recargar"))

    reconocedor.check_reload()


def test_recarga_en_caliente_sin_archivo_no_hace_nada(carpeta, motor, monkeypatch) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    os.remove(reconocedor.encodings_file)
    monkeypatch.setattr(reconocedor, "load_known_faces", lambda: pytest.fail("no debía recargar"))

    reconocedor.check_reload()


def test_sin_motor_inyectado_usa_el_de_la_raiz_de_composicion(carpeta, motor, monkeypatch):
    monkeypatch.setattr("src.composition.crear_motor_facial_configurado", lambda: motor)

    assert FaceRecognizer(faces_dir=str(carpeta)).motor is motor


def test_sin_carpeta_usa_la_de_datos_del_usuario(tmp_path, motor, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    reconocedor = FaceRecognizer(motor=motor)

    assert reconocedor.faces_dir == str(tmp_path / "OficinaEficiencia" / "data" / "faces")
    assert reconocedor.encodings_file == os.path.join(reconocedor.faces_dir, "encodings.npz")


def test_la_firma_usa_el_identificador_de_la_maquina_del_drm(monkeypatch) -> None:
    monkeypatch.setattr(modulo, "_identificador_de_maquina", lambda: "PC-1")
    firma_1 = modulo.firmar(b"datos")
    monkeypatch.setattr(modulo, "_identificador_de_maquina", lambda: "PC-2")

    assert modulo.firmar(b"datos") != firma_1
    assert modulo.firma_valida(b"datos", firma_1) is False


def test_sin_machine_id_del_drm_la_firma_usa_el_respaldo_de_la_placa(monkeypatch) -> None:
    def drm_roto() -> None:
        raise OSError("WMI no disponible")

    monkeypatch.setattr("src.security.drm.DRMValidator", drm_roto)

    assert modulo._identificador_de_maquina().startswith("FALLBACK_")


@pytest.mark.parametrize(
    "preparar",
    [lambda ruta: ruta.mkdir(), lambda ruta: ruta.write_bytes(b"")],
    ids=["es_carpeta", "archivo_vacio"],
)
def test_leer_imagen_que_no_se_puede_decodificar_devuelve_none(tmp_path, preparar) -> None:
    ruta = tmp_path / "foto.jpg"
    preparar(ruta)

    assert modulo.leer_imagen(str(ruta)) is None


def _archivo_firmado(carpeta: Path, contenido: bytes) -> None:
    (carpeta / "encodings.npz").write_bytes(modulo.firmar(contenido) + contenido)


def _npz(**arreglos: object) -> bytes:
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arreglos)
    return buffer.getvalue()


def test_un_archivo_que_solo_trae_la_firma_se_recalcula_sin_romper(carpeta, motor, caplog) -> None:
    _archivo_firmado(carpeta, b"")
    caplog.set_level(logging.INFO, logger=modulo.__name__)

    assert _reconocedor(carpeta, motor).known_face_names == []
    assert caplog.messages == [
        "[FaceRecognizer] Se recalculan los vectores (No data left in file)."
    ]


def test_el_nombre_de_una_cara_desconocida_es_unknown(carpeta, motor) -> None:
    """Contrato con el pipeline de tracking y los reportes, que guardan este texto."""
    assert _reconocedor(carpeta, motor).recognize_face(_cuadro(ROJO)) == "Unknown"


def test_las_fotos_jpeg_de_la_carpeta_tambien_se_codifican(carpeta, motor) -> None:
    (carpeta / "Ana").mkdir()
    escribir_imagen(str(carpeta / "Ana" / "1.jpeg"), ROJO)

    assert _reconocedor(carpeta, motor).known_face_names == ["Ana"]


def test_un_archivo_suelto_antes_de_una_persona_no_corta_la_carga(carpeta, motor) -> None:
    (carpeta / "0_suelto.jpg").write_bytes(b"no es carpeta de persona")
    (carpeta / "Ana").mkdir()
    escribir_imagen(str(carpeta / "Ana" / "1.png"), ROJO)

    assert _reconocedor(carpeta, motor).known_face_names == ["Ana"]


def test_la_firma_es_hmac_sha256_con_la_clave_de_la_version_2(monkeypatch) -> None:
    """Cambiar la sal invalidaría los archivos de vectores ya instalados en los clientes."""
    monkeypatch.setattr(modulo, "_identificador_de_maquina", lambda: "PC-1")
    clave = hashlib.sha256(b"PC-1_oe_face_integrity_v2").digest()

    assert modulo.firmar(b"datos") == hmac.new(clave, b"datos", hashlib.sha256).digest()


def test_sin_appdata_la_carpeta_queda_en_el_directorio_del_usuario(tmp_path, motor, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    reconocedor = FaceRecognizer(motor=motor)

    assert reconocedor.faces_dir == str(tmp_path / "OficinaEficiencia" / "data" / "faces")


def test_eliminar_a_alguien_sin_carpeta_de_fotos_no_falla(tmp_path, carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)
    reconocedor.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")
    shutil.rmtree(carpeta / "Ana")

    assert reconocedor.delete_face("Ana") is True
    assert reconocedor.known_face_names == []


def test_un_archivo_de_otra_maquina_con_rostros_no_se_carga(carpeta, motor, monkeypatch) -> None:
    monkeypatch.setattr(modulo, "_identificador_de_maquina", lambda: "OTRA-PC")
    _archivo_firmado(
        carpeta,
        _npz(encodings=np.ones((1, 3), np.float32), names=np.array(["Intruso"]),
             motor=np.array(motor.identificador)),
    )  # fmt: skip
    monkeypatch.setattr(modulo, "_identificador_de_maquina", lambda: "ESTA-PC")

    assert _reconocedor(carpeta, motor).known_face_names == []


def test_un_archivo_firmado_con_objetos_pickle_no_se_carga(carpeta, motor) -> None:
    """OWASP A08: aunque la firma sea válida, nunca se deserializa con pickle."""
    nombres = np.array(["Intruso"], dtype=object)
    _archivo_firmado(
        carpeta,
        _npz(encodings=np.ones((1, 3), np.float32), names=nombres,
             motor=np.array(motor.identificador)),
    )  # fmt: skip

    assert _reconocedor(carpeta, motor).known_face_names == []


def test_cargar_un_archivo_valido_lo_registra_en_el_log(carpeta, motor, caplog) -> None:
    _reconocedor(carpeta, MotorFacialFalso())
    caplog.set_level(logging.INFO, logger=modulo.__name__)

    _reconocedor(carpeta, motor)

    assert caplog.messages == ["[FaceRecognizer] 0 rostro(s) cargados."]


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (
            lambda c, m: (c / "encodings.npz").write_bytes(b"x" * 40),
            "firma inválida o de otra máquina",
        ),
        (
            lambda c, m: _archivo_firmado(
                c, _npz(encodings=np.empty((0, 3)), names=np.array([]), motor=np.array("otro"))
            ),
            "vectores de otro motor (otro)",
        ),
    ],
    ids=["firma", "motor"],
)
def test_el_log_explica_por_que_se_recalculan_los_vectores(
    carpeta, motor, caplog, preparar, motivo
):
    (carpeta / "encodings.npz").write_bytes(b"")
    preparar(carpeta, motor)
    caplog.set_level(logging.INFO, logger=modulo.__name__)

    _reconocedor(carpeta, motor)

    assert caplog.messages == [f"[FaceRecognizer] Se recalculan los vectores ({motivo})."]


def test_el_log_avisa_si_el_drm_no_da_el_machine_id(monkeypatch, caplog) -> None:
    def drm_roto() -> None:
        raise RuntimeError("sin WMI")

    monkeypatch.setattr("src.security.drm.DRMValidator", drm_roto)
    caplog.set_level(logging.WARNING, logger=modulo.__name__)

    modulo._identificador_de_maquina()

    assert caplog.messages == ["[FaceRecognizer] Sin machine_id del DRM (RuntimeError)."]


def test_el_log_avisa_la_recarga_y_el_registro_abortado(tmp_path, carpeta, motor, caplog) -> None:
    camara = _reconocedor(carpeta, motor)
    registro = _reconocedor(carpeta, MotorFacialFalso())
    registro.register_face(escribir_imagen(str(tmp_path / "a.png"), ROJO), "Ana")
    marca = os.path.getmtime(registro.encodings_file) + 10
    os.utime(registro.encodings_file, (marca, marca))
    caplog.set_level(logging.INFO, logger=modulo.__name__)

    camara.check_reload()
    camara.register_face(str(tmp_path / "no-existe.png"), "Beto")

    assert caplog.messages == [
        "[FaceRecognizer] El archivo de vectores cambió: se recarga.",
        "[FaceRecognizer] 1 rostro(s) cargados.",
        "[FaceRecognizer] Registro abortado: foto ausente o sin cara.",
    ]


def test_recarga_en_caliente_tras_leer_el_archivo_sin_cambios_no_vuelve_a_leer(
    carpeta, motor, monkeypatch
) -> None:
    _reconocedor(carpeta, MotorFacialFalso())
    reconocedor = _reconocedor(carpeta, motor)
    monkeypatch.setattr(reconocedor, "load_known_faces", lambda: pytest.fail("no debía recargar"))

    reconocedor.check_reload()


def test_reconocer_con_caja_desde_el_origen_conserva_la_primera_fila(carpeta, motor) -> None:
    reconocedor = _reconocedor(carpeta, motor)

    reconocedor.recognize_face(_cuadro(ROJO), bbox=(0, 0, 10, 10))

    assert motor.imagenes_codificadas[-1].shape == (10, 10, 3)
