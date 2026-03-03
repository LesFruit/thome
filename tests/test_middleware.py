"""Tests for middleware: request ID, access logging, error handling."""

import json


def test_response_has_request_id_header(client):
    """Every response must include X-Request-ID."""
    resp = client.get("/health")
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) > 0


def test_request_id_is_echoed_when_provided(client):
    """If client sends X-Request-ID, server echoes it back."""
    resp = client.get("/health", headers={"X-Request-ID": "test-123"})
    assert resp.headers["x-request-id"] == "test-123"


def test_error_envelope_on_404(client):
    """404 returns consistent error envelope, not raw FastAPI default."""
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


def test_error_envelope_on_405(client):
    """405 returns consistent error envelope."""
    resp = client.post("/health")
    assert resp.status_code == 405
    body = resp.json()
    assert "error" in body


def test_error_envelope_does_not_leak_traceback(client):
    """Error responses must not contain stack traces."""
    resp = client.get("/nonexistent")
    body = json.dumps(resp.json())
    assert "Traceback" not in body
    assert "File " not in body


def test_health_response_time_header(client):
    """Responses include X-Process-Time header."""
    resp = client.get("/health")
    assert "x-process-time" in resp.headers
    # Should be a valid float (milliseconds)
    float(resp.headers["x-process-time"])
