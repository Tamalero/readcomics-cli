# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # one-time browser install
```

## Running

```sh
python gui.py                           # PySide6 GUI (primary)

python main.py                          # interactive TUI (CLI fallback)
python main.py -s "Batman"              # skip search prompt
python main.py -o ~/Comics              # custom download directory
python main.py --no-headless            # show browser (debug scraping)
```

There are no tests or linting configuration in this project.

## Architecture

The codebase has three layers:

**GUI — `gui.py`**
PySide6 (Qt6) application with a dark Catppuccin Mocha theme. Three-panel layout: comics search results list | comic details (cover + metadata) | issues list with per-item checkboxes. All network operations run in `QThread` subclasses (`SearchWorker`, `ComicDetailWorker`, `DownloadWorker`) and communicate back via Qt signals. The `ComicDetailWorker` sets a `_cancelled` flag and disconnects its signals when superseded by a new selection, so stale results from slow Playwright calls are discarded rather than applied to the UI.

Output formats are selected via a combo box: **Folder** (raw images), **CBZ** (zip renamed to `.cbz`, Python-native via `zipfile`), or **CBR** (rar archive via the `rar` binary — warns the user if not found). After packaging, the intermediate image folder is removed.

**TUI/CLI layer — `main.py`**
All user interaction, display, and orchestration lives here. Uses Rich for tables, panels, progress bars, and spinners. Registers `atexit` and `SIGINT`/`SIGTERM` handlers that call `scraper.close()` to ensure the Playwright browser is always released. The main loop is: search → pick comic → pick issues → download, with `q` at any step looping back.

**Scraper/network layer — `src/scraper.py`**
`ComicScraper` handles all I/O. It holds two clients:
- A **lazy Playwright browser** (`self._browser`, only instantiated on first use) for pages that require JavaScript execution (readcomiconline.li is behind Cloudflare).
- An **`httpx.Client`** (`self._http`) for concurrent image downloads and cover art fetches.

Each scraper method (`search`, `get_comic_info`, `get_issues`, `get_issue_image_urls`) opens a fresh Playwright page, navigates, evaluates JavaScript to extract data, then closes the page. The browser itself is reused across calls.

For issue pages, `get_issue_image_urls` appends `?readType=1` to load all pages at once, then uses an in-page JS scroll loop to trigger lazy-loaded images before collecting URLs.

Downloads use `ThreadPoolExecutor(max_workers=6)`. The GUI's `DownloadWorker` calls `scraper._download_single_page` directly and emits `progress_update` signals; `main.py` drives its own Rich progress bar via `_download_with_progress`.

**Image rendering — `src/terminal_image.py`**
Used only by the CLI. Renders JPEG/PNG images as ANSI half-block characters (▄) using 24-bit truecolor: background = top pixel, foreground = bottom pixel, giving 2 vertical pixels per character cell. The GUI displays cover art as a native `QPixmap` instead.

## Key data shapes

- Search result / issue: `{"title": str, "url": str, "thumbnail": str}`
- Comic info: `{"cover": str, "summary": str, "genres": str, "status": str, "year": str, "publisher": str}`
- Downloads saved to: `<output_dir>/<comic-title>/<issue-title>/<001.jpg ...>`
