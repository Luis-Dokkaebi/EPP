"""La licencia DRM habilita módulos opcionales (D10: el módulo EPP se activa por licencia)."""

import pytest

from src.security.drm import DRMValidator


@pytest.fixture
def validador(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> DRMValidator:
    monkeypatch.setenv("APPDATA", str(tmp_path_factory.mktemp("appdata")))
    return DRMValidator()


@pytest.mark.parametrize(
    ("datos", "incluye"),
    [
        (None, False),
        ({"tier": "enterprise"}, False),
        ({"modulos": []}, False),
        ({"modulos": ["reportes"]}, False),
        ({"modulos": ["reportes", "epp"]}, True),
    ],
    ids=["sin_licencia", "licencia_sin_modulos", "lista_vacia", "otro_modulo", "con_epp"],
)
def test_la_licencia_incluye_un_modulo_solo_si_lo_nombra(
    validador: DRMValidator, datos: dict[str, object] | None, incluye: bool
) -> None:
    validador.license_data = datos

    assert validador.incluye_modulo("epp") is incluye
