from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import hash_password, verify_password


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str) -> None:
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS trip_revisions (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    instruction TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(trip_id, revision_number)
                );

                CREATE TABLE IF NOT EXISTS expenses (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    currency TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_trips_user_updated
                ON trips(user_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_revisions_trip
                ON trip_revisions(trip_id, revision_number DESC);

                CREATE INDEX IF NOT EXISTS idx_expenses_trip_date
                ON expenses(trip_id, expense_date DESC, created_at DESC);
                """
            )
            conn.commit()

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]:
        name = name.strip()
        email = email.strip().lower()
        if len(name) < 2:
            raise ValueError("Name must be at least 2 characters.")
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address.")
        salt, password_hash = hash_password(password)
        user_id = str(uuid.uuid4())
        now = _utc_now()
        try:
            with closing(self._connect()) as conn:
                conn.execute(
                    "INSERT INTO users (id, name, email, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, name[:100], email, salt, password_hash, now),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc
        return {"id": user_id, "name": name[:100], "email": email, "created_at": now}

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        email = email.strip().lower()
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_salt"], row["password_hash"]):
            return None
        return {"id": row["id"], "name": row["name"], "email": row["email"], "created_at": row["created_at"]}

    def save_trip(self, user_id: str, request: dict[str, Any], plan: dict[str, Any]) -> str:
        trip_id = str(uuid.uuid4())
        now = _utc_now()
        title = str(plan.get("trip_title") or f"Trip to {request.get('destination', 'destination')}")[:160]
        destination = str(request.get("destination", ""))[:120]
        plan_json = json.dumps(plan, ensure_ascii=False, default=str)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO trips (
                    id, user_id, title, destination, start_date, end_date,
                    request_json, plan_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip_id,
                    user_id,
                    title,
                    destination,
                    str(request.get("start_date", "")),
                    str(request.get("end_date", "")),
                    json.dumps(request, ensure_ascii=False, default=str),
                    plan_json,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO trip_revisions (id, trip_id, user_id, revision_number, instruction, plan_json, created_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                """,
                (str(uuid.uuid4()), trip_id, user_id, "Initial AI itinerary", plan_json, now),
            )
            conn.commit()
        return trip_id

    def list_trips(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, title, destination, start_date, end_date, created_at, updated_at
                FROM trips WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_trip(self, user_id: str, trip_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM trips WHERE id = ? AND user_id = ?",
                (trip_id, user_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        result["plan"] = json.loads(result.pop("plan_json"))
        return result

    def update_trip_plan(self, user_id: str, trip_id: str, plan: dict[str, Any], instruction: str) -> int:
        instruction = instruction.strip()[:1000] or "AI itinerary refinement"
        now = _utc_now()
        plan_json = json.dumps(plan, ensure_ascii=False, default=str)
        title = str(plan.get("trip_title") or "Updated itinerary")[:160]
        with closing(self._connect()) as conn:
            # Serialize the read-increment-write sequence so two refinements
            # cannot allocate the same revision number.
            conn.execute("BEGIN IMMEDIATE")
            owned = conn.execute(
                "SELECT id FROM trips WHERE id = ? AND user_id = ?",
                (trip_id, user_id),
            ).fetchone()
            if not owned:
                raise ValueError("Trip not found.")
            row = conn.execute(
                "SELECT COALESCE(MAX(revision_number), 0) AS latest FROM trip_revisions WHERE trip_id = ? AND user_id = ?",
                (trip_id, user_id),
            ).fetchone()
            revision = int(row["latest"]) + 1
            conn.execute(
                "UPDATE trips SET title = ?, plan_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (title, plan_json, now, trip_id, user_id),
            )
            conn.execute(
                """
                INSERT INTO trip_revisions (id, trip_id, user_id, revision_number, instruction, plan_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), trip_id, user_id, revision, instruction, plan_json, now),
            )
            conn.commit()
        return revision

    def list_trip_revisions(self, user_id: str, trip_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, revision_number, instruction, created_at
                FROM trip_revisions
                WHERE trip_id = ? AND user_id = ?
                ORDER BY revision_number DESC
                """,
                (trip_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def restore_trip_revision(self, user_id: str, trip_id: str, revision_id: str) -> int:
        with closing(self._connect()) as conn:
            revision = conn.execute(
                """
                SELECT plan_json, revision_number FROM trip_revisions
                WHERE id = ? AND trip_id = ? AND user_id = ?
                """,
                (revision_id, trip_id, user_id),
            ).fetchone()
        if not revision:
            raise ValueError("Revision not found.")
        plan = json.loads(revision["plan_json"])
        return self.update_trip_plan(
            user_id,
            trip_id,
            plan,
            f"Restored revision {revision['revision_number']}",
        )

    def add_expense(
        self,
        user_id: str,
        trip_id: str,
        expense_date: str,
        category: str,
        description: str,
        amount: float,
        currency: str,
    ) -> str:
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        category = category.strip()[:60] or "Other"
        description = description.strip()[:200]
        currency = currency.strip().upper()[:6]
        expense_id = str(uuid.uuid4())
        now = _utc_now()
        with closing(self._connect()) as conn:
            owned = conn.execute(
                "SELECT id FROM trips WHERE id = ? AND user_id = ?",
                (trip_id, user_id),
            ).fetchone()
            if not owned:
                raise ValueError("Trip not found.")
            conn.execute(
                """
                INSERT INTO expenses (
                    id, trip_id, user_id, expense_date, category, description, amount, currency, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (expense_id, trip_id, user_id, expense_date, category, description, float(amount), currency, now),
            )
            conn.commit()
        return expense_id

    def list_expenses(self, user_id: str, trip_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, expense_date, category, description, amount, currency, created_at
                FROM expenses
                WHERE trip_id = ? AND user_id = ?
                ORDER BY expense_date DESC, created_at DESC
                """,
                (trip_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_expense(self, user_id: str, trip_id: str, expense_id: str) -> bool:
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "DELETE FROM expenses WHERE id = ? AND trip_id = ? AND user_id = ?",
                (expense_id, trip_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_trip(self, user_id: str, trip_id: str) -> bool:
        with closing(self._connect()) as conn:
            cursor = conn.execute("DELETE FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
