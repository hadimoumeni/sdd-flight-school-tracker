"""Scheduling service: students, instructors and lessons, as a JSON API.

Booking and completing a lesson call the maintenance service over HTTP.
"""

import logging
import os
import time
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask.json.provider import DefaultJSONProvider
from sqlalchemy.exc import SQLAlchemyError

import logic
import maintenance_client
import store
from db import get_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("scheduling")


class IsoDatesJSON(DefaultJSONProvider):
    """Send datetimes as ISO 8601 (2026-11-12T10:00:00), not Flask's default HTTP-date format."""

    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = IsoDatesJSON(app)
UI_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:8080")
VERSION = os.environ.get("GIT_SHA", "dev")
MAINTENANCE_DOWN = (
    "maintenance service is unavailable, so the aircraft cannot be checked. Try again later."
)


@app.before_request
def start_timer():
    g.start = time.perf_counter()


@app.after_request
def log_request_and_allow_ui(response):
    duration_ms = (time.perf_counter() - g.start) * 1000
    log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, duration_ms)
    # CORS: only the UI's origin may call this service from a browser.
    response.headers["Access-Control-Allow-Origin"] = UI_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.errorhandler(ValueError)
def bad_request(exc):
    return jsonify(error=str(exc)), 400


@app.errorhandler(maintenance_client.MaintenanceUnavailable)
def maintenance_unavailable(exc):
    log.warning("maintenance call failed: %s", exc)
    return jsonify(error=MAINTENANCE_DOWN), 503


@app.get("/health")
def health():
    # Only this service's own database: health never depends on maintenance.
    try:
        with get_engine().begin() as conn:
            db_ok = store.touch_health_check(conn)
    except SQLAlchemyError:
        db_ok = False
    status = 200 if db_ok else 503
    body = {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error"}
    return jsonify(**body, version=VERSION), status


@app.get("/students")
def list_students():
    with get_engine().connect() as conn:
        return jsonify([dict(s) for s in store.list_students(conn)])


@app.post("/students")
def create_student():
    data = request.get_json(force=True)
    logic.validate_person(data.get("name"), data.get("email"))
    with get_engine().begin() as conn:
        student_id = store.create_student(conn, data["name"], data["email"])
    return jsonify(id=student_id), 201


@app.get("/instructors")
def list_instructors():
    with get_engine().connect() as conn:
        return jsonify([dict(i) for i in store.list_instructors(conn)])


@app.post("/instructors")
def create_instructor():
    data = request.get_json(force=True)
    logic.validate_person(data.get("name"), data.get("email"))
    if not data.get("certificate_number"):
        raise ValueError("certificate number is required")
    with get_engine().begin() as conn:
        instructor_id = store.create_instructor(
            conn, data["name"], data["email"], data["certificate_number"]
        )
    return jsonify(id=instructor_id), 201


@app.get("/lessons")
def list_lessons():
    with get_engine().connect() as conn:
        return jsonify([dict(lesson) for lesson in store.list_lessons(conn)])


@app.post("/lessons")
def book_lesson():
    data = request.get_json(force=True)
    start, end = logic.parse_window(data.get("start_time"), data.get("end_time"))
    student_id = logic.as_id(data.get("student_id"), "student")
    instructor_id = logic.as_id(data.get("instructor_id"), "instructor")
    aircraft_id = logic.as_id(data.get("aircraft_id"), "aircraft")

    with get_engine().begin() as conn:
        if not store.student_exists(conn, student_id):
            raise ValueError("unknown student")
        if not store.instructor_exists(conn, instructor_id):
            raise ValueError("unknown instructor")

        # Cross-seam call: is the aircraft allowed to fly? (maintenance owns that rule)
        airworthy, reason = maintenance_client.check_airworthiness(aircraft_id)
        if not airworthy:
            raise ValueError(reason)

        existing = store.scheduled_lessons_for(conn, instructor_id, aircraft_id)
        conflict = logic.find_conflict(start, end, instructor_id, aircraft_id, existing)
        if conflict:
            raise ValueError(conflict)

        lesson_id = store.create_lesson(conn, student_id, instructor_id, aircraft_id, start, end)
    return jsonify(id=lesson_id), 201


@app.post("/lessons/<int:lesson_id>/complete")
def complete_lesson(lesson_id):
    with get_engine().begin() as conn:
        lesson = store.get_lesson(conn, lesson_id)
        if lesson is None or lesson["status"] != "scheduled":
            raise ValueError("lesson is not scheduled")

        hours = logic.duration_hours(lesson["start_time"], lesson["end_time"])
        # Log the hours first: if maintenance is down, the lesson stays scheduled.
        maintenance_client.log_flight_hours(lesson["aircraft_id"], hours)
        store.mark_completed(conn, lesson_id)
    return jsonify(id=lesson_id, status="completed", hours=hours)
