"""
Tests for Geode Six Router — v2 Two-Tier Structure
Tests routing logic, health endpoint, logging, RAM guard, and endpoints.
All Ollama calls are mocked.
"""

import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set test environment before importing router
os.environ["OLLAMA_HOST"] = "http://localhost:11434"
os.environ["LOG_PATH"] = tempfile.mkdtemp()
os.environ["RAM_THRESHOLD_MB"] = "1024"

# Use temp directory for GCA_ROOT in tests
TEST_GCA_ROOT = tempfile.mkdtemp()
os.environ["GCA_ROOT"] = TEST_GCA_ROOT

from router.router import app, select_model, MODEL_LLAMA, MODEL_DOLPHIN, MODEL_BIOMISTRAL, MODEL_LLAVA

client = TestClient(app)


# ---------------------------------------------------------------------------
# Model routing tests
# ---------------------------------------------------------------------------


class TestModelRouting:
    """Test that select_model routes to the correct model."""

    def test_image_routes_to_llava(self):
        model = select_model("Describe this image", sensitive=False, image_path="/tmp/test.jpg")
        assert model == MODEL_LLAVA

    def test_biotech_keyword_routes_to_biomistral(self):
        for keyword in ["biomass", "pubmed", "biotech", "conversion"]:
            model = select_model(
                f"Tell me about {keyword} research", sensitive=False, image_path=None
            )
            assert model == MODEL_BIOMISTRAL

    def test_sensitive_flag_routes_to_dolphin(self):
        model = select_model("What is the meaning of life?", sensitive=True, image_path=None)
        assert model == MODEL_DOLPHIN

    def test_default_routes_to_llama31(self):
        model = select_model("Write a project update email", sensitive=False, image_path=None)
        assert model == MODEL_LLAMA


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test the /health endpoint."""

    @patch("router.router.check_model_available", new_callable=AsyncMock)
    def test_health_endpoint_returns_200(self, mock_check):
        mock_check.return_value = True
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Query endpoint tests
# ---------------------------------------------------------------------------


class TestQueryEndpoint:
    """Test the /query endpoint behavior."""

    @patch("router.router.query_ollama", new_callable=AsyncMock)
    @patch("router.router.get_available_ram_mb")
    def test_successful_query(self, mock_ram, mock_ollama):
        mock_ram.return_value = 4096
        mock_ollama.return_value = {
            "response": "Hello from Llama!",
            "prompt_eval_count": 10,
            "eval_count": 25,
        }
        response = client.post(
            "/query",
            json={"prompt": "Hello", "user": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello from Llama!"

    @patch("router.router.get_available_ram_mb")
    def test_low_memory_returns_friendly_message(self, mock_ram):
        mock_ram.return_value = 512  # Below 1024 threshold
        response = client.post(
            "/query",
            json={"prompt": "Hello", "user": "admin"},
        )
        assert response.status_code == 503
        assert "busy" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Download endpoint tests
# ---------------------------------------------------------------------------


class TestDownloadEndpoint:
    """Test the GET /gca/download endpoint."""

    def test_download_valid_file_returns_200(self, tmp_path):
        """Downloading a valid file within GCA_ROOT returning 200."""
        import router.router as rmod
        original_root = rmod.GCA_ROOT

        # Create a temp GCA root with a two-tier structure
        gca_dir = tmp_path / "gca"
        proj_dir = gca_dir / "Projects" / "GEO"
        proj_dir.mkdir(parents=True)
        test_file = proj_dir / "GEO_AGD_Test_20260321_v1.0.txt"
        test_file.write_text("hello world")

        rmod.GCA_ROOT = str(gca_dir)
        try:
            response = client.get(f"/gca/download?path={test_file}")
            assert response.status_code == 200
            assert response.content == b"hello world"
        finally:
            rmod.GCA_ROOT = original_root

    def test_download_path_outside_gca_returns_403(self, tmp_path):
        import router.router as rmod
        original_root = rmod.GCA_ROOT

        gca_dir = tmp_path / "gca"
        gca_dir.mkdir()
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")

        rmod.GCA_ROOT = str(gca_dir)
        try:
            response = client.get(f"/gca/download?path={outside_file}")
            assert response.status_code == 403
            assert "denied" in response.json()["detail"].lower()
        finally:
            rmod.GCA_ROOT = original_root

    def test_download_nonexistent_file_returns_404(self, tmp_path):
        import router.router as rmod
        original_root = rmod.GCA_ROOT

        gca_dir = tmp_path / "gca"
        gca_dir.mkdir()

        rmod.GCA_ROOT = str(gca_dir)
        try:
            fake_path = gca_dir / "Projects" / "GEO" / "does_not_exist.txt"
            response = client.get(f"/gca/download?path={fake_path}")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            rmod.GCA_ROOT = original_root


# ---------------------------------------------------------------------------
# Codes Endpoint Tests
# ---------------------------------------------------------------------------

class TestCodesEndpoint:
    
    def test_get_codes_returns_dict(self):
        """GET /gca/codes returns the codes dict."""
        response = client.get("/gca/codes")
        assert response.status_code == 200
        data = response.json()
        assert "Projects" in data
        assert "Operations" in data
        assert "GEO" in data["Projects"]
