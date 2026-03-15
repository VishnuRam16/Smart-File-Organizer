# Smart File Organizer

A lightweight Python background utility that automatically manages duplicate
resume downloads in your Downloads folder.

## The Problem

When you download the same resume multiple times, your OS creates:

```
Downloads/
  Sam Smith - Resume.pdf
  Sam Smith - Resume (1).pdf
  Sam Smith - Resume (2).pdf
```

Smart File Organizer detects each new duplicate, archives the old version
with a timestamp, and renames the download to the clean canonical name.

It works with **any filename convention** as long as the file contains
"Resume" or "CV" and has an OS-appended `(n)` duplicate suffix:

```
Sam Smith - Resume (1).pdf       ✓
FN_LN_Resume (2).docx            ✓
Jane Doe CV (1).pdf               ✓
my-resume (3).docx               ✓
budget (1).pdf                   ✗  (no keyword match)
photo (1).jpg                    ✗  (not pdf/docx)
```

## Requirements

- Python 3.11 or newer
- pip

## Setup

```bash
# 1. Navigate to the project folder
cd Smart-File-Organizer

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python src/main.py              # launches with system tray icon
python src/main.py --no-tray    # headless terminal-only mode
```

With the tray icon, use the menu-bar icon (macOS) or system-tray icon
(Windows) to **Start**, **Stop**, or **Quit** the watcher.

In `--no-tray` mode, press **Ctrl+C** to stop.

## Configuration

All tunable values live in `src/config.py`:

| Constant                   | Default                          | Purpose                                |
|----------------------------|----------------------------------|----------------------------------------|
| `WATCH_FOLDER`             | `~/Downloads`                    | Folder to monitor                      |
| `VERSIONS_FOLDER`          | `~/Downloads/Resume Versions`    | Latest resume (clean base name)        |
| `ARCHIVE_FOLDER`           | `.../Resume Versions/Resume Archives` | Older versions with timestamps    |
| `KEYWORD_FILTER`           | `["Resume", "CV"]`               | Filename must contain one of these     |
| `DOWNLOAD_SETTLE_INTERVAL` | `1.0` s                          | Polling interval for size check        |
| `DOWNLOAD_TIMEOUT`         | `30.0` s                         | Give-up threshold for size polling     |
| `DEBOUNCE_SECONDS`         | `3.0` s                          | Deduplication window for OS events     |
| `TEMP_EXTENSIONS`          | `.crdownload .part .tmp .download`| Extensions to always ignore           |

## How It Works

```
New file appears in ~/Downloads
        │
        ▼
ResumeEventHandler.on_created / on_moved
        │
        ▼ (after DEBOUNCE_SECONDS)
process_file()
        │
        ├── is temp extension?    → skip
        ├── contains keyword?     → skip if not
        ├── matches (n) pattern?  → skip if not (any .pdf/.docx with OS duplicate suffix)
        │
        ▼
Wait for file size to stabilise
        │
        ▼
Base file exists in Resume Versions?
  YES → archive it with timestamp → Resume Versions/Resume Archives/
        │
        ▼
Move new file to Resume Versions/ with clean base name
```

## Project Layout

```
Smart-File-Organizer/
├── src/
│   ├── config.py          # All tunable constants
│   ├── utils.py           # Regex, logging, timestamp helpers
│   ├── file_handler.py    # Core archive/promote logic
│   ├── watcher.py         # Watchdog observer with debounce
│   ├── tray.py            # System tray icon (pystray)
│   └── main.py            # Entry point
├── tests/
│   ├── test_smart_file_organizer.py   # 37 pytest unit tests
│   └── live_test.py                   # Dummy-file integration simulation
├── .gitignore
├── requirements.txt
└── README.md
```

## Example Logs

```
[INFO] Smart File Organizer starting up...
[INFO]   Watch folder  : /Users/sam/Downloads
[INFO]   Versions folder: /Users/sam/Downloads/Resume Versions
[INFO]   Archive folder : /Users/sam/Downloads/Resume Versions/Resume Archives
[INFO] Watching folder: /Users/sam/Downloads
[INFO] Press Ctrl+C to stop.
[INFO] Detected duplicate resume: Sam Smith - Resume (1).pdf
[INFO] Archived old resume → Resume Archives/Sam Smith - Resume - 2026-03-15_14-32-11.pdf
[INFO] Moved new resume → Resume Versions/Sam Smith - Resume.pdf
[INFO] Shutdown requested — stopping watcher...
[INFO] Watcher stopped. Goodbye.
```

## Run in Background (macOS/Linux)

```bash
nohup python src/main.py &> sfo.log &
```

## Running Tests

```bash
pytest tests/ -v
```

## Future Improvements

- **macOS LaunchAgent** auto-installer for run-at-login
- **Desktop notifications** via `plyer` on each processed file
- **Multiple watch folders** — extend `WATCH_FOLDER` to a list
- **Archive pruning** — delete entries older than N days
- **Support `.pages`** — extend the regex to handle more formats
- **Dry-run mode** — `--dry-run` flag that logs without modifying files
