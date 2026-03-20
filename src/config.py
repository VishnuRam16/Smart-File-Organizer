"""
config.py
---------
Central configuration for Smart File Organizer.
Modify these constants to customise behaviour without touching core logic.
"""

from pathlib import Path

# ── Folders ────────────────────────────────────────────────────────────────

# Directory to monitor for new downloads
WATCH_FOLDER: Path = Path.home() / "Downloads"

# Directory where the latest resume (clean base name) is kept
VERSIONS_FOLDER: Path = WATCH_FOLDER / "Resume Versions"

# Sub-folder for older versions with timestamps
ARCHIVE_FOLDER: Path = VERSIONS_FOLDER / "Resume Archives"

# ── Detection ──────────────────────────────────────────────────────────────

# A downloaded file must contain at least one of these keywords (case-insensitive)
# to be considered a resume candidate.
KEYWORD_FILTER: list[str] = ["Resume", "CV"]

# ── Download-completion polling ────────────────────────────────────────────

# Seconds between file-size samples when waiting for a download to finish
DOWNLOAD_SETTLE_INTERVAL: float = 1.0

# Maximum seconds to wait before giving up on a still-changing file
DOWNLOAD_TIMEOUT: float = 30.0

# ── Debounce ───────────────────────────────────────────────────────────────

# Seconds to hold off re-processing the same path (absorbs rapid OS events)
DEBOUNCE_SECONDS: float = 3.0

# ── Temp files ─────────────────────────────────────────────────────────────

# Browser in-progress download extensions — always ignored
TEMP_EXTENSIONS: frozenset[str] = frozenset(
    {".crdownload", ".part", ".tmp", ".download"}
)

# ── File Categories ────────────────────────────────────────────────────────

# Each category maps to filename keywords (checked first, case-insensitive)
# and/or extensions (fallback). Order matters — first match wins.
CATEGORIES: dict[str, dict] = {
    "Screenshots": {
        "filename_keywords": ["screenshot", "screen shot"],
        "extensions": set(),
    },
    "Resumes": {
        "filename_keywords": ["resume", "cv"],
        "extensions": set(),
    },
    "Invoices": {
        "filename_keywords": ["invoice", "receipt", "bill"],
        "extensions": set(),
    },
    "Photos": {
        "filename_keywords": [],
        "extensions": {".jpg", ".jpeg", ".png", ".heic", ".gif", ".bmp", ".tiff", ".webp"},
    },
    "Data": {
        "filename_keywords": [],
        "extensions": {".csv", ".xlsx", ".xls", ".tsv"},
    },
    "Documents": {
        "filename_keywords": [],
        "extensions": {".pdf", ".docx", ".doc", ".pptx", ".txt", ".md"},
    },
    "Code": {
        "filename_keywords": [],
        "extensions": {
            ".py", ".ipynb", ".sql", ".json", ".js", ".ts", ".jsx", ".tsx",
            ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb", ".php",
            ".sh", ".zsh", ".yaml", ".yml", ".toml", ".html", ".css",
        },
    },
}
