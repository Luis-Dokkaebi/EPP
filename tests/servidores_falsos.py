"""Servidores locales falsos para probar los canales de aviso sin red real (SPEC/9 §7.5; §4).

Todo escucha en 127.0.0.1, en un puerto libre, dentro de un hilo que la prueba arranca y detiene
con `with`. El certificado TLS es autofirmado y se genera en `tmp_path`; su vigencia de un día
hacia atrás y otro hacia adelante es lo único que depende del reloj real, porque la verificación
TLS lo exige.
"""

import ipaddress
import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta
from email.message import Message
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import NamedTuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

LOCAL = "127.0.0.1"
UN_DIA = timedelta(days=1)


class CertificadoLocal(NamedTuple):
    certificado: Path
    clave: Path
    pem: str


def certificado_autofirmado(carpeta: Path) -> CertificadoLocal:
    """Certificado válido para 127.0.0.1 y localhost, con su clave, guardados en `carpeta`."""
    clave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    ahora = datetime.now(UTC)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - UN_DIA)
        .not_valid_after(ahora + UN_DIA)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address(LOCAL))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(clave, hashes.SHA256())
    )
    pem = certificado.public_bytes(serialization.Encoding.PEM)
    ruta_certificado = carpeta / "local.crt"
    ruta_clave = carpeta / "local.key"
    ruta_certificado.write_bytes(pem)
    ruta_clave.write_bytes(
        clave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return CertificadoLocal(ruta_certificado, ruta_clave, pem.decode())


def contexto_cliente(certificado: CertificadoLocal) -> ssl.SSLContext:
    """Contexto TLS de cliente que confía solo en el certificado local."""
    return ssl.create_default_context(cadata=certificado.pem)


def contexto_servidor(certificado: CertificadoLocal) -> ssl.SSLContext:
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(certificado.certificado, certificado.clave)
    return contexto


def puerto_cerrado() -> int:
    """Un puerto de 127.0.0.1 en el que no escucha nadie (canal caído)."""
    with socket.socket() as libre:
        libre.bind((LOCAL, 0))
        return int(libre.getsockname()[1])


class PedidoRecibido(NamedTuple):
    ruta: str
    encabezados: Message
    cuerpo: bytes
    estado: int


class ServidorWebhookFalso:
    """Webhook en 127.0.0.1 que guarda cada POST y responde el código de `estado`.

    `estado` se puede cambiar durante la prueba (canal caído y restablecido). Si `retener` está
    sin marcar, el servidor demora la respuesta hasta que la prueba lo marque (canal lento).
    """

    def __init__(self, tls: ssl.SSLContext | None = None) -> None:
        self.estado = HTTPStatus.OK
        self.recibidos: list[PedidoRecibido] = []
        self.retener = threading.Event()
        self.retener.set()
        self._servidor = ThreadingHTTPServer((LOCAL, 0), self._manejador())
        self._servidor.daemon_threads = True
        if tls is not None:
            self._servidor.socket = tls.wrap_socket(self._servidor.socket, server_side=True)
        self._esquema = "http" if tls is None else "https"
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)

    @property
    def aceptados(self) -> list[PedidoRecibido]:
        """Los pedidos que el webhook respondió con éxito (2xx)."""
        return [pedido for pedido in self.recibidos if pedido.estado < HTTPStatus.MULTIPLE_CHOICES]

    @property
    def url(self) -> str:
        return f"{self._esquema}://{LOCAL}:{self._servidor.server_address[1]}/avisos"

    def __enter__(self) -> "ServidorWebhookFalso":
        self._hilo.start()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.retener.set()
        self._servidor.shutdown()
        self._servidor.server_close()
        self._hilo.join()

    def _manejador(self) -> type[BaseHTTPRequestHandler]:
        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - nombre que exige http.server
                largo = int(self.headers.get("Content-Length", "0"))
                cuerpo = self.rfile.read(largo)
                estado = falso.estado
                falso.recibidos.append(PedidoRecibido(self.path, self.headers, cuerpo, estado))
                falso.retener.wait()
                self.send_response(estado)
                if HTTPStatus.MULTIPLE_CHOICES <= estado < HTTPStatus.BAD_REQUEST:
                    self.send_header("Location", "http://127.0.0.1:9/otra")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, formato: str, *argumentos: object) -> None:
                """Sin salida por consola en las pruebas."""

        return Manejador
