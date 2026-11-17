"""Importar la carpeta de rostros desde la pantalla de empleados (SPEC/10 T-15)."""

import csv
import getpass
from pathlib import Path

import pytest

from config.path_utils import ConfigManager
from src.gui.importacion_rostros_gui import importar_carpeta_de_rostros


class RostrosFalsos:
    def __init__(self, con_rostro: int) -> None:
        self._con_rostro = con_rostro
        self.recibidos: list[tuple[list[str], str]] = []

    def register_face_burst(self, image_paths: list[str], name: str) -> int:
        self.recibidos.append((image_paths, name))
        return min(self._con_rostro, len(image_paths))


class BaseFalsa:
    def __init__(self, *registrados: str) -> None:
        self.perfiles = [(nombre, "", "") for nombre in registrados]

    def employee_exists(self, name: str) -> bool:
        return any(nombre == name for nombre, _depto, _puesto in self.perfiles)

    def save_employee_profile(self, name: str, department: str, position: str) -> None:
        self.perfiles.append((name, department, position))


@pytest.fixture
def carpeta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Planta")
    monkeypatch.setattr(getpass, "getuser", lambda: "supervisor")
    origen = tmp_path / "rostros_acme"
    (origen / "Ana Lopez").mkdir(parents=True)
    (origen / "Ana Lopez" / "a.jpg").write_bytes(b"foto")
    (origen / "Ana Lopez" / "b.jpg").write_bytes(b"foto")
    (origen / "Pedro Gil").mkdir()
    (origen / "consentimientos.csv").write_text(
        "nombre,id_consentimiento\nAna Lopez,C-001\n", encoding="utf-8"
    )
    return origen


def _bitacora(tmp_path: Path) -> Path:
    sucursal = tmp_path / "appdata" / "OficinaEficiencia" / "Tenants" / "Planta"
    return sucursal / "importaciones_rostros.csv"


def test_importar_registra_el_rostro_el_perfil_y_la_bitacora_de_la_sucursal(
    carpeta: Path, tmp_path: Path
) -> None:
    rostros, base = RostrosFalsos(con_rostro=2), BaseFalsa()

    mensaje = importar_carpeta_de_rostros(carpeta, rostros, base)

    fotos = [str(carpeta / "Ana Lopez" / "a.jpg"), str(carpeta / "Ana Lopez" / "b.jpg")]
    assert mensaje == (
        "Cargados: 1 (Ana Lopez). Omitidos: Pedro Gil (sin consentimiento registrado)."
    )
    assert rostros.recibidos == [(fotos, "Ana Lopez")]
    assert base.perfiles == [("Ana Lopez", "", "")]
    with _bitacora(tmp_path).open(encoding="utf-8", newline="") as archivo:
        [fila] = list(csv.DictReader(archivo))
    assert (fila["operador"], fila["nombre"], fila["id_consentimiento"], fila["fotos"]) == (
        "supervisor",
        "Ana Lopez",
        "C-001",
        "2",
    )
    assert fila["fecha"].endswith("+00:00")


def test_si_ninguna_foto_tiene_rostro_no_se_crea_el_perfil(carpeta: Path) -> None:
    rostros, base = RostrosFalsos(con_rostro=0), BaseFalsa()

    mensaje = importar_carpeta_de_rostros(carpeta, rostros, base)

    assert mensaje.startswith("Cargados: 0. Omitidos: Ana Lopez (sin rostro detectable")
    assert base.perfiles == []


def test_un_empleado_ya_registrado_no_se_vuelve_a_cargar(carpeta: Path) -> None:
    rostros, base = RostrosFalsos(con_rostro=2), BaseFalsa("Ana Lopez")

    mensaje = importar_carpeta_de_rostros(carpeta, rostros, base)

    assert "Ana Lopez (ya estaba registrado)" in mensaje
    assert rostros.recibidos == []


def test_sin_constancia_de_consentimientos_se_explica_y_no_se_carga_nada(carpeta: Path) -> None:
    (carpeta / "consentimientos.csv").unlink()
    rostros, base = RostrosFalsos(con_rostro=2), BaseFalsa()

    mensaje = importar_carpeta_de_rostros(carpeta, rostros, base)

    assert mensaje == (
        "Falta consentimientos.csv en la carpeta: sin constancia no se carga a nadie."
    )
    assert (rostros.recibidos, base.perfiles) == ([], [])


def test_con_una_sola_foto_con_rostro_alcanza_para_crear_el_perfil(carpeta: Path) -> None:
    rostros, base = RostrosFalsos(con_rostro=1), BaseFalsa()

    mensaje = importar_carpeta_de_rostros(carpeta, rostros, base)

    assert mensaje.startswith("Cargados: 1 (Ana Lopez).")
    assert base.perfiles == [("Ana Lopez", "", "")]
