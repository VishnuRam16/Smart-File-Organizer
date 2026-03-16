"""
file_handler.py
---------------
Core business logic: detect a duplicate resume, archive the existing base
file with a timestamp, then promote the duplicate to the canonical name.

This module is intentionally free of watchdog imports so it can be tested
independently.
"""

import shutil
import time
from pathlib import Path

from config import (
    ARCHIVE_FOLDER,
    DOWNLOAD_SETTLE_INTERVAL,
    DOWNLOAD_TIMEOUT,
    KEYWORD_FILTER,
    TEMP_EXTENSIONS,
    VERSIONS_FOLDER,
    WATCH_FOLDER,
)
from classifier import classify
from utils import build_archive_name, contains_keyword, logger, parse_duplicate, parse_generic_duplicate


# ── Internal helpers ───────────────────────────────────────────────────────

def _ensure_archive_folder() -> Path:
    """Create ARCHIVE_FOLDER (and all parents) if it does not yet exist."""
    ARCHIVE_FOLDER.mkdir(parents=True, exist_ok=True)
    return ARCHIVE_FOLDER


def _is_temp_file(path: Path) -> bool:
    """Return ``True`` for browser in-progress download extensions."""
    return path.suffix.lower() in TEMP_EXTENSIONS


def _wait_for_download_completion(path: Path) -> bool:
    """
    Poll *path* every ``DOWNLOAD_SETTLE_INTERVAL`` seconds until its size
    stops changing (download finished) or ``DOWNLOAD_TIMEOUT`` is exceeded.

    Returns:
        ``True``  — file is stable and ready to process.
        ``False`` — file disappeared or timed out.
    """
    elapsed = 0.0
    previous_size = -1

    while elapsed < DOWNLOAD_TIMEOUT:
        if not path.exists():
            # The file was removed or renamed before we could check it.
            return False

        current_size = path.stat().st_size
        if current_size == previous_size:
            return True  # Size unchanged across two samples → download done

        previous_size = current_size
        time.sleep(DOWNLOAD_SETTLE_INTERVAL)
        elapsed += DOWNLOAD_SETTLE_INTERVAL

    logger.warning("Timed out waiting for download to finish: %s", path.name)
    return False


def _archive_base_file(base_path: Path) -> bool:
    """
    Move *base_path* into ARCHIVE_FOLDER, inserting a timestamp into its name.

    Returns ``True`` on success, ``False`` if the move failed (logged).
    """
    archive_dir = _ensure_archive_folder()
    archive_name = build_archive_name(base_path.stem, base_path.suffix,
                                      source_path=base_path, archive_dir=archive_dir)
    archive_dest = archive_dir / archive_name

    try:
        shutil.move(str(base_path), str(archive_dest))
        logger.info(
            "Archived old resume → %s/%s",
            archive_dir.name,
            archive_name,
        )
        return True
    except OSError as exc:
        logger.error("Failed to archive %s: %s", base_path.name, exc)
        return False


# ── Public API ─────────────────────────────────────────────────────────────

def process_file(path: Path) -> None:
    """
    Evaluate *path* and, if it is a completed duplicate resume download,
    archive the existing base file and rename the duplicate to the base name.

    Decision tree
    ~~~~~~~~~~~~~
    1.  Skip if *path* has a temporary/browser extension.
    2.  Skip if the filename does not contain a configured keyword.
    3.  Skip if the filename does not match the ``Name - Resume (n).pdf`` pattern.
    4.  Wait for the download to finish (size-stable check).
    5.  Archive the existing base file (if present).
    6.  Rename the duplicate to the canonical base name.
    """

    # ── Guard: browser temp files ──────────────────────────────────────────
    if _is_temp_file(path):
        return

    # ── Try duplicate resume handler first ─────────────────────────────────
    if contains_keyword(path.name, KEYWORD_FILTER):
        parsed = parse_duplicate(path.name)
        if parsed is not None:
            _handle_duplicate(path, parsed)
            return

    # ── Fall through to category-based sorting ─────────────────────────────
    _handle_classify(path)


def _handle_duplicate(path: Path, parsed: tuple[str, str]) -> None:
    """Archive old copies and promote the new duplicate to the clean name."""
    base_stem, extension = parsed
    base_filename = f"{base_stem}{extension}"

    VERSIONS_FOLDER.mkdir(parents=True, exist_ok=True)
    base_path = VERSIONS_FOLDER / base_filename

    logger.info("Detected duplicate resume: %s", path.name)

    if not _wait_for_download_completion(path):
        logger.warning(
            "Could not confirm download completion for: %s — skipping.",
            path.name,
        )
        return

    if not path.exists():
        logger.warning("File disappeared before processing: %s", path.name)
        return

    # 1. The base file sitting in Downloads
    downloads_base = path.parent / base_filename
    if downloads_base.exists():
        if not _archive_base_file(downloads_base):
            logger.error(
                "Archive step failed for Downloads copy — aborting to avoid data loss."
            )
            return

    # 2. A previous latest in Resume Versions
    if base_path.exists():
        if not _archive_base_file(base_path):
            logger.error(
                "Archive step failed for Versions copy — aborting to avoid data loss."
            )
            return

    try:
        shutil.move(str(path), str(base_path))
        logger.info("Moved new resume → Resume Versions/%s", base_filename)
    except OSError as exc:
        logger.error(
            "Failed to move %s → Resume Versions/%s: %s",
            path.name,
            base_filename,
            exc,
        )


def _handle_classify(path: Path) -> None:
    """Sort *path* into a category subfolder, deduplicating within the category."""
    category = classify(path)
    if category is None:
        return

    if not _wait_for_download_completion(path):
        logger.warning(
            "Could not confirm download completion for: %s — skipping.",
            path.name,
        )
        return

    if not path.exists():
        logger.warning("File disappeared before processing: %s", path.name)
        return

    dest_folder = WATCH_FOLDER / category
    archive_folder = dest_folder / f"{category} Archive"
    dest_folder.mkdir(exist_ok=True)

    # Check if this is an OS-duplicate e.g. "file (1).png"
    parsed = parse_generic_duplicate(path.name)
    if parsed is not None:
        base_stem, extension = parsed
        base_filename = f"{base_stem}{extension}"

        # Archive old base in the category folder if it exists
        existing_base = dest_folder / base_filename
        if existing_base.exists():
            archive_folder.mkdir(exist_ok=True)
            archive_name = build_archive_name(existing_base.stem, existing_base.suffix,
                                              source_path=existing_base, archive_dir=archive_folder)
            archive_dest = archive_folder / archive_name
            try:
                shutil.move(str(existing_base), str(archive_dest))
                logger.info(
                    "Archived → %s/%s",
                    archive_folder.name,
                    archive_name,
                )
            except OSError as exc:
                logger.error("Failed to archive %s: %s", existing_base.name, exc)
                return

        # Also archive the base file if it's still sitting in Downloads
        downloads_base = path.parent / base_filename
        if downloads_base.exists() and downloads_base != path:
            archive_folder.mkdir(exist_ok=True)
            archive_name = build_archive_name(downloads_base.stem, downloads_base.suffix,
                                              source_path=downloads_base, archive_dir=archive_folder)
            archive_dest = archive_folder / archive_name
            try:
                shutil.move(str(downloads_base), str(archive_dest))
                logger.info(
                    "Archived Downloads copy → %s/%s",
                    archive_folder.name,
                    archive_name,
                )
            except OSError as exc:
                logger.error("Failed to archive %s: %s", downloads_base.name, exc)
                return

        # Move the new duplicate with the clean base name
        dest = dest_folder / base_filename
        try:
            shutil.move(str(path), str(dest))
            logger.info("Sorted %s → %s/%s", path.name, category, base_filename)
        except OSError as exc:
            logger.error("Failed to sort %s → %s/: %s", path.name, category, exc)
    else:
        # Not a duplicate — just move it
        dest = dest_folder / path.name
        if dest.exists():
            logger.info("%s already exists in %s/ — skipping.", path.name, category)
            return
        try:
            shutil.move(str(path), str(dest))
            logger.info("Sorted %s → %s/", path.name, category)
        except OSError as exc:
            logger.error("Failed to sort %s → %s/: %s", path.name, category, exc)
