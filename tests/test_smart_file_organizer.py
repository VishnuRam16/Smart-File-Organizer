"""
test_smart_file_organizer.py
----------------------------
Unit tests for Smart File Organizer.
Run with:  pytest tests/ -v
"""

import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ═══════════════════════════════════════════════════════════════════════════
# 1. UTILS — parse_duplicate, contains_keyword, build_archive_name
# ═══════════════════════════════════════════════════════════════════════════

from utils import build_archive_name, contains_keyword, parse_duplicate


class TestParseDuplicate:
    """Test the regex that detects OS-appended (n) duplicates."""

    # ── Should match ───────────────────────────────────────────────────────

    def test_standard_format(self):
        assert parse_duplicate("Sam Smith - Resume (1).pdf") == ("Sam Smith - Resume", ".pdf")

    def test_higher_index(self):
        assert parse_duplicate("Sam Smith - Resume (12).pdf") == ("Sam Smith - Resume", ".pdf")

    def test_docx(self):
        assert parse_duplicate("Sam Smith - Resume (2).docx") == ("Sam Smith - Resume", ".docx")

    def test_underscore_naming(self):
        assert parse_duplicate("FN_LN_Resume (1).pdf") == ("FN_LN_Resume", ".pdf")

    def test_space_naming(self):
        assert parse_duplicate("FN LN Resume (3).pdf") == ("FN LN Resume", ".pdf")

    def test_cv_keyword(self):
        assert parse_duplicate("Jane Doe CV (1).pdf") == ("Jane Doe CV", ".pdf")

    def test_lowercase_resume(self):
        assert parse_duplicate("my resume (1).pdf") == ("my resume", ".pdf")

    def test_mixed_case(self):
        assert parse_duplicate("John Doe - RESUME (1).PDF") == ("John Doe - RESUME", ".PDF")

    def test_dash_in_name(self):
        assert parse_duplicate("my-resume (1).docx") == ("my-resume", ".docx")

    def test_no_space_before_paren(self):
        assert parse_duplicate("resume(1).pdf") == ("resume", ".pdf")

    # ── Should NOT match ───────────────────────────────────────────────────

    def test_no_duplicate_suffix(self):
        assert parse_duplicate("Sam Smith - Resume.pdf") is None

    def test_wrong_extension(self):
        assert parse_duplicate("Sam Smith - Resume (1).xlsx") is None

    def test_jpg_file(self):
        assert parse_duplicate("photo (1).jpg") is None

    def test_no_index(self):
        assert parse_duplicate("Sam Smith - Resume ().pdf") is None

    def test_plain_text(self):
        assert parse_duplicate("notes.txt") is None

    def test_empty_string(self):
        assert parse_duplicate("") is None

    def test_temp_extension(self):
        assert parse_duplicate("resume (1).crdownload") is None


class TestContainsKeyword:
    """Test keyword matching."""

    def test_contains_resume(self):
        assert contains_keyword("Sam Smith - Resume (1).pdf", ["Resume", "CV"]) is True

    def test_contains_cv(self):
        assert contains_keyword("Jane Doe CV (1).pdf", ["Resume", "CV"]) is True

    def test_case_insensitive(self):
        assert contains_keyword("my RESUME (1).pdf", ["Resume", "CV"]) is True

    def test_no_keyword(self):
        assert contains_keyword("budget (1).pdf", ["Resume", "CV"]) is False

    def test_underscore_name_with_keyword(self):
        assert contains_keyword("FN_LN_Resume (1).pdf", ["Resume", "CV"]) is True


class TestBuildArchiveName:
    """Test archived filename generation."""

    def test_format(self):
        with patch("utils.current_timestamp", return_value="2026-03-15_14-32-11"):
            result = build_archive_name("Sam Smith - Resume", ".pdf")
            assert result == "Sam Smith - Resume - 2026-03-15_14-32-11.pdf"

    def test_docx_format(self):
        with patch("utils.current_timestamp", return_value="2026-01-01_00-00-00"):
            result = build_archive_name("FN_LN_Resume", ".docx")
            assert result == "FN_LN_Resume - 2026-01-01_00-00-00.docx"


# ═══════════════════════════════════════════════════════════════════════════
# 2. FILE_HANDLER — process_file (integration tests with tmp_path)
# ═══════════════════════════════════════════════════════════════════════════

import file_handler


@pytest.fixture
def workspace(tmp_path):
    """
    Create a fake Downloads / Resume Versions / Resume Archives structure
    and patch config values to point there.
    """
    downloads = tmp_path / "Downloads"
    versions = downloads / "Resume Versions"
    archives = versions / "Resume Archives"

    downloads.mkdir()
    versions.mkdir(parents=True)
    archives.mkdir(parents=True)

    patches = {
        "file_handler.ARCHIVE_FOLDER": archives,
        "file_handler.VERSIONS_FOLDER": versions,
        "file_handler.WATCH_FOLDER": downloads,
        "file_handler.KEYWORD_FILTER": ["Resume", "CV"],
        "file_handler.TEMP_EXTENSIONS": frozenset({".crdownload", ".part", ".tmp", ".download"}),
        "file_handler.DOWNLOAD_SETTLE_INTERVAL": 0.01,  # Speed up tests
        "file_handler.DOWNLOAD_TIMEOUT": 0.5,
    }

    # Apply all patches
    patchers = [patch(target, value) for target, value in patches.items()]
    for p in patchers:
        p.start()

    yield {
        "downloads": downloads,
        "versions": versions,
        "archives": archives,
    }

    for p in patchers:
        p.stop()


class TestProcessFile:
    """Integration tests for the full process_file() pipeline."""

    def test_new_duplicate_moves_to_versions(self, workspace):
        """A duplicate with no existing base file should move to Resume Versions."""
        dup = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup.write_text("new content")

        file_handler.process_file(dup)

        base = workspace["versions"] / "Sam Smith - Resume.pdf"
        assert base.exists(), "Base file should exist in Resume Versions"
        assert base.read_text() == "new content"
        assert not dup.exists(), "Duplicate should be removed from Downloads"

    def test_existing_base_in_downloads_gets_archived(self, workspace):
        """Old base in Downloads should be archived before the new one is placed."""
        old_base = workspace["downloads"] / "Sam Smith - Resume.pdf"
        old_base.write_text("old content")

        dup = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup.write_text("new content")

        file_handler.process_file(dup)

        # Old base archived
        archived = list(workspace["archives"].glob("Sam Smith - Resume - *.pdf"))
        assert len(archived) == 1, "Old base should be archived"
        assert archived[0].read_text() == "old content"

        # New file in versions
        base = workspace["versions"] / "Sam Smith - Resume.pdf"
        assert base.exists()
        assert base.read_text() == "new content"

    def test_existing_base_in_versions_gets_archived(self, workspace):
        """Old base in Resume Versions should be archived when a new duplicate arrives."""
        old_version = workspace["versions"] / "Sam Smith - Resume.pdf"
        old_version.write_text("old version content")

        dup = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup.write_text("newest content")

        file_handler.process_file(dup)

        # Old version archived
        archived = list(workspace["archives"].glob("Sam Smith - Resume - *.pdf"))
        assert len(archived) == 1
        assert archived[0].read_text() == "old version content"

        # New file in versions
        base = workspace["versions"] / "Sam Smith - Resume.pdf"
        assert base.read_text() == "newest content"

    def test_both_downloads_and_versions_copies_archived(self, workspace):
        """Both the Downloads base AND Versions base should be archived."""
        dl_base = workspace["downloads"] / "Sam Smith - Resume.pdf"
        dl_base.write_text("downloads copy")

        ver_base = workspace["versions"] / "Sam Smith - Resume.pdf"
        ver_base.write_text("versions copy")

        dup = workspace["downloads"] / "Sam Smith - Resume (2).pdf"
        dup.write_text("newest")

        # Patch timestamps to ensure distinct archive names
        with patch("file_handler.build_archive_name", side_effect=[
            "Sam Smith - Resume - 2026-03-15_14-00-01.pdf",
            "Sam Smith - Resume - 2026-03-15_14-00-02.pdf",
        ]):
            file_handler.process_file(dup)

        archived = list(workspace["archives"].glob("Sam Smith - Resume - *.pdf"))
        assert len(archived) == 2, "Both old copies should be archived"

        base = workspace["versions"] / "Sam Smith - Resume.pdf"
        assert base.read_text() == "newest"

    def test_ignores_temp_file(self, workspace):
        """Files with browser temp extensions should be skipped."""
        temp = workspace["downloads"] / "resume.crdownload"
        temp.write_text("downloading...")

        file_handler.process_file(temp)

        assert temp.exists(), "Temp file should not be touched"
        assert len(list(f for f in workspace["versions"].glob("*") if f.is_file())) == 0

    def test_ignores_non_keyword_file(self, workspace):
        """Files without 'Resume' or 'CV' are classified and deduped into category."""
        dup = workspace["downloads"] / "budget (1).pdf"
        dup.write_text("spreadsheet")

        file_handler.process_file(dup)

        # Classifier sorts it into Documents/ with clean base name (no (1))
        assert not dup.exists(), "Classifier should move the file"
        sorted_file = workspace["downloads"] / "Documents" / "budget.pdf"
        assert sorted_file.exists(), "Should be sorted into Documents/ as budget.pdf"

    def test_ignores_non_duplicate_resume(self, workspace):
        """A resume without (n) suffix is classified into Resumes/, not duplicate-handled."""
        base = workspace["downloads"] / "Sam Smith - Resume.pdf"
        base.write_text("original")

        file_handler.process_file(base)

        # Classifier sorts it into Resumes/ (keyword match takes priority)
        assert not base.exists(), "Classifier should move the file"
        sorted_file = workspace["downloads"] / "Resumes" / "Sam Smith - Resume.pdf"
        assert sorted_file.exists(), "Should be sorted into Resumes/"

    def test_docx_support(self, workspace):
        """Should handle .docx files the same as .pdf."""
        dup = workspace["downloads"] / "FN_LN_Resume (1).docx"
        dup.write_text("docx content")

        file_handler.process_file(dup)

        base = workspace["versions"] / "FN_LN_Resume.docx"
        assert base.exists()
        assert base.read_text() == "docx content"

    def test_underscore_naming_convention(self, workspace):
        """Should work with underscore-based filenames."""
        dup = workspace["downloads"] / "John_Doe_Resume (1).pdf"
        dup.write_text("underscore resume")

        file_handler.process_file(dup)

        base = workspace["versions"] / "John_Doe_Resume.pdf"
        assert base.exists()
        assert base.read_text() == "underscore resume"

    def test_space_naming_convention(self, workspace):
        """Should work with plain space-separated names."""
        dup = workspace["downloads"] / "Jane Doe Resume (1).pdf"
        dup.write_text("space resume")

        file_handler.process_file(dup)

        base = workspace["versions"] / "Jane Doe Resume.pdf"
        assert base.exists()

    def test_cv_keyword(self, workspace):
        """Should handle CV files."""
        dup = workspace["downloads"] / "John Smith CV (1).pdf"
        dup.write_text("cv content")

        file_handler.process_file(dup)

        base = workspace["versions"] / "John Smith CV.pdf"
        assert base.exists()

    def test_file_disappears_before_processing(self, workspace):
        """If the file is deleted before we finish waiting, skip gracefully."""
        dup = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup.write_text("content")

        # Patch _wait_for_download_completion to return False (simulating disappearance)
        with patch.object(file_handler, "_wait_for_download_completion", return_value=False):
            file_handler.process_file(dup)

        # File should still exist (we didn't move it), no crash
        assert not (workspace["versions"] / "Sam Smith - Resume.pdf").exists()

    def test_multiple_sequential_downloads(self, workspace):
        """Simulates downloading Resume (1), then (2) — both should archive properly."""
        # First download
        dup1 = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup1.write_text("version 1")
        file_handler.process_file(dup1)

        base = workspace["versions"] / "Sam Smith - Resume.pdf"
        assert base.read_text() == "version 1"

        # Second download — (1) again because the user re-downloaded
        time.sleep(1.1)  # Ensure different timestamp
        dup2 = workspace["downloads"] / "Sam Smith - Resume (1).pdf"
        dup2.write_text("version 2")
        file_handler.process_file(dup2)

        assert base.read_text() == "version 2"

        archived = list(workspace["archives"].glob("Sam Smith - Resume - *.pdf"))
        assert len(archived) == 1
        assert archived[0].read_text() == "version 1"
