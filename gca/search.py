"""
Geode Six — GCA Search and Browse Module
Semantic search via Chroma + optional AI synthesis via Llama 3.1.
Browse endpoint for listing files with filters.

v2: Tier-aware search/browse, scope filtering, dynamic code resolution.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GCA_ROOT = os.getenv("GCA_ROOT", "/mnt/nvme/gca")
LOG_PATH = os.getenv("LOG_PATH", "/mnt/nvme/logs")

SEARCH_MODEL = "geode-llama31"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
search_logger = logging.getLogger("geode.search")
search_logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    synthesize: bool = False
    scope: str = "All"  # "All", "Projects", "Operations"


class SearchResult(BaseModel):
    filename: str
    path: str
    tier: str
    project: str
    type: str
    score: float
    excerpt: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    summary: Optional[str] = None


class BrowseFile(BaseModel):
    filename: str
    path: str
    tier: str
    project: str
    type: str
    date: str
    version: str


class BrowseResponse(BaseModel):
    files: list[BrowseFile]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_filename(filename: str) -> dict:
    """Parse GCA metadata from filename. Expected: CODE_TYPE_Desc_DATE_vX.Y.ext"""
    parts = filename.split("_")
    result = {
        "filename": filename,
        "project": "",
        "type": "",
        "description": "",
        "date": "",
        "version": "",
    }
    if len(parts) >= 5:
        result["project"] = parts[0]
        result["type"] = parts[1]
        result["description"] = parts[2]
        # Date
        date_match = re.search(r"_(\d{8})_", filename)
        if date_match:
            result["date"] = date_match.group(1)
        # Version
        version_match = re.search(r"_v(\d+\.\d+)", filename)
        if version_match:
            result["version"] = version_match.group(1)
    return result


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


@router.post("/gca/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Natural language search over GCA documents."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        from gca.embed import get_embedding, _get_collection
    except ImportError:
        raise HTTPException(
            status_code=503, detail="Search module not available."
        )

    # Get query embedding
    query_embedding = await get_embedding(req.query)

    # Search Chroma — apply tier filter if scope is set
    collection = _get_collection()

    where_filter = None
    if req.scope in ("Projects", "Operations"):
        where_filter = {"tier": req.scope}

    chroma_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["documents", "metadatas", "distances"],
        where=where_filter,
    )

    # Build results (deduplicate by filename)
    seen_files = set()
    results = []

    if chroma_results and chroma_results["ids"] and chroma_results["ids"][0]:
        for i, doc_id in enumerate(chroma_results["ids"][0]):
            metadata = chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {}
            document = chroma_results["documents"][0][i] if chroma_results["documents"] else ""
            distance = chroma_results["distances"][0][i] if chroma_results["distances"] else 1.0

            filename = metadata.get("filename", "unknown")
            if filename in seen_files:
                continue
            seen_files.add(filename)

            # Convert distance to relevance score (cosine distance → score)
            score = round(max(0, 1 - distance), 2)

            # Excerpt: first 200 chars of the matching chunk
            excerpt = document[:200].strip() if document else ""

            results.append(SearchResult(
                filename=filename,
                path=metadata.get("file_path", ""),
                tier=metadata.get("tier", ""),
                project=metadata.get("code", metadata.get("project", "")),
                type=metadata.get("type", ""),
                score=score,
                excerpt=excerpt,
            ))

    search_logger.info(
        f"Search: '{req.query}' → {len(results)} results "
        f"(synthesize={req.synthesize}, scope={req.scope})"
    )

    # Optional synthesis
    summary = None
    if req.synthesize and results:
        summary = await _synthesize_results(req.query, results)

    return SearchResponse(results=results, summary=summary)


async def _synthesize_results(query: str, results: list[SearchResult]) -> str:
    """Pass search results to Llama 3.1 for a plain-English summary."""
    results_text = "\n".join(
        f"- {r.filename} (project: {r.project}, score: {r.score}): {r.excerpt}"
        for r in results[:5]
    )

    prompt = (
        f"Based on these search results for the query '{query}', "
        f"provide a brief plain-English summary of what was found:\n\n"
        f"{results_text}\n\n"
        f"Summarize the key findings in 2-3 sentences."
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": SEARCH_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as e:
        search_logger.error(f"Synthesis failed: {e}")
        return "Summary generation failed. Please review the results below."


# ---------------------------------------------------------------------------
# Browse endpoint
# ---------------------------------------------------------------------------


@router.get("/gca/browse", response_model=BrowseResponse)
async def browse(
    project: Optional[str] = Query(None, description="Filter by project/operation code"),
    type: Optional[str] = Query(None, alias="type", description="Filter by type code"),
    tier: Optional[str] = Query(None, description="Filter by tier: Projects or Operations"),
    sort: str = Query("date_desc", description="Sort: date_desc, date_asc, project_asc"),
):
    """List all files in GCA with optional filters and sorting.
    Iterates two-tier structure: GCA_ROOT/[tier]/[code]/[files].
    """
    files = []
    gca_root = os.getenv("GCA_ROOT", GCA_ROOT)

    if not os.path.isdir(gca_root):
        return BrowseResponse(files=[], total=0)

    # Determine which tiers to scan
    tiers_to_scan = ["Projects", "Operations"]
    if tier and tier in ("Projects", "Operations"):
        tiers_to_scan = [tier]

    for tier_name in tiers_to_scan:
        tier_path = os.path.join(gca_root, tier_name)
        if not os.path.isdir(tier_path):
            continue

        for code_dir in os.listdir(tier_path):
            code_path = os.path.join(tier_path, code_dir)
            if not os.path.isdir(code_path):
                continue

            # Filter by project/operation code
            if project and code_dir.upper() != project.upper():
                continue

            for filename in os.listdir(code_path):
                filepath = os.path.join(code_path, filename)
                if not os.path.isfile(filepath):
                    continue

                parsed = _parse_filename(filename)

                # Filter by type
                if type and parsed["type"].upper() != type.upper():
                    continue

                files.append(BrowseFile(
                    filename=filename,
                    path=filepath,
                    tier=tier_name,
                    project=parsed["project"],
                    type=parsed["type"],
                    date=parsed["date"],
                    version=parsed["version"],
                ))

    # Sort
    if sort == "date_desc":
        files.sort(key=lambda f: f.date, reverse=True)
    elif sort == "date_asc":
        files.sort(key=lambda f: f.date)
    elif sort == "project_asc":
        files.sort(key=lambda f: f.project)

    return BrowseResponse(files=files, total=len(files))
