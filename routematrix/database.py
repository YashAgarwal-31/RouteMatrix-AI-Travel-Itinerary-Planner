from __future__ import annotations

import json
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
        self.path = path
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
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

                CREATE INDEX IF NOT EXISTS idx_trips_user_updated
                ON trips(user_id, updated_at DESC);
                """
            )
            conn.commit()

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]:
        name = name.strip()
        email = email.strip().lower()
        if len(name) < 2:
            raise ValueError("Name must be at least 2 characters.")
        if "@" not in email or len(email) > 254:
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
                    json.dumps(plan, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
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

    def delete_trip(self, user_id: str, trip_id: str) -> bool:
        with closing(self._connect()) as conn:
            cursor = conn.execute("DELETE FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
