from datetime import date

from routematrix.exporters import map_search_url, plan_to_ics, plan_to_markdown
from routematrix.models import Activity, BudgetItem, DayPlan, TripPlan, TripRequest


def test_trip_request_days_and_export():
    request = TripRequest(
        destination="Kyoto, Japan",
        origin="Delhi, India",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        travelers=2,
        budget_amount=100000,
        currency="inr",
    )
    assert request.trip_days == 2
    assert request.currency == "INR"

    plan = TripPlan(
        destination="Kyoto, Japan",
        trip_title="Kyoto Highlights",
        overview="A balanced two-day plan.",
        currency="INR",
        estimated_total_cost=80000,
        budget_fit="within_budget",
        budget_breakdown=[BudgetItem(category="Food", amount=10000, note="Estimate")],
        days=[
            DayPlan(
                day=1,
                date="2026-10-01",
                theme="Historic Kyoto",
                summary="Temples and local food.",
                activities=[
                    Activity(
                        time="09:00",
                        name="Fushimi Inari",
                        description="Explore the shrine early.",
                        estimated_cost=0,
                        map_query="Fushimi Inari Kyoto",
                    )
                ],
            )
        ],
    )
    markdown = plan_to_markdown(request, plan)
    assert "Kyoto Highlights" in markdown
    assert "Fushimi Inari" in markdown
    assert "google.com/maps" in markdown

    calendar = plan_to_ics(plan)
    assert "BEGIN:VCALENDAR" in calendar
    assert "SUMMARY:Fushimi Inari" in calendar
    assert "DTSTART:20261001T090000" in calendar
    assert calendar.endswith("END:VCALENDAR\r\n")


def test_map_url_encodes_query():
    url = map_search_url("India Gate New Delhi")
    assert "India+Gate+New+Delhi" in url
