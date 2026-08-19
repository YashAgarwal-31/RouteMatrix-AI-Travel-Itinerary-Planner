from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=120)
    origin: str = Field(default="", max_length=120)
    start_date: date
    end_date: date
    travelers: int = Field(ge=1, le=12)
    budget_amount: float = Field(gt=0, le=10_000_000)
    currency: str = Field(default="INR", min_length=3, max_length=6)
    pace: Literal["Relaxed", "Balanced", "Fast-paced"] = "Balanced"
    interests: list[str] = Field(default_factory=list, max_length=12)
    accommodation: str = Field(default="Mid-range", max_length=80)
    food_preferences: str = Field(default="", max_length=500)
    transport_preferences: str = Field(default="", max_length=500)
    accessibility_needs: str = Field(default="", max_length=500)
    additional_notes: str = Field(default="", max_length=1000)

    @field_validator("destination", "origin", "food_preferences", "transport_preferences", "accessibility_needs", "additional_notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def trip_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class Activity(BaseModel):
    time: str = Field(description="Approximate local time, e.g. 09:00")
    name: str
    category: str = "Experience"
    neighborhood: str = ""
    description: str
    estimated_cost: float = Field(default=0, ge=0)
    booking_required: bool = False
    map_query: str = Field(default="", description="Searchable place name with destination")
    tips: list[str] = Field(default_factory=list)


class DayPlan(BaseModel):
    day: int = Field(ge=1)
    date: str
    theme: str
    summary: str
    activities: list[Activity] = Field(default_factory=list)
    meal_notes: list[str] = Field(default_factory=list)
    daily_estimated_cost: float = Field(default=0, ge=0)


class BudgetItem(BaseModel):
    category: str
    amount: float = Field(ge=0)
    note: str = ""


class Recommendation(BaseModel):
    name: str
    reason: str
    price_level: str = ""
    area: str = ""


class TripPlan(BaseModel):
    destination: str
    trip_title: str
    overview: str
    currency: str
    estimated_total_cost: float = Field(ge=0)
    budget_fit: Literal["within_budget", "near_budget", "over_budget", "unknown"] = "unknown"
    budget_note: str = ""
    budget_breakdown: list[BudgetItem] = Field(default_factory=list)
    days: list[DayPlan] = Field(default_factory=list)
    stay_recommendations: list[Recommendation] = Field(default_factory=list)
    food_recommendations: list[Recommendation] = Field(default_factory=list)
    local_transport: list[str] = Field(default_factory=list)
    packing_list: list[str] = Field(default_factory=list)
    local_tips: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    sustainability_tips: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    live_data_disclaimer: str = (
        "Prices, opening hours, availability, visas, weather, and local conditions can change. "
        "Verify live information before booking or travel."
    )
