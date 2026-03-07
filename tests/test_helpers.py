"""Tests for helper functions in app.py, app/utils_legacy.py, and app/recommender.py."""

import math

import numpy as np
import pytest


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# app/utils_legacy.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from app.utils_legacy import nan_to_none as legacy_nan_to_none
from app.utils_legacy import parse_forward_value as legacy_parse_forward


class TestLegacyNanToNone:
    def test_none(self):
        assert legacy_nan_to_none(None) is None

    def test_nan(self):
        assert legacy_nan_to_none(float("nan")) is None

    def test_regular_float(self):
        assert legacy_nan_to_none(3.14) == 3.14

    def test_string_passes_through(self):
        assert legacy_nan_to_none("hello") == "hello"

    def test_zero(self):
        assert legacy_nan_to_none(0) == 0


class TestLegacyParseForward:
    def test_integer(self):
        assert legacy_parse_forward(2) == 2.0

    def test_string_number(self):
        assert legacy_parse_forward("3.5") == 3.5

    def test_fraction_scales(self):
        # "2/5" → 2 * (10/5) = 4.0
        assert legacy_parse_forward("2/5") == pytest.approx(4.0)

    def test_none(self):
        assert legacy_parse_forward(None) == 0

    def test_garbage(self):
        assert legacy_parse_forward("abc") == 0

    def test_fraction_2_2_over_5(self):
        # "2.2/5" → 2.2 * (10/5) = 4.4
        assert legacy_parse_forward("2.2/5") == pytest.approx(4.4)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# app/recommender.py private helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from app.recommender import _norm_text, _tokenize, _jaccard, _clamp01, _fnum, _score_row


class TestRecommenderNormText:
    def test_none(self):
        assert _norm_text(None) == ""

    def test_strip_lower(self):
        assert _norm_text("  HELLO  ") == "hello"


class TestRecommenderTokenize:
    def test_basic(self):
        assert _tokenize("pine, herbal") == ["pine", "herbal"]

    def test_slash(self):
        assert "earthy" in _tokenize("earthy/woody")
        assert "woody" in _tokenize("earthy/woody")


class TestRecommenderJaccard:
    def test_identical(self):
        assert _jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_disjoint(self):
        assert _jaccard(["x"], ["y"]) == 0.0


class TestRecommenderClamp:
    def test_clamp(self):
        assert _clamp01(-1) == 0.0
        assert _clamp01(2) == 1.0
        assert _clamp01(0.5) == 0.5


class TestRecommenderFnum:
    def test_integer(self):
        assert _fnum(5) == 5.0

    def test_fraction(self):
        # "2.2/5" → numerator 2.2
        assert _fnum("2.2/5") == pytest.approx(2.2)

    def test_none(self):
        assert _fnum(None) == 0.0

    def test_nan_string(self):
        assert _fnum("nan") == 0.0

    def test_empty(self):
        assert _fnum("") == 0.0


class TestRecommenderScoreRow:
    def test_returns_tuple(self, sample_request, sample_row):
        result = _score_row(sample_request, sample_row)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_score_range(self, sample_request, sample_row):
        score, _ = _score_row(sample_request, sample_row)
        assert 0.0 <= score <= 1.0

    def test_breakdown_keys(self, sample_request, sample_row):
        _, bk = _score_row(sample_request, sample_row)
        assert set(bk.keys()) == {
            "odor_type", "family_type", "tags", "description",
            "intensity", "forwardness",
        }
