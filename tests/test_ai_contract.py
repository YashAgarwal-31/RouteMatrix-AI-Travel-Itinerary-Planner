from datetime import date

import pytest
from google.genai import types
from pydantic import ValidationError

from routematrix.ai import SYSTEM_RULES, build_prompt, build_refinement_prompt
from routematrix.models import DayPlan, TripPlan, TripRequest


def _request() -> TripRequest:
    return TripRequest(
        destination="Paris, France",
        origin="Delhi, India",
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 12),
        travelers=2,
        budget_amount=150000,
        currency="INR",
        interests=["Food & cafes", "Art & museums"],
    )


def test_gemini_structured_output_config_accepts_trip_plan_schema():
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_RULES,
        response_mime_type="application/json",
        response_schema=TripPlan,
        max_output_tokens=16000,
        temperature=0.35,
    )
    assert config.response_schema is not None
    assert config.system_instruction


def test_prompt_contains_trip_constraints_without_system_rules():
    prompt = build_prompt(_request())
    assert "Paris, France" in prompt
    assert "150000.00 INR" in prompt
    assert "exactly 3 day plans" in prompt
    assert SYSTEM_RULES not in prompt


def test_refinement_prompt_preserves_constraints_and_change_request():
    request = _request()
    current = TripPlan(
        destination="Paris, France",
        trip_title="Paris Explorer",
        overview="A balanced trip.",
        currency="INR",
        estimated_total_cost=140000,
        budget_fit="within_budget",
        days=[
            DayPlan(day=1, date="2026-09-10", theme="Arrival", summary="Explore central Paris."),
            DayPlan(day=2, date="2026-09-11", theme="Museums", summary="Visit major museums."),
            DayPlan(day=3, date="2026-09-12", theme="Neighborhoods", summary="Explore local neighborhoods."),
        ],
    )
    prompt = build_refinement_prompt(request, current, "Make Day 2 more relaxed")
    assert "Make Day 2 more relaxed" in prompt
    assert "150000.00 INR" in prompt
    assert "Paris Explorer" in prompt
    assert "exactly 3 days" in prompt


def test_trip_request_rejects_reversed_dates():
    with pytest.raises(ValidationError):
        TripRequest(
            destination="Rome, Italy",
            start_date=date(2026, 9, 12),
            end_date=date(2026, 9, 10),
            travelers=1,
            budget_amount=50000,
            currency="INR",
        )
