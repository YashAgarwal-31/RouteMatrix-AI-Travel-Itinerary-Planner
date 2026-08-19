from __future__ import annotations

import logging

import streamlit as st

from routematrix.ai import GeminiPlanner
from routematrix.config import get_settings
from routematrix.database import Database
from routematrix.models import TripPlan, TripRequest
from routematrix.ui import (
    hero,
    inject_styles,
    render_plan,
    render_saved_trip_list,
    travel_search_links,
    trip_request_form,
)


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="RouteMatrix · AI Travel Planner",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
settings = get_settings()
db = Database(settings.database_path)


def init_session() -> None:
    defaults = {
        "user": None,
        "active_request": None,
        "active_plan": None,
        "active_trip_id": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def logout() -> None:
    for key in ["user", "active_request", "active_plan", "active_trip_id"]:
        st.session_state[key] = None
    st.rerun()


def auth_screen() -> None:
    hero()
    st.subheader("Your trips, saved in one workspace")
    st.write("Create an account to save generated itineraries and reopen them later.")
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            user = db.authenticate(email, password)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("Invalid email or password.")

    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", help="Use at least 10 characters.", key="register_password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    user = db.create_user(name, email, password)
                    st.session_state.user = user
                    st.success("Account created.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def plan_new_trip() -> None:
    hero()
    if not settings.gemini_api_key:
        st.error("Gemini is not configured. Add GEMINI_API_KEY through environment variables or Streamlit secrets.")
        st.code('GEMINI_API_KEY="your-key"')
        return

    request = trip_request_form(settings.max_trip_days)
    if request is None:
        if st.session_state.active_plan and st.session_state.active_request:
            st.divider()
            render_plan(st.session_state.active_request, st.session_state.active_plan)
        return

    try:
        with st.spinner("Designing a practical itinerary…"):
            planner = GeminiPlanner(settings.gemini_api_key, settings.gemini_model)
            plan = planner.generate(request)
        trip_id = db.save_trip(
            st.session_state.user["id"],
            request.model_dump(mode="json"),
            plan.model_dump(mode="json"),
        )
        st.session_state.active_request = request
        st.session_state.active_plan = plan
        st.session_state.active_trip_id = trip_id
        st.success("Itinerary generated and saved to My Trips.")
        render_plan(request, plan)
        travel_search_links(request.destination, request.origin)
    except Exception:
        logger.exception("Itinerary generation failed")
        st.error("The itinerary could not be generated right now. Your trip was not saved. Please try again shortly.")


def saved_trips() -> None:
    hero()
    trips = db.list_trips(st.session_state.user["id"])
    trip_id = render_saved_trip_list(trips)
    if not trip_id:
        return
    trip = db.get_trip(st.session_state.user["id"], trip_id)
    if not trip:
        st.error("Trip not found.")
        return

    request = TripRequest.model_validate(trip["request"])
    plan = TripPlan.model_validate(trip["plan"])
    c1, c2 = st.columns([5, 1])
    c1.caption(f"Saved {trip['created_at'][:10]}")
    if c2.button("Delete trip", type="secondary", use_container_width=True):
        db.delete_trip(st.session_state.user["id"], trip_id)
        st.success("Trip deleted.")
        st.rerun()
    render_plan(request, plan)
    travel_search_links(request.destination, request.origin)


def account_page() -> None:
    hero()
    user = st.session_state.user
    st.subheader("Account")
    st.write(f"**Name:** {user['name']}")
    st.write(f"**Email:** {user['email']}")
    st.write(f"**Member since:** {user['created_at'][:10]}")
    st.info("RouteMatrix stores passwords as salted scrypt hashes. The raw password is never stored.")
    st.caption("For a large public SaaS deployment, move authentication and persistence to a managed database/identity service.")


init_session()

if not st.session_state.user:
    auth_screen()
    st.stop()

with st.sidebar:
    st.markdown("## 🧭 RouteMatrix")
    st.caption(f"Signed in as {st.session_state.user['name']}")
    page = st.radio("Workspace", ["Plan a trip", "My trips", "Account"])
    st.divider()
    st.caption(f"AI model: {settings.gemini_model}")
    if st.button("Sign out", use_container_width=True):
        logout()

if page == "Plan a trip":
    plan_new_trip()
elif page == "My trips":
    saved_trips()
else:
    account_page()
