from datetime import date

import pytest
from google.genai import types
from pydantic import ValidationError

from routematrix.ai import SYSTEM_RULES, build_prompt
from routematrix.models import TripPlan, TripRequest


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
    request = TripRequest(
        destination="Paris, France",
        origin="Delhi, India",
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 12),
        travelers=2,
        budget_amount=150000,
        currency="INR",
        interests=["Food & cafes", "Art & museums"],
    )
    prompt = build_prompt(request)
    assert "Paris, France" in prompt
    assert "150000.00 INR" in prompt
    assert "exactly 3 day plans" in prompt
    assert SYSTEM_RULES not in prompt


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
