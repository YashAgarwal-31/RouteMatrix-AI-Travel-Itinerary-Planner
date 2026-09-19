from datetime import date
from io import BytesIO

import pytest

from routematrix import live_data
from routematrix.live_data import LiveDataError, fetch_exchange_rate, fetch_weather_snapshot, weather_code_label


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_weather_snapshot_uses_geocoding_and_filters_trip_dates(monkeypatch):
    responses = iter(
        [
            b'{"results":[{"name":"Tokyo","country":"Japan","latitude":35.6762,"longitude":139.6503,"timezone":"Asia/Tokyo"}]}',
            b'{"current":{"time":"2026-09-20T12:00","temperature_2m":28.1,"apparent_temperature":30.0,"relative_humidity_2m":72,"weather_code":2,"wind_speed_10m":9.4},"daily":{"time":["2026-09-20","2026-09-21","2026-09-22"],"weather_code":[2,61,3],"temperature_2m_max":[30.0,27.0,26.0],"temperature_2m_min":[22.0,21.0,20.0],"precipitation_probability_max":[20,70,30]}}',
        ]
    )
    seen_urls = []

    def fake_urlopen(request, timeout):
        seen_urls.append(request.full_url)
        return FakeResponse(next(responses))

    monkeypatch.setattr(live_data, "urlopen", fake_urlopen)

    snapshot = fetch_weather_snapshot(
        "Tokyo, Japan",
        date(2026, 9, 21),
        date(2026, 9, 22),
    )

    assert snapshot.location.name == "Tokyo"
    assert snapshot.current.temperature_c == 28.1
    assert snapshot.current.humidity_percent == 72
    assert [item.date for item in snapshot.forecast] == ["2026-09-21", "2026-09-22"]
    assert snapshot.forecast_available_for_trip is True
    assert "geocoding-api.open-meteo.com" in seen_urls[0]
    assert "api.open-meteo.com" in seen_urls[1]


def test_weather_snapshot_marks_future_trip_when_forecast_not_available(monkeypatch):
    responses = iter(
        [
            b'{"results":[{"name":"Paris","country":"France","latitude":48.8566,"longitude":2.3522,"timezone":"Europe/Paris"}]}',
            b'{"current":{"time":"2026-09-20T12:00","temperature_2m":19.0,"apparent_temperature":18.0,"relative_humidity_2m":60,"weather_code":1,"wind_speed_10m":8.0},"daily":{"time":["2026-09-20","2026-09-21"],"weather_code":[1,2],"temperature_2m_max":[21.0,22.0],"temperature_2m_min":[12.0,13.0],"precipitation_probability_max":[10,20]}}',
        ]
    )

    monkeypatch.setattr(
        live_data,
        "urlopen",
        lambda request, timeout: FakeResponse(next(responses)),
    )

    snapshot = fetch_weather_snapshot(
        "Paris, France",
        date(2026, 11, 1),
        date(2026, 11, 3),
    )

    assert snapshot.forecast == []
    assert snapshot.forecast_available_for_trip is False


def test_exchange_rate_snapshot_parses_live_pair(monkeypatch):
    payload = b'{"date":"2026-09-19","base":"USD","quote":"INR","rate":95.88}'
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(payload)

    monkeypatch.setattr(live_data, "urlopen", fake_urlopen)

    snapshot = fetch_exchange_rate("usd", "inr")

    assert snapshot.base == "USD"
    assert snapshot.quote == "INR"
    assert snapshot.rate == 95.88
    assert snapshot.rate_date == "2026-09-19"
    assert captured["url"].endswith("/usd/inr")


def test_exchange_rate_same_currency_avoids_network(monkeypatch):
    monkeypatch.setattr(
        live_data,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("Network should not be called"),
    )
    snapshot = fetch_exchange_rate("INR", "INR")
    assert snapshot.rate == 1.0


def test_live_data_failure_is_safe_after_retries(monkeypatch):
    calls = {"count": 0}

    def fail(*_args, **_kwargs):
        calls["count"] += 1
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(live_data, "urlopen", fail)
    monkeypatch.setattr(live_data.time, "sleep", lambda _seconds: None)

    with pytest.raises(LiveDataError, match="temporarily unavailable"):
        fetch_exchange_rate("USD", "EUR")

    assert calls["count"] == 3


def test_weather_code_has_human_label():
    assert weather_code_label(0) == "Clear sky"
    assert weather_code_label(95) == "Thunderstorm"
