"""The HTTP client, with maintenance replaced by a fake requests.request."""

import pytest
import requests

import maintenance_client
from maintenance_client import MaintenanceUnavailable


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def answer_with(monkeypatch, response):
    calls = []

    def fake_request(method, url, timeout, **kwargs):
        calls.append({"method": method, "url": url, "timeout": timeout, **kwargs})
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "request", fake_request)
    return calls


def test_airworthy_aircraft(monkeypatch):
    answer_with(monkeypatch, FakeResponse(200, {"airworthy": True, "reason": None}))
    assert maintenance_client.check_airworthiness(3) == (True, None)


def test_uses_maintenance_url_and_timeout_from_environment(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_URL", "http://maintenance.test:9000/")
    monkeypatch.setenv("MAINTENANCE_TIMEOUT_S", "1.5")
    calls = answer_with(monkeypatch, FakeResponse(200, {"airworthy": True, "reason": None}))
    maintenance_client.check_airworthiness(3)
    assert calls[0]["url"] == "http://maintenance.test:9000/aircraft/3/airworthiness"
    assert calls[0]["timeout"] == 1.5


def test_unknown_aircraft_is_a_user_error(monkeypatch):
    answer_with(monkeypatch, FakeResponse(404, {"error": "aircraft not found"}))
    with pytest.raises(ValueError, match="unknown aircraft"):
        maintenance_client.check_airworthiness(99)


@pytest.mark.parametrize(
    "failure",
    [requests.Timeout("too slow"), requests.ConnectionError("refused"), FakeResponse(503)],
    ids=["timeout", "connection-refused", "server-error"],
)
def test_maintenance_down_raises_unavailable(monkeypatch, failure):
    answer_with(monkeypatch, failure)
    with pytest.raises(MaintenanceUnavailable):
        maintenance_client.check_airworthiness(3)


def test_log_flight_hours_posts_the_hours(monkeypatch):
    calls = answer_with(monkeypatch, FakeResponse(200, {"aircraft_id": 3, "added_hours": 2.0}))
    maintenance_client.log_flight_hours(3, 2.0)
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/aircraft/3/flight-hours")
    assert calls[0]["json"] == {"hours": 2.0}
