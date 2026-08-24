import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import _validate_security_settings, app, settings


def test_application_defaults_to_fail_closed_production_mode(monkeypatch) -> None:
    assert Settings.model_fields["APP_ENV"].default == "production"
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "change-me-in-production")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "admin2026")

    with pytest.raises(RuntimeError, match="SECRET_KEY, ADMIN_PASSWORD"):
        _validate_security_settings()


def test_api_fallback_never_returns_the_react_index() -> None:
    client = TestClient(app)
    try:
        unknown = client.get("/api/v1/definitely-missing")
        wrong_method = client.get("/api/v1/plans/1/generate")
    finally:
        client.close()

    assert unknown.status_code == 404
    assert unknown.headers["content-type"].startswith("application/json")
    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "POST"


def test_security_headers_are_added_to_static_responses() -> None:
    client = TestClient(app)
    try:
        response = client.get("/")
    finally:
        client.close()

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
