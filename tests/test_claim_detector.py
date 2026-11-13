"""Tests for claim extraction.

Needs the spaCy `en_core_web_sm` model. The module loads it at import time,
so if it is missing these tests skip rather than fail the build.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

spacy = pytest.importorskip("spacy")

try:
    spacy.load("en_core_web_sm")
except Exception:  # pragma: no cover - depends on the environment
    pytest.skip(
        "the spaCy model 'en_core_web_sm' is not installed "
        "(run: python -m spacy download en_core_web_sm)",
        allow_module_level=True,
    )

from models.claim_detector import extract_claims  # noqa: E402


class TestExtractClaims:
    def test_empty_text_yields_no_claims(self):
        assert extract_claims("") == []
        assert extract_claims("   ") == []
        assert extract_claims(None) == []

    def test_a_long_sentence_with_a_subject_and_verb_is_a_claim(self):
        text = "The government announced a new vaccine programme on Tuesday morning."
        claims = extract_claims(text)
        assert len(claims) == 1
        assert "vaccine" in claims[0]

    def test_short_sentences_are_dropped_among_longer_ones(self):
        text = (
            "It rained. "
            "The committee published a detailed review of the funding programme. "
            "Yes. "
            "The minister denied the allegations during the televised briefing."
        )
        claims = extract_claims(text)
        assert len(claims) == 2
        assert "committee" in claims[0]
        assert "minister" in claims[1]

    def test_a_single_short_line_falls_back_to_the_line(self):
        # Nothing clears the subject-verb filter, so the line fallback runs
        # and the one line comes back as the claim.
        assert extract_claims("It rained all day.") == ["It rained all day."]

    def test_at_most_six_claims_are_returned(self):
        sentences = [
            f"The committee published finding number {i} about the new programme."
            for i in range(20)
        ]
        claims = extract_claims(" ".join(sentences))
        assert len(claims) <= 6

    def test_a_fragment_falls_back_to_lines(self):
        # No sentence carries a subject-verb pair, so the line fallback runs.
        result = extract_claims("Alpha Beta\nGamma Delta\nEpsilon Zeta")
        assert result == ["Alpha Beta", "Gamma Delta", "Epsilon Zeta"]

    def test_the_fallback_also_caps_at_six(self):
        lines = [f"Line {i}" for i in range(30)]
        assert len(extract_claims("\n".join(lines))) == 6

    def test_claims_are_strings(self):
        claims = extract_claims(
            "The minister denied the allegations during the televised briefing."
        )
        assert all(isinstance(c, str) for c in claims)
