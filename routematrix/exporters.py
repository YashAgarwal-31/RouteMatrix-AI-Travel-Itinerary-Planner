from __future__ import annotations

import json
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
