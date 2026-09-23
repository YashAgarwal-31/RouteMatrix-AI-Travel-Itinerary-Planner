from __future__ import annotations

from datetime import date

from routematrix.ai import GeminiPlanner
from routematrix.config import get_settings
from routematrix.models import TripRequest


def main() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for the live Gemini smoke test.")

    today = date.today()
    request = TripRequest(
        destination="New Delhi, India",
        origin="Noida, India",
        start_date=today,
        end_date=today,
        travelers=1,
        budget_amount=5000,
        currency="INR",
        pace="Balanced",
        interests=["Culture & heritage", "Food & cafes"],
        accommodation="Budget",
        additional_notes="Create a compact one-day portfolio smoke-test itinerary.",
    )
    planner = GeminiPlanner(
        settings.gemini_api_key,
        settings.gemini_model,
        timeout_ms=settings.gemini_timeout_ms,
        max_attempts=settings.gemini_max_attempts,
    )
    plan = planner.generate(request)

    if len(plan.days) != 1 or plan.days[0].date != today.isoformat():
        raise RuntimeError("Gemini smoke test returned an invalid itinerary contract.")

    print(
        "GEMINI_API_SMOKE_OK "
        f"model={planner.last_model_used} "
        f"destination={plan.destination} "
        f"activities={len(plan.days[0].activities)}"
    )


if __name__ == "__main__":
    main()

