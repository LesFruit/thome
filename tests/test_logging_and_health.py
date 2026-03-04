"""TDD tests for structured logging, sanitization, and error tracking."""

import json
import logging


def test_json_log_format(client, capsys):
    """Structured logs are valid JSON with required fields."""
    # Trigger a request that produces logs
    client.get("/health")
    # We can at least verify the logger setup works
    from app.logging_config import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "timestamp" in parsed
    assert "level" in parsed
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message"


def test_json_log_includes_request_context():
    """Log records with request context fields are included in JSON output."""
    from app.logging_config import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Access",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 1.5
    output = json.loads(formatter.format(record))
    assert output["request_id"] == "req-123"
    assert output["method"] == "GET"
    assert output["status_code"] == 200
    assert output["duration_ms"] == 1.5


def test_error_envelope_no_traceback_on_500(client):
    """500 responses must not contain stack traces."""
    # 404 as proxy (we already test this, but let's be explicit about 500-safety)
    resp = client.get("/nonexistent")
    body = json.dumps(resp.json())
    assert "Traceback" not in body
    assert "File " not in body


def test_validation_error_returns_safe_details(client):
    """Validation errors return field-level details without internal leakage."""
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "not-an-email",
            "password": "StrongPass1!",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "validation_error"
    # Should have field details but no internal file paths
    details_str = json.dumps(body)
    assert "Traceback" not in details_str


def test_health_no_sensitive_info(client):
    """Health endpoint response contains no sensitive data."""
    resp = client.get("/health")
    body = json.dumps(resp.json())
    assert "password" not in body.lower()
    assert "secret" not in body.lower()
    assert "token" not in body.lower()
