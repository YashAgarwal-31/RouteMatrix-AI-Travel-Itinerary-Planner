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

    assert db.delete_trip(user["id"], trip_id)
    assert db.get_trip(user["id"], trip_id) is None
