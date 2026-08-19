from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "RouteMatrix"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    database_path: str = "data/routematrix.db"
    max_trip_days: int = 21


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
        return str(value).strip() if value is not None else ""
    except Exception:
        return ""


def get_settings() -> Settings:
    api_key = os.getenv("GEMINI_API_KEY", "").strip() or _streamlit_secret("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "").strip() or _streamlit_secret("GEMINI_MODEL") or "gemini-2.5-flash-lite"
    database_path = os.getenv("ROUTEMATRIX_DB_PATH", "").strip() or "data/routematrix.db"
    max_trip_days = int(os.getenv("MAX_TRIP_DAYS", "21"))
    return Settings(
        gemini_api_key=api_key,
        gemini_model=model,
        database_path=database_path,
        max_trip_days=max(1, min(max_trip_days, 30)),
    )


def ensure_parent(path: str) -> None:
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
