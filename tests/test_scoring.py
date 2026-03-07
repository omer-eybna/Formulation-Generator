"""Tests for app/services/scoring.py — the core scoring utilities."""

import math

import numpy as np
import pytest

from app.services.scoring import (
    clamp01,
    fnum,
    forward_similarity,
    intensity_similarity,
    jaccard,
    norm_text,
    score_row,
    tokenize,
)


# ──────────────────────────────────────────────
# norm_text
# ──────────────────────────────────────────────
class TestNormText:
    def test_none_returns_empty(self):
        assert norm_text(None) == ""

    def test_strips_whitespace(self):
        assert norm_text("  Hello  ") == "hello"

    def test_lowercases(self):
        assert norm_text("DIESEL") == "diesel"

    def test_numeric_input(self):
        assert norm_text(42) == "42"


# ──────────────────────────────────────────────
# tokenize
# ──────────────────────────────────────────────
class TestTokenize:
    def test_comma_separated(self):
        assert tokenize("pine, herbal, glue") == ["pine", "herbal", "glue"]

    def test_slash_splits(self):
        assert tokenize("earthy/woody") == ["earthy", "woody"]

    def test_pipe_splits(self):
        assert tokenize("sweet|sour") == ["sweet", "sour"]

    def test_short_tokens_removed(self):
        # single-char tokens should be stripped
        assert tokenize("a, bb, c, dd") == ["bb", "dd"]

    def test_none_returns_empty_list(self):
        assert tokenize(None) == []

    def test_empty_string(self):
        assert tokenize("") == []


# ──────────────────────────────────────────────
# jaccard
# ──────────────────────────────────────────────
class TestJaccard:
    def test_identical_sets(self):
        assert jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_disjoint_sets(self):
        assert jaccard(["a", "b"], ["c", "d"]) == 0.0

    def test_partial_overlap(self):
        # {a,b} ∩ {b,c} = {b} → 1/3
        assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)

    def test_both_empty(self):
        assert jaccard([], []) == 0.0

    def test_one_empty(self):
        assert jaccard(["a"], []) == 0.0


# ──────────────────────────────────────────────
# clamp01
# ──────────────────────────────────────────────
class TestClamp01:
    def test_below_zero(self):
        assert clamp01(-0.5) == 0.0

    def test_above_one(self):
        assert clamp01(1.5) == 1.0

    def test_in_range(self):
        assert clamp01(0.7) == 0.7

    def test_boundary_zero(self):
        assert clamp01(0.0) == 0.0

    def test_boundary_one(self):
        assert clamp01(1.0) == 1.0


# ──────────────────────────────────────────────
# intensity_similarity
# ──────────────────────────────────────────────
class TestIntensitySimilarity:
    def test_same_intensity(self):
        assert intensity_similarity(5.0, 5.0) == 1.0

    def test_max_distance(self):
        # distance 9 → similarity 0
        assert intensity_similarity(1.0, 10.0) == 0.0

    def test_one_step_apart(self):
        assert intensity_similarity(5.0, 6.0) == pytest.approx(1.0 - 1 / 9)

    def test_symmetric(self):
        assert intensity_similarity(3.0, 7.0) == intensity_similarity(7.0, 3.0)


# ──────────────────────────────────────────────
# forward_similarity  (cosine similarity)
# ──────────────────────────────────────────────
class TestForwardSimilarity:
    def test_parallel_vectors(self):
        assert forward_similarity(1, 0, 0, 2, 0, 0) == pytest.approx(1.0)

    def test_anti_parallel(self):
        assert forward_similarity(1, 0, 0, -1, 0, 0) == pytest.approx(-1.0)

    def test_orthogonal(self):
        assert forward_similarity(1, 0, 0, 0, 1, 0) == pytest.approx(0.0)

    def test_zero_request_vector(self):
        assert forward_similarity(0, 0, 0, 1, 1, 1) == 0.0

    def test_zero_row_vector(self):
        assert forward_similarity(1, 1, 1, 0, 0, 0) == 0.0


# ──────────────────────────────────────────────
# fnum  (flexible number parser)
# ──────────────────────────────────────────────
class TestFnum:
    def test_integer(self):
        assert fnum(5) == 5.0

    def test_float(self):
        assert fnum(3.14) == pytest.approx(3.14)

    def test_string_float(self):
        assert fnum("7.5") == 7.5

    def test_fraction_string(self):
        # "2.2/5" → takes numerator 2.2
        assert fnum("2.2/5") == pytest.approx(2.2)

    def test_none_returns_default(self):
        assert fnum(None) == 0.0
        assert fnum(None, default=5.0) == 5.0

    def test_empty_string_returns_default(self):
        assert fnum("") == 0.0

    def test_garbage_returns_default(self):
        assert fnum("not-a-number", default=99.0) == 99.0


# ──────────────────────────────────────────────
# score_row  (end-to-end scoring)
# ──────────────────────────────────────────────
class TestScoreRow:
    def test_perfect_match_scores_high(self, sample_request, sample_row):
        """Row closely matching the request should score near max."""
        score, breakdown = score_row(sample_request, sample_row)
        assert 0.0 <= score <= 1.0
        # With matching odor_type, family_type, overlapping tags, close
        # intensity and aligned forward profile this should score > 0.5
        assert score > 0.5
        assert set(breakdown.keys()) == {
            "odor_type", "family_type", "tags", "description",
            "intensity", "forwardness",
        }

    def test_empty_request_scores_low(self, sample_row):
        """An empty request has no signal — score should be low."""
        empty_req = {
            "odor_type": "",
            "family_type": "",
            "tags": "",
            "odor_description": "",
            "intensity_1_10": 5,
            "cannabis_forward": 0,
            "fruity_forward": 0,
            "dessert_forward": 0,
        }
        score, _ = score_row(empty_req, sample_row)
        # Only intensity contributes (default vs row); everything else ~0
        assert score < 0.5

    def test_weights_sum_to_one(self):
        """The hardcoded weights in score_row should sum to 1.0."""
        assert 0.22 + 0.18 + 0.18 + 0.12 + 0.20 + 0.10 == pytest.approx(1.0)

    def test_score_is_float(self, sample_request, sample_row):
        score, _ = score_row(sample_request, sample_row)
        assert isinstance(score, float)

    def test_breakdown_values_between_0_and_1(self, sample_request, sample_row):
        _, breakdown = score_row(sample_request, sample_row)
        for v in breakdown.values():
            assert 0.0 <= v <= 1.0
