"""Cross-seam integration tests, run against the real system: both services and
SQL Server, started with docker compose. Nothing is stubbed.

    docker compose up -d --build
    pip install -r tests/integration/requirements.txt
    pytest tests/integration -v

Every test creates its own aircraft, student and instructor (unique names), so the
tests do not depend on each other or on data already in the database.
"""

import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import requests
import yaml

MAINTENANCE = os.environ.get("MAINTENANCE_URL", "http://localhost:8001")
SCHEDULING = os.environ.get("SCHEDULING_URL", "http://localhost:8002")
REPO_ROOT = Path(__file__).resolve().parents[2]


def wait_until_healthy(base_url, timeout_s=240):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{base_url}/health", timeout=5).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    pytest.fail(f"{base_url} did not become healthy in {timeout_s} s")


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=REPO_ROOT, check=True)


def post(base_url, path, body=None):
    return requests.post(f"{base_url}{path}", json=body or {}, timeout=10)


@pytest.fixture(scope="session", autouse=True)
def system_is_up():
    wait_until_healthy(MAINTENANCE)
    wait_until_healthy(SCHEDULING)


@pytest.fixture
def aircraft_id():
    tail = f"N{uuid.uuid4().hex[:6].upper()}"
    r = post(MAINTENANCE, "/aircraft", {"tail_number": tail, "model": "Cessna 172"})
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def people():
    """A new student and instructor, so instructor bookings never clash between tests."""
    name = uuid.uuid4().hex[:6]
    student = post(SCHEDULING, "/students", {"name": f"S {name}", "email": f"s{name}@ex.com"})
    instructor = post(
        SCHEDULING,
        "/instructors",
        {"name": f"I {name}", "email": f"i{name}@ex.com", "certificate_number": "CFI-1"},
    )
    return student.json()["id"], instructor.json()["id"]


def book(people, aircraft_id, start="2026-12-01T10:00", end="2026-12-01T12:00"):
    student_id, instructor_id = people
    return post(
        SCHEDULING,
        "/lessons",
        {
            "student_id": student_id,
            "instructor_id": instructor_id,
            "aircraft_id": aircraft_id,
            "start_time": start,
            "end_time": end,
        },
    )


def aircraft_by_id(aircraft_id):
    aircraft = requests.get(f"{MAINTENANCE}/aircraft", timeout=10).json()
    return next(a for a in aircraft if a["id"] == aircraft_id)


def test_booking_an_airworthy_aircraft_succeeds(people, aircraft_id):
    r = book(people, aircraft_id)
    assert r.status_code == 201
    assert r.json()["id"] > 0


def test_safety_squawk_in_maintenance_blocks_booking_in_scheduling(people, aircraft_id):
    squawk = {"aircraft_id": aircraft_id, "description": "Left brake not holding", "severity": "safety"}
    assert post(MAINTENANCE, "/squawks", squawk).status_code == 201

    r = book(people, aircraft_id)
    assert r.status_code == 400
    assert "Left brake not holding" in r.json()["error"]


def test_unknown_aircraft_is_rejected(people):
    r = book(people, 999_999)
    assert r.status_code == 400
    assert r.json()["error"] == "unknown aircraft"


def test_completing_a_lesson_logs_flight_hours_in_maintenance(people, aircraft_id):
    lesson_id = book(people, aircraft_id, "2026-12-02T09:00", "2026-12-02T11:30").json()["id"]

    r = post(SCHEDULING, f"/lessons/{lesson_id}/complete")
    assert r.status_code == 200
    assert r.json()["hours"] == 2.5
    assert aircraft_by_id(aircraft_id)["total_hours"] == 2.5

    lesson = next(
        lesson
        for lesson in requests.get(f"{SCHEDULING}/lessons", timeout=10).json()
        if lesson["id"] == lesson_id
    )
    assert lesson["status"] == "completed"
    assert lesson["completed_at"]  # column added by migration 002


def test_maintenance_down_gives_a_clear_503_not_a_hang(people, aircraft_id):
    compose("stop", "maintenance")
    try:
        # Scheduling still serves its own domain...
        assert requests.get(f"{SCHEDULING}/health", timeout=10).status_code == 200
        assert requests.get(f"{SCHEDULING}/lessons", timeout=10).status_code == 200

        # ...and the cross-seam flow fails fast, with a message instead of a stack trace.
        started = time.monotonic()
        r = book(people, aircraft_id)
        elapsed = time.monotonic() - started
        assert r.status_code == 503
        assert "maintenance service is unavailable" in r.json()["error"]
        assert elapsed < 5
    finally:
        compose("start", "maintenance")
        wait_until_healthy(MAINTENANCE)


def test_cross_seam_responses_match_the_maintenance_openapi_document(aircraft_id):
    """What scheduling relies on must be what maintenance's openapi.yaml promises."""
    spec = yaml.safe_load((REPO_ROOT / "services/maintenance/openapi.yaml").read_text())
    paths = spec["paths"]

    airworthiness = requests.get(
        f"{MAINTENANCE}/aircraft/{aircraft_id}/airworthiness", timeout=10
    ).json()
    assert set(airworthiness) == set(spec["components"]["schemas"]["Airworthiness"]["required"])

    flight_hours = post(MAINTENANCE, f"/aircraft/{aircraft_id}/flight-hours", {"hours": 1.0})
    documented = paths["/aircraft/{aircraft_id}/flight-hours"]["post"]["responses"]["200"]
    schema = documented["content"]["application/json"]["schema"]
    assert set(flight_hours.json()) == set(schema["required"])
