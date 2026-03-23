"""
Geode Six — Dynamic Code Management
Reads/writes codes.json, resolves tier for a given code, builds AI naming prompt.
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

GCA_ROOT = os.getenv("GCA_ROOT", "/mnt/nvme/gca")
CODES_FILE = os.path.join(GCA_ROOT, "codes.json")

# Type codes (document type, NOT folder codes)
TYPE_CODES = [
    "AGD", "SUM", "OPS", "BRF", "TSR", "VIS", "REQ",
    "IDX", "FRM", "RPT", "BIO", "AGR", "CON",
]

# Default codes written on first run if codes.json doesn't exist
_DEFAULT_CODES = {
    "Projects": {
        "PR5": "Project Epsilon",
        "PR6": "Project Zeta",
        "GEO": "Geode Solutions",
        "PR4": "Project Delta",
        "PR3": "Project Gamma",
        "PR1": "Project Alpha",
        "CMP": "[YOUR_COMPANY_NAME]",
        "PR2": "Project Beta",
        "VRT": "Vertigrow",
    },
    "Operations": {
        "ARC": "Earlier Projects / Archive",
        "CON": "Contacts / Bullpen",
        "HR": "HR / People",
        "LDS": "Leads",
        "MTG": "Meetings / Agendas / Transcripts",
        "OPS": "Ops Resources",
        "TPL": "Templates",
    },
}


# ---------------------------------------------------------------------------
# Read / write helpers
# ---------------------------------------------------------------------------

def load_codes() -> dict:
    """Load codes.json. Returns {"Projects": {...}, "Operations": {...}}."""
    if os.path.isfile(CODES_FILE):
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return _DEFAULT_CODES.copy()


def save_codes(codes: dict) -> None:
    """Persist codes dict back to codes.json."""
    os.makedirs(os.path.dirname(CODES_FILE), exist_ok=True)
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, indent=2, ensure_ascii=False)


def ensure_codes_file() -> dict:
    """Create codes.json with defaults if it doesn't exist. Returns codes."""
    if not os.path.isfile(CODES_FILE):
        codes = _DEFAULT_CODES.copy()
        save_codes(codes)
        return codes
    return load_codes()


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def all_codes() -> list[tuple[str, str, str]]:
    """Return flat list of (code, label, tier) tuples."""
    codes = load_codes()
    result = []
    for tier in ("Projects", "Operations"):
        for code, label in codes.get(tier, {}).items():
            result.append((code, label, tier))
    return result


def valid_code(code: str) -> bool:
    """Return True if code exists in any tier."""
    codes = load_codes()
    for tier_codes in codes.values():
        if code in tier_codes:
            return True
    return False


def tier_for_code(code: str) -> Optional[str]:
    """Return 'Projects' or 'Operations' for a given code, or None."""
    codes = load_codes()
    for tier, tier_codes in codes.items():
        if code in tier_codes:
            return tier
    return None


def all_folder_codes() -> list[str]:
    """Return flat list of all folder codes."""
    codes = load_codes()
    result = []
    for tier_codes in codes.values():
        result.extend(tier_codes.keys())
    return result


# ---------------------------------------------------------------------------
# Folder management
# ---------------------------------------------------------------------------

def add_code(code: str, label: str, tier: str) -> dict:
    """Add a new code to codes.json and create the folder on disk.
    Returns the updated full codes dict.
    """
    codes = load_codes()
    if tier not in ("Projects", "Operations"):
        raise ValueError(f"Invalid tier: {tier}")
    if code in codes.get("Projects", {}) or code in codes.get("Operations", {}):
        raise ValueError(f"Code already exists: {code}")

    codes[tier][code] = label
    save_codes(codes)

    # Create folder
    folder = os.path.join(GCA_ROOT, tier, code)
    os.makedirs(folder, exist_ok=True)

    return codes


def ensure_folder_structure() -> None:
    """Create all tier/code folders on disk from codes.json."""
    codes = load_codes()
    for tier in ("Projects", "Operations"):
        for code in codes.get(tier, {}):
            path = os.path.join(GCA_ROOT, tier, code)
            os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------
# AI naming prompt builder
# ---------------------------------------------------------------------------

def build_naming_prompt() -> str:
    """Build the AI naming prompt dynamically from codes.json."""
    codes = load_codes()

    project_lines = []
    for code, label in codes.get("Projects", {}).items():
        extra = ""
        if code == "VRT":
            extra = " (vertical growing / controlled environment agriculture project)"
        project_lines.append(f"  {code} — {label}{extra}")

    ops_lines = []
    for code, label in codes.get("Operations", {}).items():
        ops_lines.append(f"  {code} — {label}")

    type_list = ", ".join(TYPE_CODES)

    prompt = f"""You are a file naming assistant for Geode Solutions. Given a document, assign:

TIER: either "Projects" or "Operations"
  Projects — work tied to a specific project or client
  Operations — internal ops, templates, HR, meetings, contacts, archives

PROJECT/OPERATION CODE (pick ONE from the correct tier):

Projects tier:
{chr(10).join(project_lines)}

Operations tier:
{chr(10).join(ops_lines)}

TYPE code (one of: {type_list})
  Note: CON as a TYPE code means "Contacts document type" — this is different from
  CON as an Operations folder code which means "Contacts / Bullpen folder".
  These are two separate concepts.

Description: 3-4 words, CamelCase, no spaces, describes what this specific document is about

If the user provides a hint note, use it to inform your decision.
Respond ONLY with valid JSON: {{"tier": "Projects", "code": "XXX", "type": "XXX", "description": "XxxXxx"}}
No explanation. No markdown. JSON only."""

    return prompt
