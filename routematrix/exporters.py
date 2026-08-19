from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from .models import TripPlan, TripRequest


def map_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def plan_to_json(plan: TripPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def plan_to_markdown(request: TripRequest, plan: TripPlan) -> str:
    lines = [
        f"# {plan.trip_title}",
        "",
        f"**Destination:** {plan.destination}",
        f"**Dates:** {request.start_date.isoformat()} → {request.end_date.isoformat()}",
        f"**Travelers:** {request.travelers}",
        f"**Estimated total:** {plan.estimated_total_cost:,.0f} {plan.currency}",
        f"**Budget fit:** {plan.budget_fit.replace('_', ' ').title()}",
        "",
        plan.overview,
        "",
        "## Budget",
    ]
    for item in plan.budget_breakdown:
        lines.append(f"- **{item.category}:** {item.amount:,.0f} {plan.currency} — {item.note}")

    for day in plan.days:
        lines.extend(["", f"## Day {day.day} — {day.theme}", day.summary, ""])
        for activity in day.activities:
            lines.append(
                f"- **{activity.time} · {activity.name}** ({activity.category}) — {activity.description} "
                f"Estimated {activity.estimated_cost:,.0f} {plan.currency}."
            )
            if activity.map_query:
                lines.append(f"  - Map: {map_search_url(activity.map_query)}")
            for tip in activity.tips:
                lines.append(f"  - Tip: {tip}")
        for note in day.meal_notes:
            lines.append(f"- Meal note: {note}")

    sections = [
        ("Stay recommendations", [f"{x.name}: {x.reason}" for x in plan.stay_recommendations]),
        ("Food recommendations", [f"{x.name}: {x.reason}" for x in plan.food_recommendations]),
        ("Local transport", plan.local_transport),
        ("Packing list", plan.packing_list),
        ("Local tips", plan.local_tips),
        ("Safety notes", plan.safety_notes),
        ("Sustainability", plan.sustainability_tips),
        ("Assumptions", plan.assumptions),
    ]
    for title, items in sections:
        if items:
            lines.extend(["", f"## {title}"])
            lines.extend([f"- {item}" for item in items])

    lines.extend(["", f"> {plan.live_data_disclaimer}"])
    return "\n".join(lines)


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _activity_datetime(day_date: str, activity_time: str) -> datetime:
    cleaned = activity_time.strip().split("-")[0].strip()
    for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            parsed_time = datetime.strptime(cleaned, fmt).time()
            return datetime.combine(datetime.fromisoformat(day_date).date(), parsed_time)
        except ValueError:
            continue
    return datetime.combine(datetime.fromisoformat(day_date).date(), datetime.min.time()).replace(hour=9)


def plan_to_ics(plan: TripPlan) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RouteMatrix//AI Travel Itinerary//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_escape(plan.trip_title)}",
    ]
    event_number = 0
    for day in plan.days:
        for activity in day.activities:
            event_number += 1
            start = _activity_datetime(day.date, activity.time)
            end = start + timedelta(hours=1)
            description = activity.description
            if activity.tips:
                description += " Tips: " + " | ".join(activity.tips)
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:routematrix-{day.day}-{event_number}@local",
                    f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
                    f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                    f"SUMMARY:{_ics_escape(activity.name)}",
                    f"DESCRIPTION:{_ics_escape(description)}",
                    f"LOCATION:{_ics_escape(activity.map_query or activity.neighborhood or plan.destination)}",
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
