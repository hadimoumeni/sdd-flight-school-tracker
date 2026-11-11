import pytest

from logic import airworthiness, validate_aircraft, validate_hours, validate_squawk


def test_fresh_aircraft_is_airworthy():
    assert airworthiness(0, 0, []) == (True, None)


def test_aircraft_over_100_hours_since_inspection_is_grounded():
    airworthy, reason = airworthiness(150, 50, [])
    assert airworthy is False
    assert "100-hour inspection" in reason


def test_aircraft_under_100_hours_since_inspection_is_airworthy():
    assert airworthiness(149.9, 50, []) == (True, None)


def test_aircraft_with_open_safety_squawk_is_grounded():
    airworthy, reason = airworthiness(0, 0, ["Left brake not holding"])
    assert airworthy is False
    assert "Left brake not holding" in reason


def test_inspection_overdue_is_reported_before_squawks():
    _, reason = airworthiness(200, 0, ["Left brake not holding"])
    assert "100-hour inspection" in reason


@pytest.mark.parametrize("tail_number,model", [("", "Cessna 172"), ("N123", ""), (None, None)])
def test_aircraft_needs_tail_number_and_model(tail_number, model):
    with pytest.raises(ValueError, match="required"):
        validate_aircraft(tail_number, model)


def test_valid_aircraft_passes():
    validate_aircraft("N12345", "Cessna 172")


def test_squawk_needs_description():
    with pytest.raises(ValueError, match="description"):
        validate_squawk("", "minor")


def test_squawk_severity_must_be_known():
    with pytest.raises(ValueError, match="severity"):
        validate_squawk("Flat tyre", "urgent")


def test_valid_squawk_passes():
    validate_squawk("Flat tyre", "safety")


@pytest.mark.parametrize("hours", [0, -1, "2", None])
def test_flight_hours_must_be_positive_number(hours):
    with pytest.raises(ValueError, match="positive"):
        validate_hours(hours)


def test_positive_flight_hours_pass():
    validate_hours(2.5)
