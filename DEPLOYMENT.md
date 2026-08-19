# RouteMatrix Deployment Guide

RouteMatrix is a Streamlit application. The simplest public demo deployment is Streamlit Community Cloud.

## 1. Required secret

Create a Gemini API key and keep it outside Git. RouteMatrix reads the key from either an environment variable or Streamlit secrets:

```toml
GEMINI_API_KEY = "your-key"
GEMINI_MODEL = "gemini-2.5-flash-lite"
```

Never commit `.streamlit/secrets.toml` or `.env`.

## 2. Streamlit Community Cloud

1. Push the production-ready branch to `main`.
2. In Streamlit Community Cloud, create an app from this repository.
3. Set the entry point to `app.py`.
4. Add `GEMINI_API_KEY` in the app's Secrets settings.
5. Deploy.
6. Run the smoke test below before sharing the link.

## 3. Persistence note

The current architecture uses SQLite for accounts and saved itineraries. It is ideal for local development, portfolio demos, and a single app instance. Some managed platforms use ephemeral filesystems, which means local SQLite data may be lost on restart/redeploy.

For a persistent public multi-user deployment, set `ROUTEMATRIX_DB_PATH` to a persistent volume or replace the SQLite adapter with a managed database such as PostgreSQL/Supabase/MongoDB.

## 4. Production smoke test

Before sharing the live URL:

- Register a new account and sign in again after logout.
- Generate a 1-day itinerary.
- Generate a 5-7 day itinerary with dietary/accessibility constraints.
- Confirm every generated day renders without schema errors.
- Confirm the total budget, budget breakdown, and currency are displayed.
- Open at least one map search shortcut.
- Download both Markdown and JSON exports.
- Open the trip again from **My trips**.
- Delete a saved trip and verify it disappears.
- Test a missing/invalid Gemini key and confirm the app fails safely.
- Test the app on desktop and mobile widths.

## 5. Security checklist

- Keep API keys in provider secrets/environment variables.
- Keep `.env`, `.streamlit/secrets.toml`, and local database files ignored by Git.
- Do not store payment information or passport/identity documents in this demo architecture.
- Generated recommendations are planning guidance, not guarantees of price, safety, availability, visa rules, weather, or opening hours.
