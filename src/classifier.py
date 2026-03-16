"""
classifier.py
--------------
Classify a file into a category based on filename keywords and extension.
Returns the category name or None if no match.
"""

from pathlib import Path

from config import CATEGORIES


def classify(path: Path) -> str | None:
    """
    Return the category name for *path*, or ``None`` if it doesn't match
    any configured category.

    Priority:
      1. Filename keyword match (case-insensitive) — first category wins.
      2. Extension match — first category wins.
    """
    name_lower = path.name.lower()
    ext_lower = path.suffix.lower()

    # Pass 1: filename keyword match (highest priority)
    for category, rules in CATEGORIES.items():
        for kw in rules["filename_keywords"]:
            if kw.lower() in name_lower:
                return category

    # Pass 2: extension match
    for category, rules in CATEGORIES.items():
        if ext_lower in rules["extensions"]:
            return category

    return None
