from datetime import datetime

import pytest

from logic import (
    as_id,
    duration_hours,
    find_conflict,
    is_valid_email,
    parse_window,
    validate_person,
)


def at(hour):
    return datetime(2026, 11, 12, hour)


def lesson(instructor_id, aircraft_id, start_hour, end_hour):
    return {
        "instructor_id": instructor_id,
        "aircraft_id": aircraft_id,
        "start_time": at(start_hour),
        "end_time": at(end_hour),
    }


def test_free_slot_has_no_conflict():
    assert find_conflict(at(10), at(12), 1, 1, []) is None


def test_double_booking_the_same_instructor_is_rejected():
    message = find_conflict(at(10), at(12), 1, 2, [lesson(1, 9, 11, 13)])
    assert "instructor is already booked" in message


def test_double_booking_the_same_aircraft_is_rejected():
    message = find_conflict(at(10), at(12), 1, 2, [lesson(7, 2, 9, 11)])
    assert "aircraft is already booked" in message


def test_back_to_back_lessons_do_not_conflict():
    assert find_conflict(at(12), at(14), 1, 1, [lesson(1, 1, 10, 12)]) is None


def test_parse_window_returns_datetimes():
    assert parse_window("2026-11-12T10:00", "2026-11-12T12:00") == (at(10), at(12))


def test_end_time_before_start_time_is_rejected():
    with pytest.raises(ValueError, match="end time must be after start time"):
        parse_window("2026-11-12T12:00", "2026-11-12T10:00")


@pytest.mark.parametrize("start", ["tomorrow", None])
def test_unreadable_times_are_rejected(start):
    with pytest.raises(ValueError, match="ISO dates"):
        parse_window(start, "2026-11-12T10:00")


def test_duration_in_hours():
    assert duration_hours(at(10), at(12)) == 2.0


@pytest.mark.parametrize("email", ["alex@example.com", "a.b@school.co.uk"])
def test_valid_emails(email):
    assert is_valid_email(email)


@pytest.mark.parametrize("email", ["", None, "alex", "@example.com", "alex@example"])
def test_invalid_emails(email):
    assert not is_valid_email(email)


def test_person_needs_name_and_valid_email():
    with pytest.raises(ValueError, match="name"):
        validate_person("", "alex@example.com")
    with pytest.raises(ValueError, match="invalid email"):
        validate_person("Alex Rivera", "alex")
    validate_person("Alex Rivera", "alex@example.com")


def test_ids_accept_numbers_and_numeric_strings():
    assert as_id(3, "student") == 3
    assert as_id("3", "student") == 3


@pytest.mark.parametrize("value", [None, "", "abc"])
def test_missing_or_bad_ids_are_rejected(value):
    with pytest.raises(ValueError, match="student is required"):
        as_id(value, "student")
