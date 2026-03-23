"""
Geode Six — AI Router
FastAPI application that routes prompts to the correct Ollama model.

Routing logic:
  - image_path provided → LLaVA (vision)
  - biomedical keywords → BioMistral
  - sensitive=true → Dolphin-Mistral (uncensored)
  - default → Llama 3.1

v2: Added /gca/codes and /gca/folder/create endpoints.
"""

import json
import logging
import os
import re
import time
import base64
from datetime import datetime
from pathlib import Path

import httpx
import psutil
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LOG_PATH = os.getenv("LOG_PATH", "/mnt/nvme/logs")
RAM_THRESHOLD_MB = int(os.getenv("RAM_THRESHOLD_MB", "1024"))
DEFAULT_USER = os.getenv("DEFAULT_USER", "admin")

# Model names (built via build_modelfiles.sh)
MODEL_LLAMA = "geode-llama31"
MODEL_DOLPHIN = "geode-dolphin"
MODEL_BIOMISTRAL = "geode-biomistral"
MODEL_LLAVA = "geode-llava"

# Biomedical routing keywords
BIO_KEYWORDS = [
    "biomass", "pubmed", "biotech", "conversion", "enzyme", "fermentation",
    "biofuel", "cellulose", "lignin", "biomedical", "clinical", "pathology",
    "genomic", "pharmaceutical", "molecular", "protein", "metabolism",
]

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs(LOG_PATH, exist_ok=True)

# File logger for structured request logs
request_logger = logging.getLogger("geode.requests")
request_logger.setLevel(logging.INFO)
log_file = os.path.join(LOG_PATH, "router.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("%(message)s"))
request_logger.addHandler(file_handler)

# Console logger
app_logger = logging.getLogger("geode.app")
app_logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
app_logger.addHandler(console_handler)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Geode Six Router", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include GCA sub-routers
try:
    from gca.intake import router as intake_router
    app.include_router(intake_router)
except ImportError:
    pass

try:
    from gca.search import router as search_router
    app.include_router(search_router)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    prompt: str
    user: str = DEFAULT_USER
    sensitive: bool = False
    image_path: Optional[str] = None


class QueryResponse(BaseModel):
    response: str
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int


class HealthResponse(BaseModel):
    status: str
    models: dict
    ram_available_mb: int
    ram_total_mb: int
    uptime_seconds: float


class FolderCreateRequest(BaseModel):
    name: str
    code: str
    tier: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_start_time = time.time()


def get_available_ram_mb() -> int:
    """Return available system RAM in MB."""
    mem = psutil.virtual_memory()
    return int(mem.available / (1024 * 1024))


def select_model(prompt: str, sensitive: bool, image_path: Optional[str]) -> str:
    """Route to the correct model based on request parameters."""
    # 1. Image → LLaVA
    if image_path:
        return MODEL_LLAVA

    # 2. Biomedical keywords → BioMistral
    prompt_lower = prompt.lower()
    if any(keyword in prompt_lower for keyword in BIO_KEYWORDS):
        return MODEL_BIOMISTRAL

    # 3. Sensitive → Dolphin
    if sensitive:
        return MODEL_DOLPHIN

    # 4. Default → Llama 3.1
    return MODEL_LLAMA


async def check_model_available(model: str) -> bool:
    """Check if a model is available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                model_names = [m["name"] for m in data.get("models", [])]
                # Check for exact match or prefix match (ollama sometimes adds :latest)
                return any(
                    m == model or m.startswith(f"{model}:") for m in model_names
                )
    except Exception:
        pass
    return False


async def query_ollama(
    model: str, prompt: str, image_path: Optional[str] = None
) -> dict:
    """Send a generation request to Ollama and return the response."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    # If image_path provided, encode and attach for LLaVA
    if image_path and os.path.isfile(image_path):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload["images"] = [img_b64]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()


def log_request(
    user: str,
    model: str,
    prompt: str,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
):
    """Log a structured JSON record for every request."""
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user,
        "model": model,
        "prompt_preview": prompt[:100],
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    request_logger.info(json.dumps(record))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health():
    """Return model availability and system memory info."""
    models = {}
    for name in [MODEL_LLAMA, MODEL_DOLPHIN, MODEL_BIOMISTRAL, MODEL_LLAVA]:
        models[name] = await check_model_available(name)

    ram = psutil.virtual_memory()
    return HealthResponse(
        status="ok",
        models=models,
        ram_available_mb=int(ram.available / (1024 * 1024)),
        ram_total_mb=int(ram.total / (1024 * 1024)),
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Route a prompt to the correct model and return the response."""
    # RAM guard
    available_ram = get_available_ram_mb()
    if available_ram < RAM_THRESHOLD_MB:
        app_logger.warning(
            f"Low RAM: {available_ram}MB available (threshold: {RAM_THRESHOLD_MB}MB)"
        )
        raise HTTPException(
            status_code=503,
            detail="System is busy, please try again in a moment.",
        )

    # Select model
    model = select_model(req.prompt, req.sensitive, req.image_path)
    app_logger.info(
        f"Routing query from {req.user} to {model} "
        f"(sensitive={req.sensitive}, image={'yes' if req.image_path else 'no'})"
    )

    # Query Ollama
    start = time.time()
    try:
        result = await query_ollama(model, req.prompt, req.image_path)
    except httpx.HTTPStatusError as e:
        app_logger.error(f"Ollama error: {e.response.status_code} — {e.response.text}")
        raise HTTPException(status_code=502, detail="Model backend error.")
    except httpx.ConnectError:
        app_logger.error("Cannot connect to Ollama")
        raise HTTPException(
            status_code=502, detail="Cannot connect to Ollama. Is it running?"
        )
    except Exception as e:
        app_logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

    latency_ms = int((time.time() - start) * 1000)

    response_text = result.get("response", "")
    tokens_in = result.get("prompt_eval_count", 0)
    tokens_out = result.get("eval_count", 0)

    # Log the request
    log_request(req.user, model, req.prompt, latency_ms, tokens_in, tokens_out)

    return QueryResponse(
        response=response_text,
        model=model,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


# ---------------------------------------------------------------------------
# File download endpoint
# ---------------------------------------------------------------------------
GCA_ROOT = os.getenv("GCA_ROOT", "/mnt/nvme/gca")


@app.get("/gca/download")
async def download_file(path: str):
    """Download a file from GCA storage.

    Security: only serves files under GCA_ROOT. Rejects path traversal.
    """
    from fastapi.responses import FileResponse

    # Resolve both paths to catch traversal attacks (e.g., ../../etc/passwd)
    gca_root_resolved = os.path.realpath(GCA_ROOT)
    requested_path_resolved = os.path.realpath(path)

    # Validate path is within GCA_ROOT
    if not requested_path_resolved.startswith(gca_root_resolved):
        raise HTTPException(
            status_code=403,
            detail="Access denied. You can only download files from the GCA archive.",
        )

    # Check file exists
    if not os.path.isfile(requested_path_resolved):
        raise HTTPException(
            status_code=404,
            detail="File not found on this server.",
        )

    filename = os.path.basename(requested_path_resolved)
    return FileResponse(
        path=requested_path_resolved,
        filename=filename,
        media_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# GCA Codes endpoint (v2)
# ---------------------------------------------------------------------------


@app.get("/gca/codes")
async def get_codes():
    """Return full contents of codes.json for UI dropdown population."""
    from gca.codes import load_codes
    return load_codes()


# ---------------------------------------------------------------------------
# GCA Folder Create endpoint (v2)
# ---------------------------------------------------------------------------


@app.post("/gca/folder/create")
async def create_folder(req: FolderCreateRequest):
    """Create a new project/operation folder.

    Validates code format, creates folder on disk, updates codes.json.
    """
    from gca.codes import add_code, load_codes

    # Validate code: 2-4 uppercase letters
    code = req.code.upper().strip()
    if not re.match(r'^[A-Z]{2,4}$', code):
        raise HTTPException(
            status_code=400,
            detail="Code must be 2-4 uppercase letters.",
        )

    # Validate tier
    if req.tier not in ("Projects", "Operations"):
        raise HTTPException(
            status_code=400,
            detail="Tier must be 'Projects' or 'Operations'.",
        )

    # Validate name
    name = req.name.strip()
    if not name:
        raise HTTPException(
            status_code=400,
            detail="Folder name cannot be empty.",
        )

    # Check if code already exists
    codes = load_codes()
    all_existing = {}
    all_existing.update(codes.get("Projects", {}))
    all_existing.update(codes.get("Operations", {}))
    if code in all_existing:
        raise HTTPException(
            status_code=409,
            detail=f"Code '{code}' is already taken.",
        )

    # Create folder and update codes.json
    try:
        updated_codes = add_code(code, name, req.tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    app_logger.info(f"Created new folder: {req.tier}/{code} — {name}")
    return updated_codes


# ---------------------------------------------------------------------------
# Mount static UI files
# ---------------------------------------------------------------------------
ui_dir = Path(__file__).parent.parent / "ui"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    from fastapi.responses import RedirectResponse

    @app.get("/")
    async def root():
        """Redirect root to web UI."""
        return RedirectResponse(url="/ui/")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
