from streamlit.testing.v1 import AppTest


def test_streamlit_auth_screen_starts_without_provider_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("ROUTEMATRIX_DB_PATH", str(tmp_path / "app-smoke.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = AppTest.from_file("app.py", default_timeout=15).run()

    assert not app.exception
    assert any("Your trips, saved in one workspace" in item.value for item in app.subheader)
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]

