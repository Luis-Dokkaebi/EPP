import json
import pytest

from src.zones.zone_checker import ZoneChecker


@pytest.fixture
def zones_file(tmp_path):
    zones = {
        "Escritorio": [[100, 100], [200, 100], [200, 200], [100, 200]],
        "Sala":       [[300, 300], [400, 300], [400, 400], [300, 400]],
    }
    path = tmp_path / "zonas.json"
    path.write_text(json.dumps(zones))
    return str(path)


def test_missing_file_does_not_raise(tmp_path):
    checker = ZoneChecker(zones_path=str(tmp_path / "nonexistent.json"))
    assert checker.zones == {}
    assert checker.polygons == {}


def test_empty_zones_file_returns_empty_results(tmp_path):
    path = tmp_path / "zonas.json"
    path.write_text("{}")
    checker = ZoneChecker(zones_path=str(path))
    assert checker.check(150, 150) == {}


def test_point_inside_first_zone(zones_file):
    checker = ZoneChecker(zones_path=zones_file)
    result = checker.check(150, 150)
    assert result["Escritorio"] is True
    assert result["Sala"] is False


def test_point_outside_all_zones(zones_file):
    checker = ZoneChecker(zones_path=zones_file)
    result = checker.check(0, 0)
    assert result["Escritorio"] is False
    assert result["Sala"] is False


def test_point_inside_second_zone(zones_file):
    checker = ZoneChecker(zones_path=zones_file)
    result = checker.check(350, 350)
    assert result["Escritorio"] is False
    assert result["Sala"] is True


def test_check_returns_all_zone_names(zones_file):
    checker = ZoneChecker(zones_path=zones_file)
    result = checker.check(0, 0)
    assert set(result.keys()) == {"Escritorio", "Sala"}


def test_single_zone_boundaries(tmp_path):
    zones = {"Oficina": [[0, 0], [100, 0], [100, 100], [0, 100]]}
    path = tmp_path / "zonas.json"
    path.write_text(json.dumps(zones))
    checker = ZoneChecker(zones_path=str(path))
    assert checker.check(50, 50)["Oficina"] is True
    assert checker.check(150, 150)["Oficina"] is False
