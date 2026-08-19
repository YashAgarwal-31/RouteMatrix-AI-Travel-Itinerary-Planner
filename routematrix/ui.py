from __future__ import annotations

from datetime import date
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from .exporters import map_search_url, plan_to_ics, plan_to_json, plan_to_markdown
from .models import TripPlan, TripRequest


INTEREST_OPTIONS = [
    "Culture & heritage",
    "Food & cafes",
    "Nature",
    "Adventure",
    "Beaches",
    "Nightlife",
    "Shopping",
    "Photography",
    "Art & museums",
    "Wellness",
    "Family activities",
    "Hidden gems",
]

CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "JPY", "SGD", "AUD"]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 1.7rem; padding-bottom: 3rem;}
        .rm-hero {padding: 1.4rem 1.6rem; border: 1px solid rgba(128,128,128,.25); border-radius: 20px; margin-bottom: 1rem;}
        .rm-kicker {font-size:.82rem; text-transform:uppercase; letter-spacing:.12em; opacity:.7; font-weight:700;}
        .rm-title {font-size:2.35rem; font-weight:800; line-height:1.08; margin:.35rem 0;}
        .rm-subtitle {font-size:1rem; opacity:.78; max-width:850px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero() -> None:
    st.markdown(
        """
        <div class="rm-hero">
          <div class="rm-kicker">AI travel planning workspace</div>
          <div class="rm-title">RouteMatrix</div>
          <div class="rm-subtitle">Build budget-aware, day-by-day travel plans with structured AI recommendations, saved trips, exports, and practical planning guidance.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def trip_request_form(max_trip_days: int) -> TripRequest | None:
    today = date.today()
    with st.form("trip_planner_form"):
        st.subheader("Plan a new trip")
        st.caption("RouteMatrix uses your constraints to generate a structured itinerary. Live prices and availability still need verification.")

        c1, c2 = st.columns(2)
        destination = c1.text_input("Destination *", placeholder="Tokyo, Japan")
        origin = c2.text_input("Starting city", placeholder="New Delhi, India")

        c1, c2, c3 = st.columns(3)
        start_date = c1.date_input("Start date", value=today)
        end_date = c2.date_input("End date", value=today)
        travelers = c3.number_input("Travelers", min_value=1, max_value=12, value=1, step=1)

        c1, c2, c3 = st.columns(3)
        budget = c1.number_input("Total budget *", min_value=1.0, value=50000.0, step=1000.0)
        currency = c2.selectbox("Currency", CURRENCIES, index=0)
        pace = c3.selectbox("Travel pace", ["Relaxed", "Balanced", "Fast-paced"], index=1)

        interests = st.multiselect("Interests", INTEREST_OPTIONS, default=["Culture & heritage", "Food & cafes"])

        c1, c2 = st.columns(2)
        accommodation = c1.selectbox("Accommodation", ["Budget", "Mid-range", "Boutique", "Luxury", "Hostel", "Apartment / homestay"], index=1)
        food_preferences = c2.text_input("Food preferences / dietary needs", placeholder="Vegetarian, halal, local food, no seafood")

        transport_preferences = st.text_input("Transport preferences", placeholder="Public transport, walking, avoid long taxi rides")
        accessibility_needs = st.text_input("Accessibility needs", placeholder="Wheelchair access, low walking, senior-friendly")
        additional_notes = st.text_area("Additional preferences", placeholder="Must-see places, celebrations, work calls, avoid early mornings…", max_chars=1000)

        submitted = st.form_submit_button("Generate AI itinerary", type="primary", use_container_width=True)

    if not submitted:
        return None

    if not destination.strip():
        st.error("Destination is required.")
        return None
    if end_date < start_date:
        st.error("End date must be on or after the start date.")
        return None
    trip_days = (end_date - start_date).days + 1
    if trip_days > max_trip_days:
        st.error(f"Please keep a single generated trip within {max_trip_days} days.")
        return None

    return TripRequest(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        travelers=int(travelers),
        budget_amount=float(budget),
        currency=currency,
        pace=pace,
        interests=interests,
        accommodation=accommodation,
        food_preferences=food_preferences,
        transport_preferences=transport_preferences,
        accessibility_needs=accessibility_needs,
        additional_notes=additional_notes,
    )


def _budget_chart(plan: TripPlan) -> None:
    if not plan.budget_breakdown:
        return
    df = pd.DataFrame([{"Category": x.category, "Amount": x.amount} for x in plan.budget_breakdown])
    st.bar_chart(df.set_index("Category"), use_container_width=True)


def render_plan(request: TripRequest, plan: TripPlan) -> None:
    st.header(plan.trip_title)
    st.write(plan.overview)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Days", request.trip_days)
    m2.metric("Travelers", request.travelers)
    m3.metric("Estimated total", f"{plan.estimated_total_cost:,.0f} {plan.currency}")
    m4.metric("Budget fit", plan.budget_fit.replace("_", " ").title())

    if plan.budget_note:
        st.info(plan.budget_note)

    tabs = st.tabs(["Day-by-day", "Budget", "Stay & food", "Travel notes", "Export"])

    with tabs[0]:
        for day in plan.days:
            with st.expander(f"Day {day.day} · {day.date} · {day.theme}", expanded=day.day == 1):
                st.write(day.summary)
                for activity in day.activities:
                    st.markdown(f"**{activity.time} — {activity.name}** · {activity.category}")
                    if activity.neighborhood:
                        st.caption(activity.neighborhood)
                    st.write(activity.description)
                    c1, c2, c3 = st.columns([1, 1, 2])
                    c1.write(f"💰 {activity.estimated_cost:,.0f} {plan.currency}")
                    c2.write("🎟️ Booking suggested" if activity.booking_required else "✅ Flexible")
                    if activity.map_query:
                        c3.markdown(f"[Open map search]({map_search_url(activity.map_query)})")
                    if activity.tips:
                        st.caption("Tips: " + " · ".join(activity.tips))
                    st.divider()
                if day.meal_notes:
                    st.markdown("**Meal notes**")
                    for note in day.meal_notes:
                        st.write(f"- {note}")
                st.caption(f"Estimated day cost: {day.daily_estimated_cost:,.0f} {plan.currency}")

    with tabs[1]:
        _budget_chart(plan)
        for item in plan.budget_breakdown:
            st.write(f"**{item.category}:** {item.amount:,.0f} {plan.currency} — {item.note}")
        st.caption("Budget values are planning estimates, not live quotes.")

    with tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Stay recommendations")
            for item in plan.stay_recommendations:
                st.markdown(f"**{item.name}** {f'· {item.price_level}' if item.price_level else ''}")
                st.write(item.reason)
                if item.area:
                    st.caption(item.area)
        with c2:
            st.subheader("Food recommendations")
            for item in plan.food_recommendations:
                st.markdown(f"**{item.name}** {f'· {item.price_level}' if item.price_level else ''}")
                st.write(item.reason)
                if item.area:
                    st.caption(item.area)

    with tabs[3]:
        sections = [
            ("Local transport", plan.local_transport),
            ("Packing list", plan.packing_list),
            ("Local tips", plan.local_tips),
            ("Safety notes", plan.safety_notes),
            ("Sustainability", plan.sustainability_tips),
            ("Assumptions", plan.assumptions),
        ]
        for title, items in sections:
            if items:
                st.subheader(title)
                for item in items:
                    st.write(f"- {item}")
        st.warning(plan.live_data_disclaimer)

    with tabs[4]:
        markdown = plan_to_markdown(request, plan)
        json_text = plan_to_json(plan)
        calendar = plan_to_ics(plan)
        c1, c2, c3 = st.columns(3)
        c1.download_button(
            "Download Markdown",
            data=markdown,
            file_name="routematrix-itinerary.md",
            mime="text/markdown",
            use_container_width=True,
        )
        c2.download_button(
            "Download JSON",
            data=json_text,
            file_name="routematrix-itinerary.json",
            mime="application/json",
            use_container_width=True,
        )
        c3.download_button(
            "Add to calendar (.ics)",
            data=calendar,
            file_name="routematrix-itinerary.ics",
            mime="text/calendar",
            use_container_width=True,
        )


def render_saved_trip_list(trips: list[dict]) -> str | None:
    if not trips:
        st.info("No saved trips yet. Generate your first itinerary from the planner.")
        return None

    st.subheader("Saved trips")
    options = {f"{t['title']} · {t['start_date']} → {t['end_date']}": t["id"] for t in trips}
    selected_label = st.selectbox("Choose a trip", list(options.keys()))
    return options[selected_label]


def travel_search_links(destination: str, origin: str = "") -> None:
    st.subheader("Live search shortcuts")
    st.caption("These links open external providers so you can verify current prices and availability.")
    encoded_destination = quote_plus(destination)
    cols = st.columns(3)
    cols[0].link_button("Google Maps", f"https://www.google.com/maps/search/?api=1&query={encoded_destination}", use_container_width=True)
    cols[1].link_button("Google Hotels", f"https://www.google.com/travel/hotels/{encoded_destination}", use_container_width=True)
    if origin:
        cols[2].link_button("Google Flights", f"https://www.google.com/travel/flights?hl=en&q={quote_plus(origin + ' to ' + destination)}", use_container_width=True)
    else:
        cols[2].link_button("Google Travel", f"https://www.google.com/travel/search?q={encoded_destination}", use_container_width=True)
