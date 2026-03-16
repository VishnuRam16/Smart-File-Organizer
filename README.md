# Smart File Organizer

A lightweight Python background utility that watches your Downloads folder,
**automatically categorizes** every new file into organized subfolders, and
**deduplicates** OS-generated copies — keeping only the latest version and
archiving older ones with their original file-creation timestamps.

## What It Does

### 1. Auto-categorize downloads

Every new file is classified by filename keywords or extension and moved
into the matching subfolder:

| Category      | Matches                                                        |
|---------------|----------------------------------------------------------------|
| Screenshots   | Filenames containing "screenshot" or "screen shot"             |
| Resumes       | Filenames containing "resume" or "cv" (.pdf/.docx)             |
| Invoices      | Filenames containing "invoice", "receipt", or "bill"           |
| Photos        | `.jpg` `.jpeg` `.png` `.heic` `.gif` `.bmp` `.tiff` `.webp`   |
| Data          | `.csv` `.xlsx` `.xls` `.tsv` `.json`                           |
| Documents     | `.pdf` `.docx` `.doc` `.pptx` `.txt` `.md`                    |

### 2. Deduplicate within each category

When the OS creates `report (1).pdf`, `report (2).pdf`, etc., the organizer:

1. **Promotes** the newest copy to the clean base name (`report.pdf`)
2. **Archives** all older versions into a `<Category> Archive/` subfolder
3. Timestamps use the file's **original creation date** (`st_birthtime`), not processing time
4. If two files share the same birthtime, a `_2`, `_3` counter suffix avoids collisions

### 3. Resume-specific handling

Resume/CV files get dedicated treatment — duplicates are managed in a
`Resume Versions/` folder with a `Resume Archives/` subfolder, separate
from the general category system.

### Before & After

```
Downloads/                              Downloads/
  IMG_1484 (1).png                        Photos/
  IMG_1484 (2).png                          IMG_1484.png            ← latest
  IMG_1484 (3).png          ──────▶         Photos Archive/
  report (1).pdf                              IMG_1484 - 2024-01-08_11-00-10.png
  report.pdf                                  IMG_1484 - 2024-01-08_11-00-46.png
  data (1).csv                            Documents/
  data.csv                                  report.pdf              ← latest
                                            Documents Archive/
                                              report - 2025-02-10_09-15-33.pdf
                                          Data/
                                            data.csv                ← latest
                                            Data Archive/
                                              data - 2024-12-01_14-22-08.csv
```

## Requirements

- Python 3.11+
- macOS, Windows, or Linux

## Setup

```bash
cd Smart-File-Organizer
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

Dependencies: `watchdog`, `pystray`, `Pillow`

## Running

```bash
python src/main.py              # launches with system tray icon
python src/main.py --no-tray    # headless terminal-only mode
```

### System tray

A menu-bar icon (macOS) or system-tray icon (Windows/Linux) lets you
**Start**, **Stop**, or **Quit** the watcher. The icon is green when
running and red when stopped.

If `pystray` is not installed, the app falls back to terminal mode
automatically.

In `--no-tray` mode, press **Ctrl+C** to stop.

## Configuration

All tunable values live in `src/config.py`:

| Constant                   | Default                               | Purpose                                |
|----------------------------|---------------------------------------|----------------------------------------|
| `WATCH_FOLDER`             | `~/Downloads`                         | Folder to monitor                      |
| `VERSIONS_FOLDER`          | `~/Downloads/Resume Versions`         | Latest resume (clean base name)        |
| `ARCHIVE_FOLDER`           | `.../Resume Versions/Resume Archives` | Older resume versions with timestamps  |
| `KEYWORD_FILTER`           | `["Resume", "CV"]`                    | Resume-handler keyword triggers        |
| `CATEGORIES`               | 6 categories (see table above)        | Category → keywords + extensions map   |
| `DOWNLOAD_SETTLE_INTERVAL` | `1.0` s                               | Polling interval for size check        |
| `DOWNLOAD_TIMEOUT`         | `30.0` s                              | Give-up threshold for size polling     |
| `DEBOUNCE_SECONDS`         | `3.0` s                               | Deduplication window for OS events     |
| `TEMP_EXTENSIONS`          | `.crdownload .part .tmp .download`    | Extensions to always ignore            |

## How It Works

```
New file appears in ~/Downloads
        │
        ▼
EventHandler.on_created / on_moved
        │
        ▼ (after DEBOUNCE_SECONDS)
process_file()
        │
        ├── is temp extension?         → skip
        ├── contains resume keyword?   → handle as resume duplicate
        │
        ▼
classify() — two-pass:
  1. filename keyword match (screenshot, invoice, etc.)
  2. extension fallback (.jpg → Photos, .csv → Data, etc.)
        │
        ├── no category match?         → skip
        │
        ▼
Is it a duplicate? e.g. "file (n).ext"
  YES → archive existing base in <Category> Archive/
        (timestamp = file's original st_birthtime)
        promote new file to clean base name
  NO  → move to <Category>/ folder
```

## Archive Timestamps

Archive filenames embed the **file's original creation date**, not the
time it was processed. This is resolved cross-platform:

| OS            | Timestamp source                     |
|---------------|--------------------------------------|
| macOS         | `st_birthtime` (file creation time)  |
| Windows 3.12+ | `st_birthtime`                      |
| Windows <3.12 | `st_ctime` (creation time)           |
| Linux         | `st_ctime` (metadata change — best available) |

If two files produce the same timestamp, a `_2`, `_3` counter is appended
to avoid overwriting: `report - 2025-02-10_09-15-33_2.pdf`

## Project Layout

```
Smart-File-Organizer/
├── src/
│   ├── config.py          # Tunable constants + category definitions
│   ├── utils.py           # Regex, logging, timestamp + archive-name helpers
│   ├── classifier.py      # Two-pass file classifier (keyword → extension)
│   ├── file_handler.py    # Core archive/promote/classify logic
│   ├── watcher.py         # Watchdog observer with per-file debounce
│   ├── tray.py            # System tray icon (pystray + Pillow)
│   └── main.py            # Entry point (tray / --no-tray)
├── tests/
│   ├── test_smart_file_organizer.py   # 37 pytest unit tests
│   ├── test_classifier_dummy.py       # Integration test on dummy files
│   └── live_test.py                   # Multi-scenario simulation
├── dummy files/            # Sample files for manual testing
├── .gitignore
├── requirements.txt
└── README.md
```

## Example Logs

```
[INFO] Smart File Organizer starting up...
[INFO]   Watch folder: /Users/sam/Downloads
[INFO] Watching folder: /Users/sam/Downloads

[INFO] Sorted IMG_1484 (1).png → Photos/IMG_1484.png
[INFO] Archived → Photos Archive/IMG_1484 - 2024-01-08_11-00-10.png
[INFO] Sorted IMG_1484 (2).png → Photos/IMG_1484.png

[INFO] Archived Downloads copy → Documents Archive/report - 2025-02-10_09-15-33.pdf
[INFO] Sorted report (1).pdf → Documents/report.pdf

[INFO] Detected duplicate resume: Sam Smith - Resume (1).pdf
[INFO] Archived old resume → Resume Archives/Sam Smith - Resume - 2026-03-15_14-32-11.pdf
[INFO] Moved new resume → Resume Versions/Sam Smith - Resume.pdf
```

## Run in Background (macOS/Linux)

```bash
nohup python src/main.py &> sfo.log &
```

## Running Tests

```bash
pytest tests/ -v                              # 37 unit tests
python tests/test_classifier_dummy.py         # integration test on dummy files
```

## Future Improvements

- **macOS LaunchAgent** auto-installer for run-at-login
- **Desktop notifications** via `plyer` on each processed file
- **Multiple watch folders** — extend `WATCH_FOLDER` to a list
- **Archive pruning** — delete entries older than N days
- **Support `.pages`** — extend the regex to handle more formats
- **Dry-run mode** — `--dry-run` flag that logs without modifying files
