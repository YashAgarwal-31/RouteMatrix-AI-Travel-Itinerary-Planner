from __future__ import annotations

import logging
from datetime import date

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


def create_planner() -> GeminiPlanner:
    return GeminiPlanner(
        settings.gemini_api_key,
        settings.gemini_model,
        timeout_ms=settings.gemini_timeout_ms,
        max_attempts=settings.gemini_max_attempts,
    )


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
            planner = create_planner()
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


def render_ai_refinement(user_id: str, trip_id: str, request: TripRequest, plan: TripPlan) -> None:
    with st.expander("✨ Refine this itinerary with AI"):
        st.caption("Ask RouteMatrix to slow the pace, reduce cost, replace an activity, add dietary/accessibility constraints, or reshape the trip. Every accepted update is versioned.")
        with st.form(f"refine_trip_{trip_id}"):
            instruction = st.text_area(
                "What should change?",
                placeholder="Make Day 2 more relaxed, replace nightlife with family-friendly activities, and keep the total under 80,000 INR.",
                max_chars=1000,
            )
            submitted = st.form_submit_button("Refine with Gemini", type="primary", use_container_width=True)
        if submitted:
            if not settings.gemini_api_key:
                st.error("Gemini is not configured for refinement.")
                return
            if len(instruction.strip()) < 3:
                st.error("Describe the change you want to make.")
                return
            try:
                with st.spinner("Reworking the itinerary while preserving your trip constraints…"):
                    updated = create_planner().refine(request, plan, instruction)
                    revision = db.update_trip_plan(
                        user_id,
                        trip_id,
                        updated.model_dump(mode="json"),
                        instruction,
                    )
                st.success(f"Itinerary updated as revision {revision}.")
                st.rerun()
            except Exception:
                logger.exception("Itinerary refinement failed")
                st.error("RouteMatrix could not apply that refinement. The current saved itinerary was left unchanged.")


def render_revision_history(user_id: str, trip_id: str) -> None:
    revisions = db.list_trip_revisions(user_id, trip_id)
    with st.expander(f"🕘 Itinerary version history ({len(revisions)})"):
        if not revisions:
            st.info("No itinerary revisions are available.")
            return
        for revision in revisions:
            st.caption(
                f"Revision {revision['revision_number']} · {revision['created_at'][:19].replace('T', ' ')} UTC · {revision['instruction']}"
            )
        if len(revisions) > 1:
            options = {
                f"Revision {item['revision_number']} — {item['instruction'][:70]}": item["id"]
                for item in revisions[1:]
            }
            selected = st.selectbox("Restore an earlier version", list(options.keys()), key=f"revision_select_{trip_id}")
            if st.button("Restore selected version", key=f"restore_revision_{trip_id}", use_container_width=True):
                restored_number = db.restore_trip_revision(user_id, trip_id, options[selected])
                st.success(f"Earlier itinerary restored as new revision {restored_number}.")
                st.rerun()


def render_expense_tracker(user_id: str, trip_id: str, request: TripRequest, plan: TripPlan) -> None:
    st.subheader("💳 Trip expense tracker")
    expenses = db.list_expenses(user_id, trip_id)
    spent = sum(float(item["amount"]) for item in expenses if item["currency"] == plan.currency)
    remaining = request.budget_amount - spent

    c1, c2, c3 = st.columns(3)
    c1.metric("Trip budget", f"{request.budget_amount:,.0f} {request.currency}")
    c2.metric("Recorded spend", f"{spent:,.0f} {plan.currency}")
    c3.metric("Budget remaining", f"{remaining:,.0f} {plan.currency}")

    with st.form(f"expense_form_{trip_id}"):
        c1, c2, c3 = st.columns([1, 1, 1])
        expense_date = c1.date_input(
            "Date",
            value=max(request.start_date, min(date.today(), request.end_date)),
            min_value=request.start_date,
            max_value=request.end_date,
            key=f"expense_date_{trip_id}",
        )
        category = c2.selectbox(
            "Category",
            ["Accommodation", "Food", "Transport", "Activities", "Shopping", "Flights", "Other"],
            key=f"expense_category_{trip_id}",
        )
        amount = c3.number_input("Amount", min_value=0.0, step=100.0, key=f"expense_amount_{trip_id}")
        description = st.text_input("Description", placeholder="Metro pass, museum ticket, dinner…", key=f"expense_desc_{trip_id}")
        submitted = st.form_submit_button("Add expense", use_container_width=True)
    if submitted:
        try:
            db.add_expense(
                user_id,
                trip_id,
                expense_date.isoformat(),
                category,
                description,
                float(amount),
                plan.currency,
            )
            st.success("Expense recorded.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    if expenses:
        display_rows = [
            {
                "Date": item["expense_date"],
                "Category": item["category"],
                "Description": item["description"],
                "Amount": f"{item['amount']:,.2f} {item['currency']}",
            }
            for item in expenses
        ]
        st.dataframe(display_rows, hide_index=True, use_container_width=True)
        expense_options = {
            f"{item['expense_date']} · {item['category']} · {item['amount']:,.0f} {item['currency']} · {item['description'][:40]}": item["id"]
            for item in expenses
        }
        selected_expense = st.selectbox("Remove an expense", list(expense_options.keys()), key=f"expense_delete_select_{trip_id}")
        confirm_expense_delete = st.checkbox(
            "Confirm expense deletion",
            key=f"expense_delete_confirm_{trip_id}",
        )
        if st.button(
            "Delete selected expense",
            key=f"expense_delete_{trip_id}",
            disabled=not confirm_expense_delete,
        ):
            db.delete_expense(user_id, trip_id, expense_options[selected_expense])
            st.rerun()
    else:
        st.caption("No actual expenses recorded yet.")


def saved_trips() -> None:
    hero()
    user_id = st.session_state.user["id"]
    trips = db.list_trips(user_id)
    trip_id = render_saved_trip_list(trips)
    if not trip_id:
        return
    trip = db.get_trip(user_id, trip_id)
    if not trip:
        st.error("Trip not found.")
        return

    request = TripRequest.model_validate(trip["request"])
    plan = TripPlan.model_validate(trip["plan"])
    st.caption(f"Saved {trip['created_at'][:10]} · Last updated {trip['updated_at'][:19].replace('T', ' ')} UTC")
    with st.expander("Danger zone"):
        confirm_trip_delete = st.checkbox(
            f'Permanently delete "{trip["title"]}" and all its revisions and expenses',
            key=f"trip_delete_confirm_{trip_id}",
        )
        if st.button(
            "Delete trip permanently",
            type="secondary",
            key=f"trip_delete_{trip_id}",
            disabled=not confirm_trip_delete,
        ):
            db.delete_trip(user_id, trip_id)
            st.success("Trip deleted.")
            st.rerun()

    render_plan(request, plan)
    travel_search_links(request.destination, request.origin)
    st.divider()
    render_ai_refinement(user_id, trip_id, request, plan)
    render_revision_history(user_id, trip_id)
    st.divider()
    render_expense_tracker(user_id, trip_id, request, plan)


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
