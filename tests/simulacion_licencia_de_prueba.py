"""Simulación de la prueba de 14 días en el equipo del cliente (SPEC/10 §4 y §10).

Une las piezas reales: el emisor del proveedor firma con una llave de la corrida, el DRM valida
con la pública inyectada, el aviso sale del presentador y la guardia revalida. Solo son dobles el
reloj, la ventana principal y la librería de rostros (dlib no existe fuera de Windows).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.keygen_b2b import (
    Pedido,
    PedidoInvalidoError,
    RegistroDeEmisiones,
    emitir_licencia,
    pedido_del_tier,
)
from src.gui.aviso_licencia import aviso_de_prueba
from src.recognition import face_recognizer
from src.recognition.face_recognizer import FaceRecognizer
from src.security import drm
from src.security.drm import DRMValidator
from src.security.guardia_licencia import GuardiaDeLicencia
from tests.licencias_firmadas import RelojEn, generar_llave, publica_de

HOY = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
OTRO_EQUIPO = "cd" * 32
HUELLA_DE_ROSTRO = [0.25] * 128
LO_APRENDIDO = ("faces/Ana/foto.jpg", "zonas/zonas_config.json", "db/local_tracking.db")


class VentanaPrincipalFalsa:
    """La app vigilada por la guardia: anota lo que se le pide; nadie activa otra licencia."""

    def __init__(self) -> None:
        self.vigilando = True
        self.pidio_licencia = False

    def suspender(self) -> None:
        self.vigilando = False

    def pedir_licencia(self) -> bool:
        self.pidio_licencia = True
        return False

    def reanudar(self) -> None:
        self.vigilando = True

    def cerrar(self) -> None:
        self.vigilando = False


class EquipoDelCliente:
    """La PC del cliente con la app instalada y el proveedor que le emite licencias."""

    def __init__(self, carpeta: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self._llave = generar_llave()
        self._registro = RegistroDeEmisiones(carpeta / "proveedor" / "emisiones.csv")
        self._sucursal = carpeta / "appdata" / "OficinaEficiencia" / "Tenants" / "Planta"
        monkeypatch.setenv("APPDATA", str(carpeta / "appdata"))
        monkeypatch.setattr(face_recognizer, "face_recognition", MagicMock())
        self.poner_reloj(HOY)
        self.licencia = DRMValidator(publica_de(self._llave))
        self.app = VentanaPrincipalFalsa()
        self.ultima_activacion: bool | None = None
        self.emision_rechazada = False

    def poner_reloj(self, instante: datetime) -> None:
        self._ahora = instante
        self._monkeypatch.setattr(drm, "datetime", RelojEn(instante.timestamp()))

    def adelantar(self, tiempo: timedelta) -> None:
        self.poner_reloj(self._ahora + tiempo)

    def emitir(self, tier: str, emitida: datetime, dias: int | None = None) -> str:
        """Lo que hace el proveedor: firma la licencia para este equipo y la anota."""
        return self._emitir(self.licencia.machine_id, tier, emitida, dias)

    def emitir_para_otro_equipo(self) -> str:
        return self._emitir(OTRO_EQUIPO, "prueba", HOY, None)

    def _emitir(self, hw_id: str, tier: str, emitida: datetime, dias: int | None) -> str:
        base = pedido_del_tier(hw_id, "acme-planta1", tier)
        pedido = Pedido(hw_id, base.cliente, tier, dias or base.dias, base.camaras, base.modulos)
        numero = (
            len(self._registro.ruta.read_text().splitlines()) if self._registro.ruta.exists() else 0
        )
        return emitir_licencia(pedido, self._llave, self._registro, emitida, f"licencia-{numero}")

    def intentar_otra_prueba(self) -> None:
        try:
            self.emitir("prueba", HOY)
        except PedidoInvalidoError:
            self.emision_rechazada = True

    def instalar(self, licencia: str) -> None:
        """Deja la licencia guardada como si se hubiera activado al emitirse."""
        Path(self.licencia.license_path).write_text(licencia, encoding="utf-8")

    def activar(self, licencia: str) -> None:
        self.ultima_activacion = self.licencia.activate_license(licencia)

    def abrir(self) -> bool:
        return self.licencia.validate_license()

    def aviso(self) -> str | None:
        aviso = aviso_de_prueba(self.licencia)
        return None if aviso is None else aviso.texto

    def revalidar(self) -> None:
        GuardiaDeLicencia(self.licencia, self.app).revisar()

    def guardar_lo_aprendido(self) -> None:
        for relativo in LO_APRENDIDO:
            archivo = self._sucursal / relativo
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(f"contenido de {relativo}", encoding="utf-8")

    def lo_aprendido(self) -> dict[str, str]:
        return {
            relativo: (self._sucursal / relativo).read_text(encoding="utf-8")
            for relativo in LO_APRENDIDO
        }

    def registrar_empleado(self, nombre: str) -> None:
        rostros = self._rostros()
        rostros.known_face_names.append(nombre)
        rostros.known_face_encodings.append(HUELLA_DE_ROSTRO)
        rostros.save_encodings()

    def empleados_reconocibles(self) -> list[str]:
        nombres: list[str] = self._rostros().known_face_names
        return nombres

    def _rostros(self) -> FaceRecognizer:
        carpeta = self._sucursal / "faces"
        return FaceRecognizer(str(carpeta), str(carpeta / "encodings.npz"))
