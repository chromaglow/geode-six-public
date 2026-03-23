"""
Tests for Geode Six Search & Browse — v2 Two-Tier Structure
Tests search results, browse filters/sort, and synthesize flag.
"""

import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set test environment
os.environ["OLLAMA_HOST"] = "http://localhost:11434"
os.environ["LOG_PATH"] = tempfile.mkdtemp()
os.environ["RAM_THRESHOLD_MB"] = "1024"

# Create a test GCA_ROOT with sample files in two tiers
TEST_GCA_ROOT = tempfile.mkdtemp()
os.environ["GCA_ROOT"] = TEST_GCA_ROOT
os.environ["CHROMA_PATH"] = tempfile.mkdtemp()

from gca.codes import ensure_codes_file
ensure_codes_file()

# Create test files
for tier, project in [("Projects", "PR2"), ("Projects", "PR1"), ("Projects", "GEO"), ("Operations", "HR")]:
    proj_dir = os.path.join(TEST_GCA_ROOT, tier, project)
    os.makedirs(proj_dir, exist_ok=True)

# PR2 files (Projects)
with open(os.path.join(TEST_GCA_ROOT, "Projects", "PR2", "PR2_REQ_ProjectBeta_20260304_v1.0.docx"), "w") as f:
    f.write("test")
with open(os.path.join(TEST_GCA_ROOT, "Projects", "PR2", "PR2_BRF_BiomassProject_20260310_v0.1.pdf"), "w") as f:
    f.write("test")

# PR1 files (Projects)
with open(os.path.join(TEST_GCA_ROOT, "Projects", "PR1", "PR1_TSR_EconomicDev_20260313_v2.0.docx"), "w") as f:
    f.write("test")

# GEO files (Projects)
with open(os.path.join(TEST_GCA_ROOT, "Projects", "GEO", "GEO_AGD_WeeklyMeeting_20260315_v1.0.docx"), "w") as f:
    f.write("test")
with open(os.path.join(TEST_GCA_ROOT, "Projects", "GEO", "GEO_SUM_WeeklyMeeting_20260310_v1.0.docx"), "w") as f:
    f.write("test")

# HR files (Operations)
with open(os.path.join(TEST_GCA_ROOT, "Operations", "HR", "HR_OPS_Onboarding_20260301_v1.0.txt"), "w") as f:
    f.write("test")


from router.router import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Browse endpoint tests
# ---------------------------------------------------------------------------


class TestBrowseEndpoint:
    """Test GET /gca/browse endpoint."""

    def test_browse_returns_all_files(self):
        """Browse without filters returns all files across both tiers."""
        response = client.get("/gca/browse")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 6

    def test_browse_filters_by_tier(self):
        """Browse with tier filter returns only that tier's files."""
        # Projects
        resp_proj = client.get("/gca/browse?tier=Projects")
        assert resp_proj.status_code == 200
        assert resp_proj.json()["total"] == 5
        
        # Operations
        resp_ops = client.get("/gca/browse?tier=Operations")
        assert resp_ops.status_code == 200
        assert resp_ops.json()["total"] == 1
        assert resp_ops.json()["files"][0]["project"] == "HR"

    def test_browse_filters_by_project(self):
        """Browse with project filter returns only that project's files."""
        response = client.get("/gca/browse?project=PR2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for f in data["files"]:
            assert f["project"] == "PR2"

    def test_browse_filters_by_type(self):
        """Browse with type filter returns only matching types."""
        response = client.get("/gca/browse?type=AGD")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["files"][0]["type"] == "AGD"

    def test_browse_sorts_by_date_descending(self):
        """Default sort is date descending (newest first)."""
        response = client.get("/gca/browse")
        assert response.status_code == 200
        data = response.json()
        dates = [f["date"] for f in data["files"] if f["date"]]
        assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Search endpoint tests
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    """Test POST /gca/search endpoint."""

    def test_empty_query_returns_error(self):
        """Empty search query returns error."""
        response = client.post("/gca/search", json={"query": "", "synthesize": False})
        assert response.status_code == 400

    @patch("gca.embed._get_collection")
    @patch("gca.embed.get_embedding", new_callable=AsyncMock)
    def test_search_scope_filter_passed_to_chroma(self, mock_embed, mock_get_collection):
        """Search scope passes correct where filter to Chroma."""
        mock_embed.return_value = [0.1] * 768
        
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [], "metadatas": [], "distances": [], "documents": []}
        mock_get_collection.return_value = mock_collection
        
        # Search Projects only
        client.post("/gca/search", json={"query": "test", "scope": "Projects"})
        mock_collection.query.assert_called_with(
            query_embeddings=[[0.1] * 768],
            n_results=10,
            include=["documents", "metadatas", "distances"],
            where={"tier": "Projects"}
        )
        
        # Search Operations only
        client.post("/gca/search", json={"query": "test", "scope": "Operations"})
        mock_collection.query.assert_called_with(
            query_embeddings=[[0.1] * 768],
            n_results=10,
            include=["documents", "metadatas", "distances"],
            where={"tier": "Operations"}
        )
        
        # Search All
        client.post("/gca/search", json={"query": "test", "scope": "All"})
        mock_collection.query.assert_called_with(
            query_embeddings=[[0.1] * 768],
            n_results=10,
            include=["documents", "metadatas", "distances"],
            where=None
        )
