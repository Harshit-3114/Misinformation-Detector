"""Tests for the image inspection heuristics.

`services/media_check.py` only needs Pillow, so these are cheap to run.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.media_check import check_image  # noqa: E402


@pytest.fixture
def image_factory(tmp_path):
    def make(name="sample.png", size=(800, 600), color=(120, 30, 200), exif=None, noise=False):
        path = tmp_path / name
        if noise:
            # Random pixels, so the encoded file has a realistic size rather
            # than compressing down to a few kilobytes.
            import random

            rng = random.Random(1234)
            width, height = size
            data = bytes(rng.randrange(256) for _ in range(width * height * 3))
            img = Image.frombytes("RGB", size, data)
        else:
            img = Image.new("RGB", size, color)
        if exif is not None:
            img.save(path, exif=exif)
        else:
            img.save(path)
        return str(path)

    return make


class TestCheckImage:
    def test_a_clean_image_with_metadata_is_likely_authentic(self, image_factory):
        exif = Image.Exif()
        exif[0x010F] = "Test Camera"
        result = check_image(
            image_factory("clean.jpg", size=(800, 600), exif=exif, noise=True)
        )
        assert result["status"] == "checked"
        assert result["has_exif"] is True
        assert result["suspicion_score"] == 0
        assert result["verdict"] == "Likely Authentic"
        assert result["width"] == 800
        assert result["height"] == 600

    def test_a_clean_image_without_metadata_is_flagged_for_review(self, image_factory):
        # Stripped metadata on its own is worth 30 points, which is enough to
        # call the image suspicious but not enough to call it synthetic.
        result = check_image(image_factory("stripped.png", size=(800, 600), noise=True))
        assert result["has_exif"] is False
        assert result["suspicion_score"] == 30
        assert result["verdict"] == "Suspicious — review manually"

    def test_a_heavily_compressed_image_is_flagged(self, image_factory):
        # A flat image compresses to a few kilobytes, which trips the
        # small-file heuristic even though the pixels are legitimate.
        result = check_image(image_factory("flat.png", size=(800, 600)))
        assert result["size_bytes"] < 50_000
        assert "Small file size" in result["reasons"]
        assert result["suspicion_score"] >= 10

    def test_a_small_image_is_suspicious(self, image_factory):
        result = check_image(image_factory("tiny.png", size=(100, 100)))
        assert result["suspicion_score"] > 0
        assert result["verdict"] in (
            "Suspicious — review manually",
            "Possibly AI-generated / metadata stripped",
        )

    def test_low_resolution_is_reported(self, image_factory):
        result = check_image(image_factory("small.png", size=(320, 320)))
        assert "Low resolution" in result["reasons"]

    def test_exif_presence_is_detected(self, image_factory):
        exif = Image.Exif()
        exif[0x010F] = "Test Camera"
        result = check_image(image_factory("with-exif.jpg", exif=exif))
        assert result["has_exif"] is True
        assert "No EXIF metadata found" not in result["reasons"]

    def test_missing_exif_is_noted(self, image_factory):
        result = check_image(image_factory("no-exif.png"))
        assert result["has_exif"] is False
        assert "No EXIF metadata found" in result["reasons"]

    def test_a_non_image_file_reports_an_error(self, tmp_path):
        path = tmp_path / "not-an-image.txt"
        path.write_text("definitely not an image")
        result = check_image(str(path))
        assert result["status"] == "error"
        assert "message" in result

    def test_a_missing_file_reports_an_error(self, tmp_path):
        result = check_image(str(tmp_path / "does-not-exist.png"))
        assert result["status"] == "error"

    def test_size_is_reported_in_bytes(self, image_factory):
        result = check_image(image_factory("sized.png"))
        assert result["size_bytes"] > 0

    def test_verdict_matches_the_suspicion_band(self, image_factory):
        result = check_image(image_factory("band.png", size=(100, 100)))
        score = result["suspicion_score"]
        if score >= 40:
            assert result["verdict"] == "Possibly AI-generated / metadata stripped"
        elif score >= 20:
            assert result["verdict"] == "Suspicious — review manually"
        else:
            assert result["verdict"] == "Likely Authentic"
