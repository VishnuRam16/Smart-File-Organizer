"""
utils.py
--------
Shared utilities: structured logging, timestamp generation, and filename
pattern parsing.  No business logic lives here.
"""

import logging
import re
from datetime import datetime
from pathlib import Path


# ── Logging ────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """Configure and return the application-wide logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger("smart_file_organizer")


# Module-level logger consumed by every other module via:
#   from utils import logger
logger = setup_logging()


# ── Timestamp ──────────────────────────────────────────────────────────────

def current_timestamp() -> str:
    """Return a filesystem-safe timestamp: ``YYYY-MM-DD_HH-MM-SS``."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


# ── Filename pattern helpers ───────────────────────────────────────────────

# Matches any file with an OS-appended duplicate suffix: "(n)"
# Examples:
#   "Sam Smith - Resume (1).pdf"
#   "FN_LN_Resume (2).docx"
#   "my CV (3).pdf"
#
# Groups:
#   1 → base stem   e.g. "Sam Smith - Resume", "FN_LN_Resume"
#   2 → copy index  e.g. "1"
#   3 → extension   e.g. ".pdf" or ".docx"
#
# The keyword filter in file_handler.py ensures only resume/CV files
# are processed. This regex is intentionally broad.
_DUPLICATE_RE = re.compile(
    r"^(.+?)\s*\((\d+)\)(\.(?:pdf|docx))$",
    re.IGNORECASE,
)

# Broader pattern: any file with OS-appended (n) suffix, any extension
_GENERIC_DUPLICATE_RE = re.compile(
    r"^(.+?)\s*\((\d+)\)(\.\w+)$",
    re.IGNORECASE,
)


def parse_duplicate(filename: str) -> tuple[str, str] | None:
    """
    If *filename* has an OS-appended ``(n)`` suffix return ``(base_stem, extension)``,
    otherwise return ``None``.

    Examples::

        parse_duplicate("Sam Smith - Resume (1).pdf")
        # → ("Sam Smith - Resume", ".pdf")

        parse_duplicate("FN_LN_Resume (2).docx")
        # → ("FN_LN_Resume", ".docx")

        parse_duplicate("Sam Smith - Resume.pdf")
        # → None  (already the canonical name)

        parse_duplicate("budget.xlsx")
        # → None  (not pdf/docx)
    """
    m = _DUPLICATE_RE.match(filename)
    if m:
        return m.group(1), m.group(3)
    return None


def parse_generic_duplicate(filename: str) -> tuple[str, str] | None:
    """
    Like ``parse_duplicate`` but matches *any* extension.

    Examples::

        parse_generic_duplicate("IMG_1484 (2).png") → ("IMG_1484", ".png")
        parse_generic_duplicate("sample (1).csv")   → ("sample", ".csv")
        parse_generic_duplicate("report.pdf")       → None
    """
    m = _GENERIC_DUPLICATE_RE.match(filename)
    if m:
        return m.group(1), m.group(3)
    return None


def contains_keyword(filename: str, keywords: list[str]) -> bool:
    """
    Return ``True`` if *filename* contains at least one entry from *keywords*
    (comparison is case-insensitive).
    """
    lower = filename.lower()
    return any(kw.lower() in lower for kw in keywords)


def build_archive_name(stem: str, extension: str,
                       source_path: Path | None = None,
                       archive_dir: Path | None = None) -> str:
    """
    Build an archive filename using the file's original creation date.

    Uses ``st_birthtime`` (macOS, Windows 3.12+), falls back to
    ``st_ctime`` (creation time on Windows, metadata change on Linux).
    If *archive_dir* already contains a file with that name, appends
    ``_2``, ``_3``, etc. to avoid collisions.

    Example::

        build_archive_name("report", ".pdf", source_path=Path("report.pdf"),
                           archive_dir=Path("Documents Archive"))
        # → "report - 2026-02-15_10-23-45.pdf"
    """
    if source_path and source_path.exists():
        stat = source_path.stat()
        birth = getattr(stat, "st_birthtime", stat.st_ctime)
        ts = datetime.fromtimestamp(birth).strftime("%Y-%m-%d_%H-%M-%S")
    else:
        ts = current_timestamp()

    name = f"{stem} - {ts}{extension}"

    # Avoid collision within the archive directory
    if archive_dir and archive_dir.exists():
        candidate = archive_dir / name
        counter = 2
        while candidate.exists():
            name = f"{stem} - {ts}_{counter}{extension}"
            candidate = archive_dir / name
            counter += 1

    return name
