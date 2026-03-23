#!/usr/bin/env python3
"""
Geode Six — One-Time GCA Import Script
Imports existing files from a source folder (e.g., Google Drive download)
into the GCA system with AI naming and Chroma embedding.

v2: Routes files to two-tier structure. Optional --tier flag.

Usage:
    python scripts/import_gca.py --source /path/to/google-drive-download
    python scripts/import_gca.py --source /path/to/files --tier Operations
"""

import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from gca.intake import (
    SUPPORTED_EXTENSIONS,
    ai_suggest_name,
    build_filename,
    extract_metadata_date,
    extract_text_preview,
    resolve_date,
    next_version,
)
from gca.codes import GCA_ROOT, tier_for_code, valid_code, ensure_codes_file

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_PATH = os.getenv("LOG_PATH", "/mnt/nvme/logs")
os.makedirs(LOG_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_PATH, "import.log")),
    ],
)
logger = logging.getLogger("geode.import")


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------
async def import_file(filepath: str, stats: dict, force_tier: str = None):
    """Import a single file into GCA."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        logger.info(f"  SKIP (unsupported type): {filepath}")
        stats["skipped"] += 1
        return

    try:
        original_filename = os.path.basename(filepath)

        # Extract text preview
        text_preview = extract_text_preview(filepath, ext)

        # Extract metadata date
        metadata_date = extract_metadata_date(filepath, ext)

        # Get file ctime
        file_ctime = os.path.getctime(filepath)

        # AI naming
        logger.info(f"  AI naming: {original_filename}")
        suggestion = await ai_suggest_name(text_preview, original_filename, note=None)
        tier = suggestion["tier"]
        project = suggestion["code"]
        type_code = suggestion["type"]
        description = suggestion["description"]

        # Override tier if forced
        if force_tier:
            tier = force_tier

        # Resolve date
        date, date_estimated = resolve_date(None, metadata_date, original_filename, file_ctime)
        if date_estimated:
            logger.info(f"    Date estimated (no date found in file)")

        # Version — imports default to v1.0 (they're existing files)
        version = next_version(tier, project, type_code, description, "1.0")

        # Build filename
        final_filename = build_filename(project, type_code, description, date, version, ext)

        # Ensure tier/project directory
        project_dir = os.path.join(GCA_ROOT, tier, project)
        os.makedirs(project_dir, exist_ok=True)

        # Copy file
        final_path = os.path.join(project_dir, final_filename)

        # Never overwrite
        while os.path.exists(final_path):
            version = next_version(tier, project, type_code, description, version)
            final_filename = build_filename(project, type_code, description, date, version, ext)
            final_path = os.path.join(project_dir, final_filename)

        shutil.copy2(filepath, final_path)
        logger.info(f"  → {tier}/{project}/{final_filename}")

        stats["processed"] += 1
        stats["files"].append({
            "original": original_filename,
            "renamed": final_filename,
            "tier": tier,
            "project": project,
        })

    except Exception as e:
        logger.error(f"  ERROR: {filepath} — {e}")
        stats["errors"] += 1
        stats["error_files"].append({"file": filepath, "error": str(e)})


async def run_import(source_dir: str, force_tier: str = None):
    """Import all files from source directory."""
    if not os.path.isdir(source_dir):
        logger.error(f"Source directory does not exist: {source_dir}")
        sys.exit(1)

    # Ensure codes.json exists
    ensure_codes_file()

    logger.info(f"=== Geode Six GCA Import (v2) ===")
    logger.info(f"Source: {source_dir}")
    logger.info(f"Destination: {GCA_ROOT}")
    if force_tier:
        logger.info(f"Forced tier: {force_tier}")

    # Collect all files
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for fname in files:
            all_files.append(os.path.join(root, fname))

    logger.info(f"Found {len(all_files)} files")

    stats = {
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "files": [],
        "error_files": [],
    }

    for i, filepath in enumerate(all_files, 1):
        logger.info(f"[{i}/{len(all_files)}] {os.path.basename(filepath)}")
        await import_file(filepath, stats, force_tier=force_tier)

    # Run full Chroma embedding
    logger.info("")
    logger.info("=== Running Chroma Embedding Pass ===")
    try:
        from gca.embed import embed_all_files
        await embed_all_files()
        logger.info("Embedding complete.")
    except ImportError:
        logger.warning("Embedding module not available — skipping.")
    except Exception as e:
        logger.error(f"Embedding failed: {e}")

    # Summary
    logger.info("")
    logger.info("=== Import Summary ===")
    logger.info(f"  Files processed: {stats['processed']}")
    logger.info(f"  Files skipped:   {stats['skipped']}")
    logger.info(f"  Errors:          {stats['errors']}")

    if stats["error_files"]:
        logger.info("")
        logger.info("Errors:")
        for err in stats["error_files"]:
            logger.info(f"  {err['file']}: {err['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="Import files into Geode Six GCA (v2 two-tier structure)"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source folder (e.g., /path/to/google-drive-download)",
    )
    parser.add_argument(
        "--tier",
        choices=["Projects", "Operations"],
        default=None,
        help="Force all files in this batch to a specific tier",
    )
    args = parser.parse_args()

    asyncio.run(run_import(args.source, force_tier=args.tier))


if __name__ == "__main__":
    main()
