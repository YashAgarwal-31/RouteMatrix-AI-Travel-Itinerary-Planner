from datetime import date

from routematrix.database import Database


def test_user_and_trip_round_trip(tmp_path):
    db = Database(str(tmp_path / "route.db"))
    user = db.create_user("Yash", "yash@example.com", "StrongPass123")
    assert db.authenticate("YASH@example.com", "StrongPass123")["id"] == user["id"]
    assert db.authenticate("yash@example.com", "wrong") is None

    request = {
        "destination": "Tokyo, Japan",
        "origin": "Delhi, India",
        "start_date": date(2026, 9, 1).isoformat(),
        "end_date": date(2026, 9, 3).isoformat(),
    }
    plan = {"trip_title": "Tokyo in 3 Days", "destination": "Tokyo, Japan"}
    trip_id = db.save_trip(user["id"], request, plan)

    listed = db.list_trips(user["id"])
    assert listed[0]["id"] == trip_id

    loaded = db.get_trip(user["id"], trip_id)
    assert loaded["request"]["destination"] == "Tokyo, Japan"
    assert loaded["plan"]["trip_title"] == "Tokyo in 3 Days"

    revisions = db.list_trip_revisions(user["id"], trip_id)
    assert revisions[0]["revision_number"] == 1

    updated_plan = {"trip_title": "Relaxed Tokyo", "destination": "Tokyo, Japan"}
    revision_number = db.update_trip_plan(user["id"], trip_id, updated_plan, "Make it more relaxed")
    assert revision_number == 2
    assert db.get_trip(user["id"], trip_id)["plan"]["trip_title"] == "Relaxed Tokyo"

    revisions = db.list_trip_revisions(user["id"], trip_id)
    assert [item["revision_number"] for item in revisions] == [2, 1]
    restored_number = db.restore_trip_revision(user["id"], trip_id, revisions[1]["id"])
    assert restored_number == 3
    assert db.get_trip(user["id"], trip_id)["plan"]["trip_title"] == "Tokyo in 3 Days"

    expense_id = db.add_expense(
        user["id"],
        trip_id,
        "2026-09-02",
        "Food",
        "Sushi dinner",
        2500,
        "INR",
    )
    expenses = db.list_expenses(user["id"], trip_id)
    assert expenses[0]["id"] == expense_id
    assert expenses[0]["amount"] == 2500
    assert db.delete_expense(user["id"], trip_id, expense_id)
    assert db.list_expenses(user["id"], trip_id) == []

    assert db.delete_trip(user["id"], trip_id)
    assert db.get_trip(user["id"], trip_id) is None


def test_trip_data_is_user_scoped(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    owner = db.create_user("Owner", "owner@example.com", "StrongPass123")
    stranger = db.create_user("Stranger", "stranger@example.com", "StrongPass123")
    trip_id = db.save_trip(
        owner["id"],
        {
            "destination": "Paris",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
        },
        {"trip_title": "Paris Trip", "destination": "Paris"},
    )

    assert db.get_trip(stranger["id"], trip_id) is None
    assert not db.delete_trip(stranger["id"], trip_id)
    try:
        db.add_expense(stranger["id"], trip_id, "2026-09-01", "Food", "Lunch", 100, "EUR")
    except ValueError as exc:
        assert "Trip not found" in str(exc)
    else:
        raise AssertionError("Expected cross-user expense write to be rejected")
