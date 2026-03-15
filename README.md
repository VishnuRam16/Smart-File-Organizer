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

## Requirements

- Python 3.11 or newer
- pip

## Setup

```bash
# 1. Navigate to the project folder
cd smart_file_organizer

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Press **Ctrl+C** to stop.

## Configuration

All tunable values live in `config.py`:

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
        ├── matches (n) pattern?  → skip if not
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
nohup python main.py &> rvk.log &
```

## Future Improvements

- **System tray icon** via `pystray` with a "Stop" option
- **macOS LaunchAgent** auto-installer for run-at-login
- **Desktop notifications** via `plyer` on each processed file
- **Multiple watch folders** — extend `WATCH_FOLDER` to a list
- **Unit tests** with `pytest` + `tmp_path` fixtures
- **Archive pruning** — delete entries older than N days
- **Support `.docx` / `.pages`** — extend the regex beyond PDF
- **Dry-run mode** — `--dry-run` flag that logs without modifying files
