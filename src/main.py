"""
main.py
-------
Entry point for Smart File Organizer.

Usage:
    python src/main.py
"""

import sys
from pathlib import Path

# Make the package importable when run as a script from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ARCHIVE_FOLDER, VERSIONS_FOLDER, WATCH_FOLDER
from utils import logger
from watcher import run_watcher


def main() -> None:
    logger.info("Smart File Organizer starting up...")
    logger.info("  Watch folder   : %s", WATCH_FOLDER)
    logger.info("  Versions folder: %s", VERSIONS_FOLDER)
    logger.info("  Archive folder : %s", ARCHIVE_FOLDER)

    # Create both folders on first run
    VERSIONS_FOLDER.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FOLDER.mkdir(parents=True, exist_ok=True)

    run_watcher(WATCH_FOLDER)


if __name__ == "__main__":
    main()
