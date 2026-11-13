"""Tests for the fact-check service.

The semantic path needs `sentence-transformers` and the `all-MiniLM-L6-v2`
model, which is a heavyweight download. If either is unavailable these tests
skip rather than fail.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sentence_transformers")

from services import factcheck  # noqa: E402

VALID_RATINGS = {"True", "False", "Partly True", "Unverified"}


@pytest.fixture(scope="module")
def demo_db():
    return factcheck._DEMO_CLAIMS


class TestDemoDatabase:
    def test_the_database_is_not_empty(self, demo_db):
        assert len(demo_db) > 0

    def test_every_entry_has_the_expected_shape(self, demo_db):
        for entry in demo_db:
            assert set(entry) == {"claim", "rating", "source"}
            assert entry["claim"].strip()
            assert entry["rating"].strip()
            assert entry["source"].startswith("http")

    def test_every_rating_is_understood_by_the_scorer(self, demo_db):
        from services.score import _rating_to_score

        for entry in demo_db:
            assert entry["rating"] in VALID_RATINGS
            assert _rating_to_score(entry["rating"]) != 50 or entry["rating"] == "Unverified"


class TestSemanticMatching:
    def test_a_near_duplicate_claim_matches_its_entry(self, demo_db):
        result = factcheck._semantic_match_demo(demo_db[0]["claim"])
        assert result["method"] == "demo_semantic"
        assert result["score"] > 0.55
        assert result["claim"] == demo_db[0]["claim"]

    def test_the_match_carries_the_source_and_rating(self, demo_db):
        result = factcheck._semantic_match_demo(demo_db[0]["claim"])
        assert result["rating"] in VALID_RATINGS
        assert result["source"].startswith("http")


class TestFactCheck:
    def test_a_known_claim_comes_back_rated(self, demo_db):
        result = factcheck.fact_check(demo_db[0]["claim"])
        assert result["rating"] in VALID_RATINGS
        assert result["method"] == "demo_semantic"

    def test_an_unrelated_claim_is_marked_unverified(self):
        result = factcheck.fact_check(
            "The municipal orchestra performed a concert of obscure medieval motets."
        )
        assert result["rating"] == "Unverified"
        assert result["source"] is None
        assert result["method"] == "none"

    def test_a_low_confidence_match_is_not_trusted(self):
        result = factcheck.fact_check("Quantum chromodynamics lattice gauge theory.")
        assert result["match_score"] < 0.55
        assert result["rating"] == "Unverified"
