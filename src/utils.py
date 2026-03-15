"""
utils.py
--------
Shared utilities: structured logging, timestamp generation, and filename
pattern parsing.  No business logic lives here.
"""

import logging
import re
from datetime import datetime


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


def contains_keyword(filename: str, keywords: list[str]) -> bool:
    """
    Return ``True`` if *filename* contains at least one entry from *keywords*
    (comparison is case-insensitive).
    """
    lower = filename.lower()
    return any(kw.lower() in lower for kw in keywords)


def build_archive_name(stem: str, extension: str) -> str:
    """
    Append the current timestamp to *stem* and return a full filename.

    Example::

        build_archive_name("Sam Smith - Resume", ".pdf")
        # → "Sam Smith - Resume - 2026-03-15_14-32-11.pdf"
    """
    return f"{stem} - {current_timestamp()}{extension}"
