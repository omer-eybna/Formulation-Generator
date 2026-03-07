"""Integration tests for the monolithic app.py FastAPI routes.

app.py (the monolith) lives alongside the app/ package, so `import app`
loads the package.  We use importlib to load app.py directly as a module
called ``app_monolith``.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure DATABASE_URL is always set for the monolith import ─────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _load_app_monolith(mock_engine):
    """Import app.py as 'app_monolith' with a mocked sqlalchemy engine."""
    spec = importlib.util.spec_from_file_location("app_monolith", APP_PY)
    mod = importlib.util.module_from_spec(spec)

    # Patch create_engine before executing the module code
    with patch("sqlalchemy.create_engine", return_value=mock_engine):
        spec.loader.exec_module(mod)

    # Disable startup events so tests don't call init_db_and_load_if_needed
    mod.app.router.on_startup.clear()
    return mod


@pytest.fixture(scope="module")
def app_env():
    """Load app.py once for the module and yield (TestClient, module)."""
    from fastapi.testclient import TestClient

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__ = MagicMock()
    mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    mod = _load_app_monolith(mock_engine)
    mod.engine = mock_engine  # make the mock accessible to tests

    yield TestClient(mod.app), mod


# ──────────────────────────────────────────────
# GET /
# ──────────────────────────────────────────────
class TestHomeRoute:
    def test_get_home_200(self, app_env):
        client, _ = app_env
        assert client.get("/").status_code == 200

    def test_home_contains_form(self, app_env):
        client, _ = app_env
        html = client.get("/").text
        assert "Formulation Generator" in html
        assert '<form method="post" action="/recommend">' in html

    def test_home_has_sliders(self, app_env):
        client, _ = app_env
        html = client.get("/").text
        for name in ("cannabis_forward", "fruity_forward", "dessert_forward"):
            assert name in html

    def test_home_has_input_fields(self, app_env):
        client, _ = app_env
        html = client.get("/").text
        for name in ("odor_type", "family_type", "tags"):
            assert f'name="{name}"' in html


# ──────────────────────────────────────────────
# POST /recommend
# ──────────────────────────────────────────────
class TestRecommendRoute:
    MOCK_DB_ROWS = [
        {
            "id": "abc-123",
            "name": "Test Product",
            "product_code": "TP-001",
            "odor_type": "Diesel",
            "family_type": "Herbal",
            "tags": "pine, herbal",
            "odor_description": "earthy diesel",
            "intensity_1_10": 7,
            "cannabis_forward": 5,
            "fruity_forward": 2,
            "dessert_forward": 0,
            "aroma_color": "#4a7c3f",
            "notes_color_secondary": "#2e5c2a",
            "main_terpenes": "Myrcene",
        },
    ]

    def _setup_mock_db(self, mod, rows):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = rows
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_conn)
        cm.__exit__ = MagicMock(return_value=False)
        mod.engine.connect.return_value = cm

    def test_post_recommend_200(self, app_env):
        client, mod = app_env
        self._setup_mock_db(mod, self.MOCK_DB_ROWS)
        resp = client.post("/recommend", data={
            "odor_type": "Diesel", "family_type": "Herbal",
            "tags": "pine", "odor_description": "earthy",
            "intensity_1_10": "7",
            "cannabis_forward": "5", "fruity_forward": "2", "dessert_forward": "0",
        })
        assert resp.status_code == 200

    def test_recommend_contains_results(self, app_env):
        client, mod = app_env
        self._setup_mock_db(mod, self.MOCK_DB_ROWS)
        resp = client.post("/recommend", data={
            "odor_type": "Diesel", "family_type": "",
            "tags": "", "odor_description": "",
            "intensity_1_10": "5",
            "cannabis_forward": "0", "fruity_forward": "0", "dessert_forward": "0",
        })
        assert "Top 5 Matches" in resp.text
        assert "Test Product" in resp.text

    def test_recommend_empty_db(self, app_env):
        client, mod = app_env
        self._setup_mock_db(mod, [])
        resp = client.post("/recommend", data={
            "odor_type": "Diesel", "family_type": "",
            "tags": "", "odor_description": "",
            "intensity_1_10": "5",
            "cannabis_forward": "0", "fruity_forward": "0", "dessert_forward": "0",
        })
        assert resp.status_code == 200

    def test_recommend_shows_score_pill(self, app_env):
        client, mod = app_env
        self._setup_mock_db(mod, self.MOCK_DB_ROWS)
        resp = client.post("/recommend", data={
            "odor_type": "Diesel", "family_type": "Herbal",
            "tags": "pine, herbal", "odor_description": "earthy diesel",
            "intensity_1_10": "7",
            "cannabis_forward": "5", "fruity_forward": "2", "dessert_forward": "0",
        })
        assert "pill" in resp.text

    def test_recommend_shows_request_summary(self, app_env):
        client, mod = app_env
        self._setup_mock_db(mod, self.MOCK_DB_ROWS)
        resp = client.post("/recommend", data={
            "odor_type": "Floral", "family_type": "Sweet",
            "tags": "rose", "odor_description": "delicate flower",
            "intensity_1_10": "3",
            "cannabis_forward": "0", "fruity_forward": "0", "dessert_forward": "0",
        })
        assert "Floral" in resp.text
        assert "Sweet" in resp.text
