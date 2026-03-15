"""
watcher.py
----------
Watchdog observer lifecycle and debounced filesystem-event handler.

Why debounce?
  When a browser saves a file, the OS can fire multiple rapid ``created``
  and ``modified`` events for the same path.  The debounce timer ensures we
  only call ``process_file`` once, after the burst of events has settled.

Why also handle ``on_moved``?
  Chrome/Edge write to ``<name>.crdownload`` then *rename* it to the final
  filename.  Watchdog surfaces that rename as a ``FileMovedEvent`` whose
  ``dest_path`` is the finished file.
"""

import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config import DEBOUNCE_SECONDS, WATCH_FOLDER
from file_handler import process_file
from utils import logger


class ResumeEventHandler(FileSystemEventHandler):
    """
    Watchdog event handler with per-file debouncing.

    Each unique file path gets its own ``threading.Timer``.  If another event
    arrives for the same path before the timer fires, the old timer is
    cancelled and a fresh one is started.
    """

    def __init__(self) -> None:
        super().__init__()
        # path string → active Timer
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ── Watchdog callbacks ─────────────────────────────────────────────────

    def on_created(self, event: FileCreatedEvent) -> None:
        """A new file appeared in the watched directory."""
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        """
        A file was renamed inside the watched directory.
        Handles the browser pattern: ``file.crdownload`` → ``file.pdf``.
        """
        if not event.is_directory:
            self._schedule(Path(event.dest_path))

    # ── Debounce machinery ─────────────────────────────────────────────────

    def _schedule(self, path: Path) -> None:
        """
        (Re-)schedule processing of *path* after ``DEBOUNCE_SECONDS``.
        Any previously pending timer for the same path is cancelled first.
        """
        key = str(path)

        with self._lock:
            existing = self._pending.get(key)
            if existing is not None:
                existing.cancel()

            timer = threading.Timer(
                DEBOUNCE_SECONDS,
                self._dispatch,
                args=(path, key),
            )
            timer.daemon = True  # Don't block interpreter shutdown
            timer.start()
            self._pending[key] = timer

    def _dispatch(self, path: Path, key: str) -> None:
        """Called by the timer thread; cleans up state then processes the file."""
        with self._lock:
            self._pending.pop(key, None)

        try:
            process_file(path)
        except Exception as exc:  # Broad catch: watcher must never crash
            logger.error(
                "Unexpected error while processing %s: %s",
                path.name,
                exc,
                exc_info=True,
            )


# ── Observer lifecycle ─────────────────────────────────────────────────────

def create_observer(watch_folder: Path = WATCH_FOLDER) -> Observer:
    """
    Build and return a configured (not yet started) watchdog ``Observer``.

    Raises:
        FileNotFoundError: if *watch_folder* does not exist.
    """
    if not watch_folder.exists():
        raise FileNotFoundError(
            f"Watch folder does not exist: {watch_folder}\n"
            "Create it or update WATCH_FOLDER in config.py."
        )

    handler = ResumeEventHandler()
    observer = Observer()
    # recursive=False: only watch the top-level Downloads folder
    observer.schedule(handler, str(watch_folder), recursive=False)
    return observer


def run_watcher(watch_folder: Path = WATCH_FOLDER) -> None:
    """
    Start the observer and block until the user presses **Ctrl+C**.
    Performs a clean shutdown on interrupt.
    """
    observer = create_observer(watch_folder)
    observer.start()
    logger.info("Watching folder: %s", watch_folder)
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested — stopping watcher...")
    finally:
        observer.stop()
        observer.join()
        logger.info("Watcher stopped. Goodbye.")
