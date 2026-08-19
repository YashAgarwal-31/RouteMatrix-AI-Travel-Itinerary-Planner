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

1. Merge the production-ready branch to `main` after CI is green.
2. In Streamlit Community Cloud, create an app from this repository.
3. Set the entry point to `app.py`.
4. Add `GEMINI_API_KEY` in the app's Secrets settings.
5. Deploy.
6. Run the smoke test below before sharing the link.

## 3. Persistence note

The current architecture uses SQLite for accounts, saved itineraries, itinerary revisions, and recorded expenses. It is appropriate for local development, portfolio demos, and a single app instance with persistent storage.

Some managed platforms use ephemeral filesystems, which means local SQLite data can be lost on restart/redeploy. For a persistent public multi-user deployment, set `ROUTEMATRIX_DB_PATH` to a persistent volume or replace the SQLite adapter with a managed database such as PostgreSQL/Supabase/MongoDB.

Do not market SQLite session persistence as durable cloud storage unless the selected host provides a persistent volume.

## 4. Production smoke test

Before sharing the live URL:

- Register a new account, sign out, and sign in again.
- Confirm a second user cannot see the first user's saved trips.
- Generate a 1-day itinerary.
- Generate a 5–7 day itinerary with dietary and accessibility constraints.
- Confirm every generated day renders without schema errors.
- Confirm planned budget, AI-estimated total, budget breakdown, and currency are displayed.
- Ask AI refinement to change a saved itinerary and confirm a new revision is created.
- Restore an older itinerary revision and confirm the restored plan becomes a new revision.
- Add and delete actual trip expenses and verify planned-vs-recorded totals update.
- Open at least one activity map search and the destination hotel/flight search shortcuts.
- Download Markdown, JSON, and `.ics` calendar exports; open the calendar file in a calendar app.
- Reopen the trip from **My trips** after a fresh browser session.
- Delete a saved trip and confirm its revisions/expenses disappear with it.
- Test a missing/invalid Gemini key and confirm generation/refinement fail safely without corrupting saved data.
- Test unreasonable/reversed dates and invalid expense amounts.
- Test the app on desktop and mobile widths.

## 5. AI/live-data checks

Use several real destinations and confirm that:

- The AI returns exactly the requested number of days.
- The itinerary does not claim guaranteed current prices, hotel/flight availability, weather, visa approval, or opening hours.
- Dietary/accessibility constraints are reflected throughout the plan when supplied.
- Refinement preserves the original destination/dates/traveler/budget context while applying the requested change.
- Map queries are useful enough to resolve the intended activity through an external map search.

## 6. Security checklist

- Keep API keys in provider secrets/environment variables.
- Keep `.env`, `.streamlit/secrets.toml`, and local database files ignored by Git.
- Do not store payment information, passport/identity documents, or highly sensitive personal information in this demo architecture.
- Generated recommendations are planning guidance, not guarantees of price, safety, availability, visa rules, weather, or opening hours.
- For a larger public deployment, add managed identity, a managed database, rate limiting, monitoring/alerts, backups, and a privacy/data-retention policy.
