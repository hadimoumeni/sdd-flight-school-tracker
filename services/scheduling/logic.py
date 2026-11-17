"""Scheduling business rules. Pure functions: no database, no HTTP."""

from datetime import datetime


def is_valid_email(email):
    if not email or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


def validate_person(name, email):
    if not name:
        raise ValueError("name is required")
    if not is_valid_email(email):
        raise ValueError("invalid email")


def as_id(value, name):
    """IDs arrive as JSON; accept 3 or "3", reject anything else."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is required") from exc


def parse_window(start_time, end_time):
    """Turn two ISO strings into datetimes; the lesson must end after it starts."""
    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
    except (TypeError, ValueError) as exc:
        raise ValueError("start and end times must be ISO dates, e.g. 2026-11-12T10:00") from exc
    if end <= start:
        raise ValueError("end time must be after start time")
    return start, end


def find_conflict(start, end, instructor_id, aircraft_id, existing_lessons):
    """
    Return a conflict message if the new lesson overlaps a scheduled lesson
    with the same instructor or aircraft, otherwise None.
    """
    for lesson in existing_lessons:
        overlaps = start < lesson["end_time"] and lesson["start_time"] < end
        if not overlaps:
            continue
        if lesson["instructor_id"] == instructor_id:
            return "booking conflict: instructor is already booked in that window"
        if lesson["aircraft_id"] == aircraft_id:
            return "booking conflict: aircraft is already booked in that window"
    return None


def duration_hours(start, end):
    return (end - start).total_seconds() / 3600
