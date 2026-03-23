#!/usr/bin/env python3
"""
Geode Six — Migration to v2 Two-Tier Structure

Migrates from flat GCA_ROOT/[code]/ to GCA_ROOT/[tier]/[code]/ layout.
- Writes codes.json
- Creates tier/code folders
- Moves files from old flat folders to new two-tier folders
- Drops and rebuilds Chroma index
- Validates all files present
- Prints summary

Usage:
    python scripts/migrate_to_v2.py
"""

import asyncio
import json
import logging
import os
import shutil
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from gca.codes import (
    GCA_ROOT,
    CODES_FILE,
    ensure_codes_file,
    ensure_folder_structure,
    load_codes,
    tier_for_code,
)

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
        logging.FileHandler(os.path.join(LOG_PATH, "migrate_v2.log")),
    ],
)
logger = logging.getLogger("geode.migrate")

# ---------------------------------------------------------------------------
# Old code → new tier mapping
# ---------------------------------------------------------------------------
# Codes that existed in the v1 flat structure and where they belong now
OLD_CODE_TIER_MAP = {
    "GEO": "Projects",
    "CMP": "Projects",
    "PR1": "Projects",
    "PR2": "Projects",
    "PR3": "Projects",
    "SYS": "Operations",  # SYS → OPS folder
    "HR": "Operations",   # HR stays HR
}

# Old code → new code remap (for codes that changed)
OLD_CODE_REMAP = {
    "SYS": "OPS",  # SYS was Operations, now OPS is the folder
}


async def migrate():
    """Run the full v2 migration."""
    logger.info("=" * 60)
    logger.info("Geode Six — Migration to v2 Two-Tier Structure")
    logger.info("=" * 60)
    logger.info(f"GCA_ROOT: {GCA_ROOT}")

    stats = {
        "files_moved": 0,
        "files_indexed": 0,
        "errors": 0,
        "error_files": [],
    }

    # Step 1: Write codes.json
    logger.info("\n--- Step 1: Writing codes.json ---")
    codes = ensure_codes_file()
    logger.info(f"codes.json written to {CODES_FILE}")
    logger.info(f"  Projects: {list(codes.get('Projects', {}).keys())}")
    logger.info(f"  Operations: {list(codes.get('Operations', {}).keys())}")

    # Step 2: Create folder structure
    logger.info("\n--- Step 2: Creating folder structure ---")
    ensure_folder_structure()
    logger.info("All tier/code folders created.")

    # Step 3: Move files from old flat structure
    logger.info("\n--- Step 3: Moving files from old structure ---")

    for old_code, new_tier in OLD_CODE_TIER_MAP.items():
        old_path = os.path.join(GCA_ROOT, old_code)
        if not os.path.isdir(old_path):
            logger.info(f"  {old_code}/ — not found, skipping")
            continue

        # Check if this is already inside a tier folder (skip if so)
        parent_dir = os.path.basename(os.path.dirname(old_path))
        if parent_dir in ("Projects", "Operations"):
            logger.info(f"  {old_code}/ — already in tier folder, skipping")
            continue

        new_code = OLD_CODE_REMAP.get(old_code, old_code)
        new_path = os.path.join(GCA_ROOT, new_tier, new_code)
        os.makedirs(new_path, exist_ok=True)

        files = [f for f in os.listdir(old_path) if os.path.isfile(os.path.join(old_path, f))]
        if not files:
            logger.info(f"  {old_code}/ — empty, skipping")
            continue

        logger.info(f"  {old_code}/ → {new_tier}/{new_code}/ ({len(files)} files)")

        for filename in files:
            src = os.path.join(old_path, filename)
            dst = os.path.join(new_path, filename)
            try:
                # If old code was remapped, rename files if they start with old code
                if old_code != new_code and filename.startswith(f"{old_code}_"):
                    new_filename = f"{new_code}_{filename[len(old_code) + 1:]}"
                    dst = os.path.join(new_path, new_filename)
                    logger.info(f"    {filename} → {new_filename}")
                else:
                    logger.info(f"    {filename}")

                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                else:
                    logger.info(f"    (already exists at destination, skipping)")
                stats["files_moved"] += 1
            except Exception as e:
                logger.error(f"    ERROR moving {filename}: {e}")
                stats["errors"] += 1
                stats["error_files"].append({"file": filename, "error": str(e)})

    # Step 4: Drop existing Chroma index
    logger.info("\n--- Step 4: Dropping Chroma index ---")
    try:
        from gca.embed import drop_collection
        drop_collection()
        logger.info("Chroma collection dropped.")
    except Exception as e:
        logger.error(f"Error dropping Chroma collection: {e}")

    # Step 5: Re-index all files
    logger.info("\n--- Step 5: Re-indexing all files ---")
    try:
        from gca.embed import embed_all_files
        count = await embed_all_files()
        stats["files_indexed"] = count
        logger.info(f"Indexed {count} files.")
    except Exception as e:
        logger.error(f"Re-indexing failed: {e}")

    # Step 6: Validate
    logger.info("\n--- Step 6: Validation ---")
    total_files = 0
    for tier in ("Projects", "Operations"):
        tier_path = os.path.join(GCA_ROOT, tier)
        if not os.path.isdir(tier_path):
            continue
        for code_dir in os.listdir(tier_path):
            code_path = os.path.join(tier_path, code_dir)
            if not os.path.isdir(code_path):
                continue
            file_count = len([f for f in os.listdir(code_path) if os.path.isfile(os.path.join(code_path, f))])
            if file_count > 0:
                logger.info(f"  {tier}/{code_dir}: {file_count} files")
            total_files += file_count

    logger.info(f"\nTotal files in new structure: {total_files}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"  Files moved:   {stats['files_moved']}")
    logger.info(f"  Files indexed: {stats['files_indexed']}")
    logger.info(f"  Errors:        {stats['errors']}")

    if stats["error_files"]:
        logger.info("\nErrors:")
        for err in stats["error_files"]:
            logger.info(f"  {err['file']}: {err['error']}")

    logger.info("\n⚠️  Old folders have NOT been deleted.")
    logger.info("    Verify everything looks correct, then manually remove them:")
    for old_code in OLD_CODE_TIER_MAP:
        old_path = os.path.join(GCA_ROOT, old_code)
        parent_dir = os.path.basename(os.path.dirname(old_path))
        if parent_dir not in ("Projects", "Operations") and os.path.isdir(old_path):
            logger.info(f"    rm -rf {old_path}")


def main():
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
