"""
tray.py
-------
System-tray icon for Smart File Organizer.

Provides a menu-bar (macOS) / system-tray (Windows) icon with:
  • Status indicator  — green = running, red = stopped
  • Start / Stop      — toggle the file watcher
  • Quit              — stop the watcher and exit the app

macOS constraint: pystray must own the main thread, so the watcher runs
in a daemon thread instead of the other way around.
"""

import platform
import subprocess
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from file_handler import sort_folder_once
from utils import logger
from watcher import create_observer

# ── Icon image helpers ─────────────────────────────────────────────────────

_SIZE = 64


def _make_icon(color: str) -> Image.Image:
    """Return a simple circle icon of the given *color*."""
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([4, 4, _SIZE - 4, _SIZE - 4], fill=color)
    return img


_ICON_RUNNING = _make_icon("green")
_ICON_STOPPED = _make_icon("red")


# ── Tray controller ───────────────────────────────────────────────────────

class TrayController:
    """Manages the lifecycle of both the tray icon and the watcher thread."""

    def __init__(self, watch_folder: Path) -> None:
        self._watch_folder = watch_folder
        self._observer = None
        self._observer_thread: threading.Thread | None = None
        self._icon: pystray.Icon | None = None

    # ── Watcher helpers ────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def _start_watcher(self) -> None:
        """Start the watchdog observer in a daemon thread."""
        if self.is_running:
            logger.info("Watcher is already running.")
            return

        self._observer = create_observer(self._watch_folder)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Watcher started — watching %s", self._watch_folder)
        self._update_icon()

    def _stop_watcher(self) -> None:
        """Stop the watchdog observer gracefully."""
        if not self.is_running:
            logger.info("Watcher is already stopped.")
            return

        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        logger.info("Watcher stopped.")
        self._update_icon()

    # ── Menu callbacks ─────────────────────────────────────────────────────

    def _on_start(self, icon, item) -> None:
        self._start_watcher()

    def _on_stop(self, icon, item) -> None:
        self._stop_watcher()

    def _on_quit(self, icon, item) -> None:
        self._stop_watcher()
        icon.stop()
        logger.info("Tray icon closed. Goodbye.")

    # ── Sort callbacks ─────────────────────────────────────────────────

    def _on_sort_downloads(self, icon, item) -> None:
        """Batch-sort all files in the watch folder."""
        threading.Thread(
            target=self._sort_folder_background,
            args=(self._watch_folder,),
            daemon=True,
        ).start()

    def _on_sort_folder(self, icon, item) -> None:
        """Open a folder picker and sort the selected folder."""
        threading.Thread(
            target=self._pick_and_sort,
            daemon=True,
        ).start()

    def _pick_and_sort(self) -> None:
        """Show a native folder dialog, then sort the chosen folder."""
        folder = self._ask_directory()
        if folder:
            self._sort_folder_background(Path(folder))

    @staticmethod
    def _ask_directory() -> str | None:
        """Open a native folder-picker dialog and return the chosen path (or None)."""
        if platform.system() == "Darwin":
            script = (
                'set f to POSIX path of (choose folder with prompt '
                '"Select folder to organise")\nreturn f'
            )
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=120,
                )
                path = result.stdout.strip().rstrip("/")
                return path if result.returncode == 0 and path else None
            except (subprocess.TimeoutExpired, OSError):
                return None
        else:
            # Windows / Linux — tkinter works fine off the main thread
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title="Select folder to organise")
            root.destroy()
            return folder or None

    def _sort_folder_background(self, folder: Path) -> None:
        """Run sort_folder_once in background and log the result."""
        logger.info("Sorting folder: %s", folder)
        count = sort_folder_once(folder)
        logger.info("Done — sorted %d files in %s", count, folder)

    # ── Icon management ────────────────────────────────────────────────────

    def _update_icon(self) -> None:
        if self._icon is not None:
            self._icon.icon = _ICON_RUNNING if self.is_running else _ICON_STOPPED
            self._icon.title = (
                "Smart File Organizer — Running"
                if self.is_running
                else "Smart File Organizer — Stopped"
            )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Start Watcher",
                self._on_start,
                visible=lambda item: not self.is_running,
            ),
            pystray.MenuItem(
                "Stop Watcher",
                self._on_stop,
                visible=lambda item: self.is_running,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sort Downloads Now", self._on_sort_downloads),
            pystray.MenuItem("Sort Folder\u2026", self._on_sort_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    # ── Public entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        """
        Start the watcher, create the tray icon, and block on the main
        thread (required by macOS).  Returns when the user clicks Quit.
        """
        self._start_watcher()

        self._icon = pystray.Icon(
            name="SmartFileOrganizer",
            icon=_ICON_RUNNING,
            title="Smart File Organizer — Running",
            menu=self._build_menu(),
        )

        logger.info("System tray icon active. Use the tray menu to stop or quit.")
        self._icon.run()  # Blocks on main thread (macOS requirement)
