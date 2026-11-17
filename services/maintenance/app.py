"""Maintenance service: aircraft, squawks and airworthiness, as a JSON API."""

import logging
import os
import time
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask.json.provider import DefaultJSONProvider
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import logic
import store
from db import get_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("maintenance")


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


def with_airworthiness(conn, aircraft):
    airworthy, reason = logic.airworthiness(
        aircraft["total_hours"],
        aircraft["hours_at_last_inspection"],
        store.open_safety_squawks(conn, aircraft["id"]),
    )
    return {**aircraft, "airworthy": airworthy, "reason": reason}


@app.get("/health")
def health():
    try:
        with get_engine().begin() as conn:
            db_ok = store.touch_health_check(conn)
    except SQLAlchemyError:
        db_ok = False
    status = 200 if db_ok else 503
    body = {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error"}
    return jsonify(**body, version=VERSION), status


@app.get("/aircraft")
def list_aircraft():
    with get_engine().connect() as conn:
        aircraft = [with_airworthiness(conn, a) for a in store.list_aircraft(conn)]
    return jsonify(aircraft)


@app.post("/aircraft")
def create_aircraft():
    data = request.get_json(force=True)
    logic.validate_aircraft(data.get("tail_number"), data.get("model"))
    try:
        with get_engine().begin() as conn:
            aircraft_id = store.create_aircraft(conn, data["tail_number"], data["model"])
    except IntegrityError:
        return jsonify(error="tail number already exists"), 409
    return jsonify(id=aircraft_id), 201


@app.get("/aircraft/<int:aircraft_id>/airworthiness")
def airworthiness(aircraft_id):
    with get_engine().connect() as conn:
        aircraft = store.get_aircraft(conn, aircraft_id)
        if aircraft is None:
            return jsonify(error="aircraft not found"), 404
        result = with_airworthiness(conn, aircraft)
    return jsonify(aircraft_id=aircraft_id, airworthy=result["airworthy"], reason=result["reason"])


@app.post("/aircraft/<int:aircraft_id>/flight-hours")
def add_flight_hours(aircraft_id):
    hours = request.get_json(force=True).get("hours")
    logic.validate_hours(hours)
    with get_engine().begin() as conn:
        if not store.add_flight_hours(conn, aircraft_id, hours):
            return jsonify(error="aircraft not found"), 404
    return jsonify(aircraft_id=aircraft_id, added_hours=hours)


@app.get("/squawks")
def list_open_squawks():
    with get_engine().connect() as conn:
        squawks = [dict(s) for s in store.list_open_squawks(conn)]
    return jsonify(squawks)


@app.post("/squawks")
def report_squawk():
    data = request.get_json(force=True)
    logic.validate_squawk(data.get("description"), data.get("severity"))
    with get_engine().begin() as conn:
        if store.get_aircraft(conn, data.get("aircraft_id")) is None:
            return jsonify(error="aircraft not found"), 404
        squawk_id = store.create_squawk(
            conn, data["aircraft_id"], data["description"], data["severity"]
        )
    return jsonify(id=squawk_id), 201


@app.post("/squawks/<int:squawk_id>/resolve")
def resolve_squawk(squawk_id):
    with get_engine().begin() as conn:
        if not store.resolve_squawk(conn, squawk_id):
            return jsonify(error="no open squawk with that id"), 404
    return jsonify(id=squawk_id, resolved=True)
