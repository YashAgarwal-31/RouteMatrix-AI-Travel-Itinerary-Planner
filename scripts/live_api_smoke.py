from __future__ import annotations

from datetime import date

from routematrix.live_data import fetch_exchange_rate, fetch_weather_snapshot, weather_code_label


def main() -> None:
    today = date.today()
    weather = fetch_weather_snapshot("Tokyo, Japan", today, today)
    if not (-90 <= weather.location.latitude <= 90 and -180 <= weather.location.longitude <= 180):
        raise RuntimeError("Open-Meteo returned invalid coordinates.")
    if not (-100 <= weather.current.temperature_c <= 70):
        raise RuntimeError("Open-Meteo returned an implausible temperature.")

    fx = fetch_exchange_rate("USD", "INR")
    if fx.rate <= 0:
        raise RuntimeError("Frankfurter returned a non-positive exchange rate.")

    print(
        "LIVE_API_SMOKE_OK "
        f"weather={weather.current.temperature_c:.1f}C/"
        f"{weather_code_label(weather.current.weather_code)} "
        f"location={weather.location.name},{weather.location.country} "
        f"usd_inr={fx.rate:.4f} rate_date={fx.rate_date}"
    )


if __name__ == "__main__":
    main()
