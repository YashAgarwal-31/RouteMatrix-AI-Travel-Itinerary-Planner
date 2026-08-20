from pathlib import Path

from routematrix.config import get_settings
from routematrix.database import Database


def test_invalid_numeric_environment_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("MAX_TRIP_DAYS", "not-a-number")
    monkeypatch.setenv("GEMINI_TIMEOUT_MS", "invalid")
    monkeypatch.setenv("GEMINI_MAX_ATTEMPTS", "invalid")

    settings = get_settings()

    assert settings.max_trip_days == 21
    assert settings.gemini_timeout_ms == 60_000
    assert settings.gemini_max_attempts == 3


def test_numeric_environment_is_bounded(monkeypatch):
    monkeypatch.setenv("MAX_TRIP_DAYS", "999")
    monkeypatch.setenv("GEMINI_TIMEOUT_MS", "1")
    monkeypatch.setenv("GEMINI_MAX_ATTEMPTS", "99")

    settings = get_settings()

    assert settings.max_trip_days == 30
    assert settings.gemini_timeout_ms == 5_000
    assert settings.gemini_max_attempts == 5


def test_database_normalizes_expanded_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    database = Database("~/nested/route.db")

    assert Path(database.path) == tmp_path / "nested" / "route.db"
    assert Path(database.path).exists()
