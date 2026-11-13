"""Smoke tests for the FastAPI application.

These check that the app starts, that the routes are registered, and that the
form renders — without pulling the sentence-transformer model into CI.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestRoutes:
    def test_the_home_page_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_the_home_page_has_the_form(self, client):
        response = client.get("/")
        assert "Misinformation Detector" in response.text
        assert 'action="/analyze"' in response.text

    def test_the_analyze_route_is_registered(self):
        paths = {route.path for route in app.routes}
        assert "/" in paths
        assert "/analyze" in paths

    def test_the_static_mount_is_registered(self):
        paths = {route.path for route in app.routes}
        assert any(p.startswith("/static") for p in paths)

    def test_analyze_rejects_a_request_with_no_content(self, client):
        # No URL, no text, no file: there is nothing to analyse, so no claims
        # come back. It should still render rather than error.
        response = client.post("/analyze", data={})
        assert response.status_code == 200
