"""Tests for app/utils/csv_logger.py — CSV request logging."""

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.utils.csv_logger import HEADER, _safe, log_request


# ──────────────────────────────────────────────
# _safe helper
# ──────────────────────────────────────────────
class TestSafe:
    def test_none(self):
        assert _safe(None) == ""

    def test_string(self):
        assert _safe("hello") == "hello"

    def test_number(self):
        assert _safe(42) == "42"


# ──────────────────────────────────────────────
# log_request
# ──────────────────────────────────────────────
class TestLogRequest:
    @pytest.fixture
    def log_env(self, tmp_path, monkeypatch):
        """Redirect LOG_DIR / LOG_FILE to a temp directory."""
        import app.utils.csv_logger as mod

        monkeypatch.setattr(mod, "LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "test_log.csv")
        return tmp_path / "test_log.csv"

    @pytest.fixture
    def req_payload(self):
        return {
            "odor_type": "Diesel",
            "family_type": "Herbal",
            "tags": "pine, herbal",
            "odor_description": "earthy notes",
            "intensity_1_10": 7,
            "cannabis_forward": 5,
            "fruity_forward": 2,
            "dessert_forward": 0,
        }

    @pytest.fixture
    def top5(self):
        return [
            {"name": f"Product {i}", "score": 0.9 - i * 0.1}
            for i in range(5)
        ]

    def test_creates_file_with_header(self, log_env, req_payload, top5):
        log_request(req_payload, top5)
        assert log_env.exists()

        with open(log_env, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == HEADER

    def test_appends_row(self, log_env, req_payload, top5):
        log_request(req_payload, top5)
        log_request(req_payload, top5)

        with open(log_env, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # 1 header + 2 data rows
        assert len(rows) == 3

    def test_no_duplicate_header(self, log_env, req_payload, top5):
        log_request(req_payload, top5)
        log_request(req_payload, top5)

        with open(log_env, newline="", encoding="utf-8") as f:
            content = f.read()

        # The header line should appear exactly once
        header_line = ",".join(HEADER)
        assert content.count(header_line) == 1

    def test_fewer_than_5_results(self, log_env, req_payload):
        short_results = [{"name": "Only One", "score": 0.95}]
        log_request(req_payload, short_results)

        with open(log_env, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        assert row["top1_name"] == "Only One"
        assert row["top2_name"] == ""
        assert row["top5_name"] == ""

    def test_extracts_client_info(self, log_env, req_payload, top5):
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.return_value = "TestAgent/1.0"

        log_request(req_payload, top5, request=mock_request)

        with open(log_env, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        assert row["client_ip"] == "10.0.0.1"
        assert row["user_agent"] == "TestAgent/1.0"

    def test_none_request(self, log_env, req_payload, top5):
        """Passing request=None should still work (empty IP/UA)."""
        path = log_request(req_payload, top5, request=None)
        assert Path(path).exists()

        with open(log_env, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        assert row["client_ip"] == ""
        assert row["user_agent"] == ""
