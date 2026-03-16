"""
test_classifier_dummy.py
------------------------
Tests the classifier + file_handler on the dummy files folder.
Processes files IN PLACE so the user can see the results.
"""

import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Point at the actual dummy files folder
WORK_DIR = Path(__file__).resolve().parent.parent / "dummy files"

# Patch config BEFORE importing file_handler
import config
config.WATCH_FOLDER = WORK_DIR
config.VERSIONS_FOLDER = WORK_DIR / "Resume Versions"
config.ARCHIVE_FOLDER = config.VERSIONS_FOLDER / "Resume Archives"
config.DOWNLOAD_SETTLE_INTERVAL = 0.01
config.DOWNLOAD_TIMEOUT = 1.0

from file_handler import process_file


def show_tree(root: Path, indent: str = "") -> None:
    """Print a directory tree."""
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    for entry in entries:
        if entry.name == ".DS_Store":
            continue
        if entry.is_dir():
            print(f"{indent}{entry.name}/")
            show_tree(entry, indent + "  ")
        else:
            print(f"{indent}{entry.name}")


print("=" * 60)
print("BEFORE — files in dummy files folder:")
print("=" * 60)
show_tree(WORK_DIR)
print()

# Process every file in the root of the directory
files = sorted(f for f in WORK_DIR.iterdir() if f.is_file() and f.name != ".DS_Store")
print(f"Processing {len(files)} files...\n")

for f in files:
    if f.exists():  # might have been moved by a prior iteration
        process_file(f)

print()
print("=" * 60)
print("AFTER — resulting folder structure:")
print("=" * 60)
show_tree(WORK_DIR)
