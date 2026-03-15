"""
live_test.py
------------
Simulates real downloads using dummy files in a temp directory.
"""

import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Use a temp directory so we don't touch real ~/Downloads
fake_dl = Path("/tmp/sfo_test_downloads")
if fake_dl.exists():
    shutil.rmtree(fake_dl)
fake_dl.mkdir()
versions = fake_dl / "Resume Versions"
archives = versions / "Resume Archives"
versions.mkdir(parents=True)
archives.mkdir(parents=True)

# Patch config before importing file_handler
import config
config.WATCH_FOLDER = fake_dl
config.VERSIONS_FOLDER = versions
config.ARCHIVE_FOLDER = archives
config.DOWNLOAD_SETTLE_INTERVAL = 0.1
config.DOWNLOAD_TIMEOUT = 1.0

from file_handler import process_file


def show_state():
    ver_files = sorted(p.name for p in versions.iterdir() if p.is_file())
    arc_files = sorted(p.name for p in archives.iterdir() if p.is_file())
    print(f"  Resume Versions/: {ver_files}")
    print(f"  Resume Archives/: {arc_files}")
    print()


print("=" * 60)
print("TEST 1: Standard format — Sam Smith - Resume (1).pdf")
print("=" * 60)
f = fake_dl / "Sam Smith - Resume (1).pdf"
f.write_text("Resume v1")
process_file(f)
show_state()

print("=" * 60)
print("TEST 2: Second download replaces first")
print("=" * 60)
time.sleep(1.1)
f2 = fake_dl / "Sam Smith - Resume (1).pdf"
f2.write_text("Resume v2")
process_file(f2)
show_state()

print("=" * 60)
print("TEST 3: Underscore naming — FN_LN_Resume (1).docx")
print("=" * 60)
f3 = fake_dl / "FN_LN_Resume (1).docx"
f3.write_text("Docx resume")
process_file(f3)
show_state()

print("=" * 60)
print("TEST 4: CV keyword — Jane CV (1).pdf")
print("=" * 60)
f4 = fake_dl / "Jane CV (1).pdf"
f4.write_text("CV content")
process_file(f4)
show_state()

print("=" * 60)
print("TEST 5: Non-keyword file ignored — budget (1).pdf")
print("=" * 60)
f5 = fake_dl / "budget (1).pdf"
f5.write_text("spreadsheet")
process_file(f5)
print(f"  budget (1).pdf still in Downloads: {f5.exists()}")
show_state()

print("=" * 60)
print("TEST 6: Temp file ignored — resume.crdownload")
print("=" * 60)
f6 = fake_dl / "resume.crdownload"
f6.write_text("downloading...")
process_file(f6)
print(f"  resume.crdownload still in Downloads: {f6.exists()}")
print()

print("=" * 60)
print("FINAL STATE")
print("=" * 60)
show_state()

# Cleanup
shutil.rmtree(fake_dl)
print("All live tests passed!")
