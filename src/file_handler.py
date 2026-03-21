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
from utils import (
    build_archive_name,
    contains_keyword,
    files_identical,
    logger,
    parse_duplicate,
    parse_duplicate_candidate,
)


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


def _next_variant_destination(dest_folder: Path, stem: str, extension: str) -> Path:
    """Return the next available ``<stem>_variant_<n><extension>`` path."""
    counter = 2
    while True:
        candidate = dest_folder / f"{stem}_variant_{counter}{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def _same_canonical_key(parsed: tuple[str, str] | None,
                        base_stem: str,
                        extension: str) -> bool:
    """Case-insensitive comparison of canonical ``(stem, extension)`` tuples."""
    if parsed is None:
        return False
    stem, ext = parsed
    return stem.lower() == base_stem.lower() and ext.lower() == extension.lower()


def _find_existing_duplicate_candidate(path: Path,
                                       dest_folder: Path,
                                       base_stem: str,
                                       extension: str,
                                       base_filename: str) -> Path | None:
    """
    Find an existing file in this duplicate family.

    Priority:
      1. Canonical file already in category folder
      2. Exact canonical filename in watch root (case-insensitive)
      3. Any watch-root file that normalizes to the same canonical key
    """
    canonical_dest = dest_folder / base_filename
    if canonical_dest.exists():
        return canonical_dest

    for sibling in path.parent.iterdir():
        if not sibling.is_file() or sibling == path:
            continue
        if sibling.name.lower() == base_filename.lower():
            return sibling

    for sibling in path.parent.iterdir():
        if not sibling.is_file() or sibling == path:
            continue
        if _same_canonical_key(parse_duplicate_candidate(sibling.name), base_stem, extension):
            return sibling

    return None


# ── Public API ─────────────────────────────────────────────────────────────

def process_file(path: Path, *, target_root: Path | None = None) -> None:
    """
    Evaluate *path* and sort it into the appropriate category subfolder.

    Parameters
    ----------
    target_root : Path | None
        Root folder where category subfolders are created.
        Defaults to ``WATCH_FOLDER`` when ``None``.
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
    _handle_classify(path, target_root=target_root)


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


def _handle_classify(path: Path, *, target_root: Path | None = None) -> None:
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

    root = target_root if target_root is not None else WATCH_FOLDER
    dest_folder = root / category
    archive_folder = dest_folder / f"{category} Archive"
    dest_folder.mkdir(exist_ok=True)

    # Check if this is a duplicate candidate (OS (n), copy, v1, etc.)
    parsed = parse_duplicate_candidate(path.name)
    if parsed is not None:
        base_stem, extension = parsed
        base_filename = f"{base_stem}{extension}"
        canonical_dest = dest_folder / base_filename
        existing = _find_existing_duplicate_candidate(
            path=path,
            dest_folder=dest_folder,
            base_stem=base_stem,
            extension=extension,
            base_filename=base_filename,
        )

        # No prior file in this family -> this becomes canonical latest
        if existing is None:
            try:
                shutil.move(str(path), str(canonical_dest))
                logger.info("Sorted %s → %s/%s", path.name, category, base_filename)
            except OSError as exc:
                logger.error("Failed to sort %s → %s/: %s", path.name, category, exc)
            return

        # True duplicate (same bytes) -> archive old, promote new to canonical name
        if files_identical(path, existing):
            archive_folder.mkdir(exist_ok=True)
            archive_name = build_archive_name(
                existing.stem,
                existing.suffix,
                source_path=existing,
                archive_dir=archive_folder,
            )
            archive_dest = archive_folder / archive_name
            try:
                shutil.move(str(existing), str(archive_dest))
                logger.info("Archived → %s/%s", archive_folder.name, archive_name)
            except OSError as exc:
                logger.error("Failed to archive %s: %s", existing.name, exc)
                return

            try:
                shutil.move(str(path), str(canonical_dest))
                logger.info("Sorted %s → %s/%s", path.name, category, base_filename)
            except OSError as exc:
                logger.error("Failed to sort %s → %s/: %s", path.name, category, exc)
            return

        # Same canonical family but different content -> keep both as variants
        if existing != canonical_dest and not canonical_dest.exists():
            try:
                shutil.move(str(existing), str(canonical_dest))
                logger.info("Sorted base copy → %s/%s", category, base_filename)
            except OSError as exc:
                logger.error("Failed to move base %s → %s/: %s", existing.name, category, exc)
                return

        archive_folder.mkdir(exist_ok=True)
        variant_dest = _next_variant_destination(archive_folder, base_stem, extension)
        try:
            shutil.move(str(path), str(variant_dest))
            logger.info(
                "Name collision with different content → %s Archive/%s",
                category,
                variant_dest.name,
            )
        except OSError as exc:
            logger.error("Failed to keep variant %s: %s", path.name, exc)
        return
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


def sort_folder_once(folder: Path) -> int:
    """
    Batch-process every top-level file in *folder*.

    Category subfolders are created inside *folder* itself.
    Returns the number of files processed.
    """
    folder = Path(folder)
    if not folder.is_dir():
        logger.error("sort_folder_once: not a directory: %s", folder)
        return 0

    files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.name != ".DS_Store" and not _is_temp_file(f)
    )

    count = 0
    for f in files:
        if f.exists():
            process_file(f, target_root=folder)
            count += 1

    logger.info("sort_folder_once: processed %d files in %s", count, folder)
    return count
