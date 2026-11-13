"""Tests for the credibility scoring service.

`services/score.py` has no third-party dependencies, so these run anywhere.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.score import credibility_score, _rating_to_score  # noqa: E402


class TestRatingToScore:
    def test_true_scores_high(self):
        assert _rating_to_score("True") == 90
        assert _rating_to_score("TRUE") == 90

    def test_false_scores_low(self):
        assert _rating_to_score("False") == 15

    def test_partly_true_is_middling(self):
        assert _rating_to_score("Partly True") == 45

    def test_misleading_is_middling(self):
        assert _rating_to_score("Misleading") == 45

    def test_unverified_is_neutral(self):
        assert _rating_to_score("Unverified") == 55

    def test_unknown_rating_falls_back_to_neutral(self):
        assert _rating_to_score("Pants on Fire") == 50

    def test_empty_rating_falls_back_to_neutral(self):
        assert _rating_to_score("") == 50
        assert _rating_to_score(None) == 50


class TestCredibilityScore:
    def test_true_claim_scores_high(self):
        score = credibility_score({"rating": "True"})
        assert score == 90

    def test_false_claim_scores_low(self):
        score = credibility_score({"rating": "False"})
        assert score == 15

    def test_strong_match_nudges_the_score_up(self):
        weak = credibility_score({"rating": "True", "match_score": 0.50})
        strong = credibility_score({"rating": "True", "match_score": 0.90})
        assert strong > weak

    def test_image_suspicion_lowers_the_score(self):
        clean = credibility_score({"rating": "True"}, {"suspicion_score": 0})
        suspect = credibility_score({"rating": "True"}, {"suspicion_score": 40})
        assert suspect < clean

    def test_score_is_clamped_to_the_zero_hundred_range(self):
        high = credibility_score({"rating": "True", "match_score": 1.0})
        assert 0 <= high <= 100

        low = credibility_score({"rating": "False"}, {"suspicion_score": 100})
        assert 0 <= low <= 100

    def test_missing_image_info_is_handled(self):
        assert credibility_score({"rating": "True"}, None) == 90

    def test_missing_rating_is_treated_as_unverified(self):
        # `credibility_score` defaults a missing rating to "Unverified", not
        # to an unknown rating, so it lands on the Unverified band.
        assert credibility_score({}) == 55

    @pytest.mark.parametrize("rating", ["True", "False", "Partly True", "Unverified"])
    def test_score_is_always_an_integer(self, rating):
        score = credibility_score({"rating": rating, "match_score": 0.73})
        assert isinstance(score, int)
