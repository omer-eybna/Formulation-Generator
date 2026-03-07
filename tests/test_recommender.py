"""Tests for app/recommender.py — recommend function with mocked DB."""

from unittest.mock import patch

import pytest

from app.recommender import _score_row, recommend


class TestScoreRowEndToEnd:
    """Test _score_row with various payloads."""

    def test_exact_match_all_fields(self):
        row = {
            "odor_type": "Diesel",
            "family_type": "Herbal",
            "tags": "pine, herbal",
            "odor_description": "earthy diesel",
            "intensity_1_10": 7,
            "cannabis_forward": 5,
            "fruity_forward": 2,
            "dessert_forward": 0,
        }
        req = dict(row)  # identical
        score, bk = _score_row(req, row)
        assert score > 0.8
        assert bk["odor_type"] == 1.0
        assert bk["family_type"] == 1.0

    def test_partial_odor_match(self):
        req = {"odor_type": "diesel", "family_type": "", "tags": "", "odor_description": ""}
        row = {"odor_type": "Diesel / OG", "family_type": "Herbal", "tags": "", "odor_description": ""}
        _, bk = _score_row(req, row)
        # "diesel" is in "diesel / og" → partial match 0.3
        assert bk["odor_type"] == 0.3

    def test_no_forward_signal(self):
        req = {"odor_type": "", "family_type": "", "tags": "",
               "odor_description": "", "cannabis_forward": 0,
               "fruity_forward": 0, "dessert_forward": 0}
        row = {"odor_type": "", "family_type": "", "tags": "",
               "odor_description": "", "cannabis_forward": 5,
               "fruity_forward": 5, "dessert_forward": 5}
        _, bk = _score_row(req, row)
        # zero request vector → forward_similarity returns 0 → clamp01((0+1)/2) = 0.5
        assert bk["forwardness"] == 0.5


class TestRecommend:
    """Test the recommend() function with mocked DB rows."""

    FAKE_ROWS = [
        {
            "id": "1", "name": "Best",
            "odor_type": "Diesel", "family_type": "Herbal",
            "tags": "pine, herbal", "odor_description": "earthy diesel",
            "intensity_1_10": 7,
            "cannabis_forward": 5, "fruity_forward": 2, "dessert_forward": 0,
            "aroma_color": "#000",
        },
        {
            "id": "2", "name": "Worst",
            "odor_type": "Floral", "family_type": "Sweet",
            "tags": "rose", "odor_description": "floral",
            "intensity_1_10": 2,
            "cannabis_forward": 0, "fruity_forward": 0, "dessert_forward": 9,
            "aroma_color": "#fff",
        },
    ]

    @patch("app.recommender.get_formulations")
    def test_sorted_descending(self, mock_get):
        mock_get.return_value = self.FAKE_ROWS

        results = recommend({
            "odor_type": "Diesel",
            "family_type": "Herbal",
            "tags": "pine, herbal",
            "odor_description": "earthy diesel",
            "intensity_1_10": 7,
            "cannabis_forward": 5,
            "fruity_forward": 2,
            "dessert_forward": 0,
        })

        assert len(results) == 2
        assert results[0]["score"] >= results[1]["score"]
        assert results[0]["name"] == "Best"

    @patch("app.recommender.get_formulations")
    def test_result_structure(self, mock_get):
        mock_get.return_value = self.FAKE_ROWS

        results = recommend({
            "odor_type": "", "family_type": "", "tags": "",
            "odor_description": "", "intensity_1_10": 5,
            "cannabis_forward": 0, "fruity_forward": 0, "dessert_forward": 0,
        })

        for r in results:
            assert "name" in r
            assert "score" in r
            assert "why" in r
            assert isinstance(r["why"], dict)

    @patch("app.recommender.get_formulations")
    def test_empty_db(self, mock_get):
        mock_get.return_value = []

        results = recommend({
            "odor_type": "Diesel", "family_type": "", "tags": "",
            "odor_description": "", "intensity_1_10": 5,
        })
        assert results == []
