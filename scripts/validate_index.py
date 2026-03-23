#!/usr/bin/env python3
"""
Geode Six — Index Validation Script
Checks every Chroma entry against actual files on disk.
Removes orphaned entries where the file no longer exists.

Run weekly via cron:
    0 2 * * 0 /usr/bin/python3 /path/to/geode-six/scripts/validate_index.py
"""

import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

LOG_PATH = os.getenv("LOG_PATH", "/mnt/nvme/logs")
os.makedirs(LOG_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_PATH, "index_validation.log")),
    ],
)
logger = logging.getLogger("geode.validate")


def validate_index():
    """Validate all Chroma entries against files on disk."""
    logger.info("=" * 60)
    logger.info(f"Index Validation Run — {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        from gca.embed import _get_collection
    except ImportError:
        logger.error("Embedding module not available")
        return

    collection = _get_collection()

    # Get all entries
    all_entries = collection.get(include=["metadatas"])

    total = len(all_entries["ids"]) if all_entries["ids"] else 0
    removed = 0
    errors = 0
    orphan_ids = []

    logger.info(f"Total Chroma entries: {total}")

    if total == 0:
        logger.info("No entries to validate.")
        return

    for i, entry_id in enumerate(all_entries["ids"]):
        metadata = all_entries["metadatas"][i] if all_entries["metadatas"] else {}
        file_path = metadata.get("file_path", "")

        if not file_path:
            logger.warning(f"  Entry {entry_id}: no file_path in metadata")
            orphan_ids.append(entry_id)
            removed += 1
            continue

        if not os.path.exists(file_path):
            logger.info(f"  ORPHAN: {entry_id} → {file_path} (file not found)")
            orphan_ids.append(entry_id)
            removed += 1

    # Remove orphans
    if orphan_ids:
        try:
            collection.delete(ids=orphan_ids)
            logger.info(f"Removed {len(orphan_ids)} orphaned entries")
        except Exception as e:
            logger.error(f"Failed to remove orphans: {e}")
            errors += 1

    # Summary
    logger.info("")
    logger.info("--- Validation Summary ---")
    logger.info(f"  Total checked: {total}")
    logger.info(f"  Total removed: {removed}")
    logger.info(f"  Errors:        {errors}")
    logger.info(f"  Remaining:     {total - removed}")
    logger.info("=" * 60)


if __name__ == "__main__":
    validate_index()
