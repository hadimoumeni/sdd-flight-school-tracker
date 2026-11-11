"""HTTP calls from scheduling to the maintenance service (the seam from ADR-2)."""

import os

import requests


class MaintenanceUnavailable(Exception):
    """Maintenance did not answer in time, or answered with a server error."""


def _url(path):
    base = os.environ.get("MAINTENANCE_URL", "http://maintenance:8000")
    return base.rstrip("/") + path


def _timeout():
    return float(os.environ.get("MAINTENANCE_TIMEOUT_S", "2"))


def _call(method, path, **kwargs):
    try:
        response = requests.request(method, _url(path), timeout=_timeout(), **kwargs)
    except requests.RequestException as exc:
        raise MaintenanceUnavailable(str(exc)) from exc
    if response.status_code >= 500:
        raise MaintenanceUnavailable(f"maintenance returned {response.status_code}")
    if response.status_code == 404:
        raise ValueError("unknown aircraft")
    return response.json()


def check_airworthiness(aircraft_id):
    """Returns (airworthy, reason)."""
    body = _call("GET", f"/aircraft/{aircraft_id}/airworthiness")
    return body["airworthy"], body["reason"]


def log_flight_hours(aircraft_id, hours):
    _call("POST", f"/aircraft/{aircraft_id}/flight-hours", json={"hours": hours})
