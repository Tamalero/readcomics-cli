# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```sh
fish start.fish               # creates venv, installs deps, installs Firefox, launches GUI
fish start.fish --verbose     # same but with full output
fish start.fish --no-headless # show the Firefox window (scraping debug)
```

Or manually:

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install firefox    # Firefox required — site blocks all Chromium variants
```

## Running

```sh
python gui.py                           # PySide6 GUI (primary)
python gui.py --verbose                 # debug logging to stderr + log file
python gui.py --no-headless             # show the Firefox browser window

python main.py                          # interactive Rich TUI (CLI fallback)
python main.py -s "Batman"              # skip search prompt
python main.py -o ~/Comics              # custom download directory
python main.py --no-headless            # show browser (debug scraping)
```

There are no tests or linting configuration in this project.

## Current version

Tracked in `VERSION` file. Read at runtime by `gui.py::_read_version()`. Current: **1.2.0**.

## Architecture

The codebase has three layers plus a standalone scraper module.

---

### `gui.py` — PySide6 GUI (primary entry point)

Dark Catppuccin Mocha theme. Layout: search bar row | three-panel QSplitter (Comics list | Details | Issues list) | bottom control bar.

**Search bar row:** search input + Search button + vertical separator + Mirror combo + ⟳ refresh button (42 px wide).

**Three panels:**
- **Comics** — `QListWidget` of search results. Items coloured `#a6e3a1` (green) when status is *Ongoing*, `#cdd6f4` otherwise. Colour is applied immediately at search time from `status_hint` (scraped from the search-page tooltip), not lazily. A `Sort:` QComboBox above the list lets the user order results by **Year ↓** (default, newest first), **Year ↑**, **Name**, or **Status**. `_apply_sort()` sorts `self._comics` in place and rebuilds the list; it also preserves the current selection when re-sorting.
- **Details** — scrollable cover `QPixmap` + metadata HTML (`QLabel` with `Qt.RichText`). All scraped values passed through `html.escape()`. A **Clear Cache** button (secondary style) sits above the scroll area — shows count confirmation dialog before deleting `$XDG_CACHE_HOME/readcomics/comic_cache/`.
- **Issues** — `QListWidget` with `Qt.ItemIsUserCheckable` checkboxes, Select All / None buttons.

**Bottom bar:** `Save as:` QCheckBox + CBZ/CBR QComboBox | `Delay:` QDoubleSpinBox (0–30 s, step 0.5) | Output QLineEdit + Browse | Download / Cancel buttons | QProgressBar | QTextEdit log (read-only, max height 90 px).

**Workers (all `QThread` subclasses):**
- `SearchWorker` — calls `scraper.search(query)`
- `ComicDetailWorker` — calls `scraper.get_comic_info()` then `scraper.get_issues()` sequentially; cancellable via `_cancelled` flag + signal disconnect
- `DownloadWorker` — fetches image URLs then downloads pages; concurrent (`ThreadPoolExecutor(max_workers=6)`) when delay = 0, sequential with `random.uniform(delay×0.5, delay×1.5)` jitter when delay > 0
- `UpdateCheckWorker` — silently queries GitHub releases API at startup via `urllib.request`; emits `update_available(latest_version, url)` if newer tag found; all exceptions suppressed
- `MirrorCheckWorker` — calls `detect_mirror()` at startup and on ⟳ click; emits `mirror_found(active_url, all_mirrors)` or `mirror_failed()`

**Critical threading rule:** Every `QThread.run()` calls `self._scraper.reset_browser()` as its first line. Qt recycles OS thread IDs across QThread instances, so the old thread-ID tracking was unreliable. `reset_browser()` guarantees a clean Playwright greenlet for each worker.

**Signal disconnect rule:** `_abort_detail_worker()` always disconnects signals (not gated by `isRunning()`), using `sig.disconnect(specific_slot)` rather than `sig.disconnect()` with no args — the no-args form triggers a PySide6 RuntimeWarning when there are no connections.

**Comic detail cache:** `_cache_load(url)` / `_cache_save(url, info, cover_data, issues)` store per-comic JSON under `$XDG_CACHE_HOME/readcomics/comic_cache/{sha256(url)}.json`. Fields: `url`, `info`, `cover_b64` (base64), `issues`, `cached_at`. `_on_comic_selected` checks the cache first; on a hit it calls `_on_info_ready` and `_on_issues_ready` synchronously with `_skip_cache_save=True` and skips launching a worker entirely.

**Tooltip system:** `_set_item_tooltip(item, comic)` checks cache first; if cached, calls `_update_item_tooltip` with full info + issue count. Otherwise builds the tooltip from `status_hint`, `publication_hint`, `summary_hint` extracted from the search page. `_update_item_tooltip(item, title, info, n_issues)` renders HTML with status, year, genres, issue count.

**Logging:** `_setup_logging(verbose)` writes to `$XDG_STATE_HOME/readcomics/readcomics.log` (always) and optionally stderr. XDG path is writable even from a read-only AppImage mount.

**Version + update check constants:**
```python
__version__ = _read_version()          # reads VERSION file
_GITHUB_REPO = "Tamalero/readcomics-cli"
_RELEASES_API = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
```

---

### `main.py` — Rich TUI (CLI fallback)

Search → pick comic → pick issues → download loop. Registers `atexit` and `SIGINT`/`SIGTERM` handlers calling `scraper.close()`. Includes `_safe_dirname()` for path-traversal protection identical to `gui.py`.

---

### `src/scraper.py` — `ComicScraper` + helpers

**Module-level:**
```python
KNOWN_MIRRORS = [
    "https://rcostation.xyz",
    "https://readcomiconline.li",
]
```

**`detect_mirror(candidates=None, timeout=8)`** — standalone function (not a method). Creates its own `httpx.Client`. For each candidate URL:
1. GET homepage; skip if status ≥ 400.
2. Skip if `id="keyword"` absent from response body — a domain can return HTTP 200 while serving 404 on all comic paths (`readcomiconline.li` was exactly this case).
3. On first passing candidate, regex-scan HTML for `Backup domain … <a href="...">` to discover additional mirrors.
Returns `(working_url, extra_mirrors)` or `(None, [])`.

**Browser:** Playwright **Firefox** (not Chromium — site detects and 404s all Chromium variants).

**State per instance:**
```
_playwright, _browser, _browser_tid, _browser_lock   # browser lifecycle
_ctx, _ctx_tid, _ctx_lock                            # shared session context (per thread)
_http                                                # httpx.Client (thread-safe, never reset)
```

**`_session_ctx` property:** Returns one `BrowserContext` per thread so cookies/session persist across homepage → comic detail → issues page within a single worker.

**`reset_browser()`:** Tears down `_ctx`, `_browser`, `_playwright`, resets all tid flags. Called at the top of every `QThread.run()`.

**`search()` tooltip extraction:** The site stores rich hover-tooltip data as the `title` attribute of `<div class="item">` elements. The JS walks up to the `.item` container, parses the `title` HTML via a temp DOM element, and extracts `tooltipTitle` (full untruncated name), `tooltipStatus`, `tooltipPublication`, and `tooltipSummary`. These are returned as `status_hint`, `publication_hint`, `summary_hint` in the search result dict. The `span.title` inside `<a>` is sometimes truncated; the tooltip title is always full.

**Search result dict:**
```python
{"title": str, "url": str, "thumbnail": str,
 "status_hint": str, "publication_hint": str, "summary_hint": str}
```

**`get_comic_info` year field:** Matches `"year of release"`, `"publication"`, and `"publication date"` (lowercased label text) — the site uses all three across different comic pages.

**`get_issues` filter:**
```python
path.lower().startswith(f"/comic/{slug.lower()}/") and path != comic_path
```

**`get_issue_image_urls`:** Appends `?readType=1`, then JS scroll loop (up to 15 s) to trigger lazy-loaded images.

---

### `src/terminal_image.py` — CLI-only image renderer

Renders images as ANSI half-block characters (▄) with 24-bit truecolor. Not used by the GUI (which renders cover art as `QPixmap`).

---

## Security patterns

**`_safe_dirname(name)`** (in both `gui.py` and `main.py`):
```python
def _safe_dirname(name: str) -> str:
    name = re.sub(r'[/\\:*?"<>|]', '_', name)
    name = re.sub(r'\.\.+', '.', name)
    name = name.strip('. ')
    return name or "Unknown"
```
Applied to URL-derived `comic_name` (URL path part 2) and `safe_title` (issue title) before using them as directory names.

**HTML escaping:** All scraped values rendered in `QLabel` rich text go through `html.escape()`.

**Subprocess safety:** `_package_cbr` passes `["rar", "a", "-ep", "--", out_path] + images` — the `--` prevents filenames starting with `-` being misread as flags.

---

## Key data shapes

- Search result: `{"title": str, "url": str, "thumbnail": str, "status_hint": str, "publication_hint": str, "summary_hint": str}`
- Comic info: `{"cover": str, "summary": str, "genres": str, "status": str, "year": str, "publisher": str}`
- Issue: `{"title": str, "url": str}`
- Cache entry: `{"url": str, "info": dict, "cover_b64": str, "issues": list, "cached_at": float}`
- Download layout: `<output_dir>/<_safe_dirname(comic-slug)>/<_safe_dirname(issue-title)>/<001.jpg …>`
- CBZ = Python `zipfile` renamed to `.cbz`; CBR = `rar` binary required

---

## AppImage

Built by `build-appimage.sh`. Bundles Python 3.12.13 (python-build-standalone stripped), PySide6, Playwright, Firefox, httpx, rich, Pillow. Output: `ReadComics-x86_64.AppImage` (~387 MB). Python archive cached in `appimage-build/cache/` for re-runs.

**`AppRun` environment variables:**
```bash
PLAYWRIGHT_BROWSERS_PATH="$HERE/opt/readcomics/pw-browsers"
PYTHONHOME="$HERE/opt/readcomics/python"
PYTHONPATH="$HERE/opt/readcomics"
QT_QPA_PLATFORM_PLUGIN_PATH="$SITE/PySide6/Qt/plugins/platforms"
LD_LIBRARY_PATH="$SITE/PySide6/Qt/lib:$HERE/opt/readcomics/python/lib:..."
APPDIR="$HERE"
```

**Update information embedded:** `gh-releases-zsync|Tamalero|readcomics-cli|latest|ReadComics-x86_64.AppImage.zsync`

**appimagetool flag:** `--updateinformation` (not `--update-information` — the hyphenated form is rejected).

---

## Release process

```sh
# 1. Bump VERSION file
# 2. Commit + push
git add VERSION && git commit -m "chore: bump version to X.Y.Z" && git push origin master
# 3. Build AppImage
bash build-appimage.sh
# 4. Tag + push tag
git tag vX.Y.Z && git push origin vX.Y.Z
# 5. Create GitHub release with artifacts
gh release create vX.Y.Z ReadComics-x86_64.AppImage ReadComics-x86_64.AppImage.zsync \
  --title "ReadComics vX.Y.Z" --notes "..."
```
