from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rate"
USER_AGENT = "RouteMatrix/1.0 (+https://github.com/YashAgarwal-31/RouteMatrix-AI-Travel-Itinerary-Planner)"


class LiveDataError(RuntimeError):
    """Raised when a live external-data provider cannot return usable data."""


@dataclass(frozen=True)
class GeoLocation:
    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str = ""


@dataclass(frozen=True)
class CurrentWeather:
    temperature_c: float
    apparent_temperature_c: float
    humidity_percent: int
    wind_speed_kmh: float
    weather_code: int
    observed_at: str


@dataclass(frozen=True)
class ForecastDay:
    date: str
    temperature_max_c: float
    temperature_min_c: float
    precipitation_probability_percent: int
    weather_code: int


@dataclass(frozen=True)
class WeatherSnapshot:
    location: GeoLocation
    current: CurrentWeather
    forecast: list[ForecastDay]
    forecast_available_for_trip: bool


@dataclass(frozen=True)
class ExchangeRateSnapshot:
    base: str
    quote: str
    rate: float
    rate_date: str


def _get_json(url: str, *, timeout_seconds: float = 8.0, attempts: int = 3) -> dict[str, Any]:
    timeout_seconds = max(2.0, min(float(timeout_seconds), 20.0))
    attempts = max(1, min(int(attempts), 4))
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                payload = response.read()
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                raise LiveDataError("Live provider returned an unexpected response shape.")
            return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.35 * (2**attempt))

    raise LiveDataError("Live provider is temporarily unavailable. Please try again shortly.") from last_error


def geocode_destination(destination: str) -> GeoLocation:
    destination = " ".join(destination.strip().split())
    if len(destination) < 2:
        raise LiveDataError("Destination is too short to look up live data.")

    query = urlencode(
        {
            "name": destination,
            "count": 1,
            "language": "en",
            "format": "json",
        }
    )
    data = _get_json(f"{OPEN_METEO_GEOCODING_URL}?{query}")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise LiveDataError(f'No live-data location match was found for "{destination}".')

    match = results[0]
    if not isinstance(match, dict):
        raise LiveDataError("Live geocoding returned an invalid location.")

    try:
        return GeoLocation(
            name=str(match["name"]),
            country=str(match.get("country") or ""),
            latitude=float(match["latitude"]),
            longitude=float(match["longitude"]),
            timezone=str(match.get("timezone") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveDataError("Live geocoding returned incomplete coordinates.") from exc


def weather_code_label(code: int) -> str:
    labels = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return labels.get(int(code), f"Weather code {code}")


def fetch_weather_snapshot(
    destination: str,
    trip_start: date,
    trip_end: date,
    *,
    forecast_days: int = 16,
) -> WeatherSnapshot:
    location = geocode_destination(destination)
    forecast_days = max(1, min(int(forecast_days), 16))
    params = urlencode(
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "weather_code",
                    "wind_speed_10m",
                ]
            ),
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                ]
            ),
            "timezone": "auto",
            "forecast_days": forecast_days,
        }
    )
    data = _get_json(f"{OPEN_METEO_FORECAST_URL}?{params}")

    current_data = data.get("current")
    daily_data = data.get("daily")
    if not isinstance(current_data, dict) or not isinstance(daily_data, dict):
        raise LiveDataError("Weather provider returned incomplete forecast data.")

    try:
        current = CurrentWeather(
            temperature_c=float(current_data["temperature_2m"]),
            apparent_temperature_c=float(current_data["apparent_temperature"]),
            humidity_percent=int(round(float(current_data["relative_humidity_2m"]))),
            wind_speed_kmh=float(current_data["wind_speed_10m"]),
            weather_code=int(current_data["weather_code"]),
            observed_at=str(current_data["time"]),
        )

        dates = list(daily_data["time"])
        max_temps = list(daily_data["temperature_2m_max"])
        min_temps = list(daily_data["temperature_2m_min"])
        precipitation = list(daily_data["precipitation_probability_max"])
        codes = list(daily_data["weather_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveDataError("Weather provider returned malformed values.") from exc

    lengths = {len(dates), len(max_temps), len(min_temps), len(precipitation), len(codes)}
    if len(lengths) != 1:
        raise LiveDataError("Weather provider returned inconsistent daily forecast arrays.")

    trip_forecast: list[ForecastDay] = []
    for day_text, high, low, rain, code in zip(
        dates,
        max_temps,
        min_temps,
        precipitation,
        codes,
        strict=True,
    ):
        try:
            parsed_day = date.fromisoformat(str(day_text))
            if trip_start <= parsed_day <= trip_end:
                trip_forecast.append(
                    ForecastDay(
                        date=parsed_day.isoformat(),
                        temperature_max_c=float(high),
                        temperature_min_c=float(low),
                        precipitation_probability_percent=int(round(float(rain or 0))),
                        weather_code=int(code),
                    )
                )
        except (TypeError, ValueError) as exc:
            raise LiveDataError("Weather provider returned an invalid daily forecast row.") from exc

    trip_days = (trip_end - trip_start).days + 1
    return WeatherSnapshot(
        location=location,
        current=current,
        forecast=trip_forecast,
        forecast_available_for_trip=len(trip_forecast) == trip_days,
    )


def fetch_exchange_rate(base: str, quote_currency: str) -> ExchangeRateSnapshot:
    base = base.strip().upper()
    quote_currency = quote_currency.strip().upper()
    if len(base) != 3 or len(quote_currency) != 3:
        raise LiveDataError("Currency codes must use three ISO letters.")
    if base == quote_currency:
        return ExchangeRateSnapshot(base=base, quote=quote_currency, rate=1.0, rate_date=date.today().isoformat())

    url = f"{FRANKFURTER_RATE_URL}/{quote(base.lower())}/{quote(quote_currency.lower())}"
    data = _get_json(url)
    try:
        returned_base = str(data["base"]).upper()
        returned_quote = str(data["quote"]).upper()
        rate = float(data["rate"])
        rate_date = str(data["date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveDataError("Exchange-rate provider returned malformed data.") from exc

    if returned_base != base or returned_quote != quote_currency or rate <= 0:
        raise LiveDataError("Exchange-rate provider returned an unexpected currency pair.")

    return ExchangeRateSnapshot(base=base, quote=quote_currency, rate=rate, rate_date=rate_date)
