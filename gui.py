#!/usr/bin/env python3
"""ReadComics GUI — PySide6 frontend for browsing and downloading comics."""

# When running as a PyInstaller bundle, point Playwright at the browsers folder
# that sits next to the EXE. Must be set before playwright is imported.
import os as _os, sys as _sys
if getattr(_sys, 'frozen', False):
    _os.environ.setdefault(
        'PLAYWRIGHT_BROWSERS_PATH',
        _os.path.join(_os.path.dirname(_sys.executable), 'browsers'),
    )

import argparse
import base64
import hashlib
import html
import json
import logging
import os
import random
import re
import sys
import shutil
import time
import zipfile
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QTextEdit, QComboBox, QFileDialog,
    QGroupBox, QScrollArea, QSizePolicy, QAbstractItemView,
    QMessageBox, QFrame, QCheckBox, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont, QColor

from src.scraper import ComicScraper, KNOWN_MIRRORS, detect_mirror

logger = logging.getLogger("readcomics")

# ── Version ───────────────────────────────────────────────────────────────────

def _read_version() -> str:
    try:
        v = (Path(__file__).parent / "VERSION").read_text().strip()
        return v if v else "0.0.0"
    except Exception:
        return "0.0.0"

__version__ = _read_version()
_GITHUB_REPO = "Tamalero/readcomics-cli"
_RELEASES_API = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"


def _setup_logging(verbose: bool) -> None:
    # Use XDG_STATE_HOME so the log survives in a read-only AppImage mount.
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    log_dir = state_home / "readcomics"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "readcomics.log"
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.propagate = False
    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)


# ── Theme ─────────────────────────────────────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    padding: 4px 8px;
    border-radius: 2px;
}
QListWidget::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QListWidget::item:hover:!selected {
    background-color: #313244;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
    min-height: 28px;
}
QPushButton:hover  { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton:disabled { background-color: #313244; color: #585b70; }
QPushButton#secondary {
    background-color: #313244;
    color: #cdd6f4;
    font-weight: normal;
}
QPushButton#secondary:hover { background-color: #45475a; }
QPushButton#cancel_btn {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#cancel_btn:hover { background-color: #eba0ac; }
QPushButton#cancel_btn:disabled { background-color: #313244; color: #585b70; }
QLineEdit {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 6px 10px;
    color: #cdd6f4;
    min-height: 28px;
}
QLineEdit:focus { border-color: #89b4fa; }
QProgressBar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    min-height: 20px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}
QTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #a6e3a1;
    font-family: monospace;
    font-size: 12px;
}
QComboBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
    min-height: 28px;
    min-width: 90px;
}
QComboBox::drop-down { border: none; padding-right: 8px; }
QComboBox QAbstractItemView {
    background-color: #181825;
    border: 1px solid #313244;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QScrollBar:vertical {
    background: #181825;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #6c7086; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle:horizontal { background-color: #313244; width: 2px; }
QLabel { color: #cdd6f4; }
QCheckBox { color: #cdd6f4; spacing: 6px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #313244; border-radius: 3px;
    background-color: #181825;
}
QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }
QCheckBox::indicator:hover  { border-color: #89b4fa; }
QDoubleSpinBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 6px;
    color: #cdd6f4;
    min-height: 28px;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #313244; border: none; width: 16px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #45475a;
}
QStatusBar {
    background-color: #181825;
    color: #6c7086;
    border-top: 1px solid #313244;
}
"""


# ── Worker threads ────────────────────────────────────────────────────────────

class SearchWorker(QThread):
    results_ready = Signal(list)
    error = Signal(str)

    def __init__(self, scraper: ComicScraper, query: str):
        super().__init__()
        self._scraper = scraper
        self._query = query

    def run(self):
        self._scraper.reset_browser()
        try:
            self.results_ready.emit(self._scraper.search(self._query))
        except Exception as exc:
            logger.exception("Search failed for query %r", self._query)
            self.error.emit(str(exc))


class ComicDetailWorker(QThread):
    """Loads comic metadata + cover image, then the issues list, in one thread.

    Uses its own ComicScraper instance so that rapidly switching comics
    (which creates a new worker) cannot reset the browser mid-execution of
    a still-running old worker.
    """
    info_ready = Signal(dict, bytes)   # info dict, raw cover image bytes
    issues_ready = Signal(list)
    error = Signal(str)

    def __init__(self, comic: dict, headless: bool = True):
        super().__init__()
        self._comic = comic
        self._headless = headless
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        scraper = ComicScraper(headless=self._headless)
        try:
            info = scraper.get_comic_info(self._comic["url"])
            if self._cancelled:
                return

            cover_data = b""
            cover_url = info.get("cover") or self._comic.get("thumbnail", "")
            if cover_url:
                try:
                    resp = scraper._http.get(cover_url, timeout=10)
                    resp.raise_for_status()
                    cover_data = resp.content
                except Exception:
                    logger.exception("Cover fetch failed for %s", cover_url)

            if not self._cancelled:
                self.info_ready.emit(info, cover_data)

            if self._cancelled:
                return

            issues = scraper.get_issues(self._comic["url"])
            if not self._cancelled:
                self.issues_ready.emit(issues)
        except Exception as exc:
            logger.exception("Comic detail failed for %s", self._comic.get("url"))
            if not self._cancelled:
                self.error.emit(str(exc))
        finally:
            scraper.close()


class DownloadWorker(QThread):
    progress_update = Signal(int, int, int, int, str)  # idx, total, done, n_pages, label
    issue_done = Signal(str, str)    # title, final_path
    issue_failed = Signal(str, str)  # title, error
    log_message = Signal(str)
    finished_all = Signal()

    def __init__(self, scraper: ComicScraper, issues: list, output_dir: str, fmt: str,
                 delay: float = 0.0, publisher: str = "", comic_title: str = ""):
        super().__init__()
        self._scraper = scraper
        self._issues = issues
        self._output_dir = output_dir
        self._fmt = fmt          # "folder" | "cbz" | "cbr"
        self._delay = delay      # seconds between image downloads (0 = concurrent, no delay)
        self._publisher = publisher
        self._comic_title = comic_title
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _sleep(self, seconds: float):
        """Interruptible sleep that respects cancellation."""
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._cancelled:
            time.sleep(min(0.1, end - time.monotonic()))

    def run(self):
        self._scraper.reset_browser()
        total = len(self._issues)
        for idx, issue in enumerate(self._issues, 1):
            if self._cancelled:
                break

            title = issue["title"]

            # Build path: <output>/<publisher>/<comic>/<issue>
            # Publisher and comic title come from the GUI; fall back to URL slug if absent.
            parsed = urlparse(issue["url"])
            parts = parsed.path.rstrip("/").split("/")
            raw_slug = (parts[2] if len(parts) > 2 else "Unknown").replace("-", " ").replace("_", " ")
            publisher_dir = _safe_dirname(self._publisher) if self._publisher else "Unknown"
            comic_dir = _safe_dirname(self._comic_title) if self._comic_title else _safe_dirname(raw_slug)
            safe_title = _safe_dirname(title)
            issue_dir = os.path.join(self._output_dir, publisher_dir, comic_dir, safe_title)

            # Skip without a network request if the issue was already downloaded.
            already_done = False
            if self._fmt == "cbz":
                already_done = os.path.isfile(issue_dir + ".cbz")
            elif self._fmt == "cbr":
                already_done = os.path.isfile(issue_dir + ".cbr")
            else:
                already_done = os.path.isdir(issue_dir) and bool(_image_files(issue_dir))
            if already_done:
                existing = issue_dir + (".cbz" if self._fmt == "cbz" else ".cbr" if self._fmt == "cbr" else "")
                self.log_message.emit(f"Skipping (already exists): {title}")
                self.issue_done.emit(title, existing)
                continue

            self.log_message.emit(f"Fetching page list: {title}")

            try:
                image_urls = self._scraper.get_issue_image_urls(issue["url"])
            except Exception as exc:
                logger.exception("Failed to fetch image URLs for %r", title)
                self.issue_failed.emit(title, str(exc))
                continue

            if not image_urls:
                self.issue_failed.emit(title, "no pages found")
                continue

            os.makedirs(issue_dir, exist_ok=True)

            tasks = []
            for pg, img_url in enumerate(image_urls, 1):
                if not img_url:
                    continue
                ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
                tasks.append((pg, img_url, os.path.join(issue_dir, f"{pg:03d}{ext}")))

            n = len(tasks)
            self.progress_update.emit(idx, total, 0, n, title)

            done = 0
            failed = 0
            if self._delay > 0:
                # Sequential with random delay — avoids bot detection
                for pg, img_url, fp in tasks:
                    if self._cancelled:
                        break
                    try:
                        self._scraper._download_single_page(img_url, fp)
                    except Exception:
                        logger.exception("Page %d download failed for %r", pg, title)
                        failed += 1
                    done += 1
                    self.progress_update.emit(idx, total, done, n, title)
                    if not self._cancelled:
                        pause = random.uniform(self._delay * 0.5, self._delay * 1.5)
                        self._sleep(pause)
            else:
                # Concurrent — maximum speed
                with ThreadPoolExecutor(max_workers=6) as pool:
                    fmap = {
                        pool.submit(self._scraper._download_single_page, url, fp): pg
                        for pg, url, fp in tasks
                    }
                    for fut in as_completed(fmap):
                        if self._cancelled:
                            break
                        try:
                            fut.result()
                        except Exception:
                            logger.exception("Page %d download failed for %r", fmap[fut], title)
                            failed += 1
                        done += 1
                        self.progress_update.emit(idx, total, done, n, title)

            if failed:
                self.log_message.emit(f"  ⚠ {failed}/{n} page(s) failed to download")

            if self._cancelled:
                break

            # Package into CBZ / CBR if requested
            final_path = issue_dir
            if self._fmt == "cbz":
                cbz_path = issue_dir + ".cbz"
                self.log_message.emit(f"Packaging → {os.path.basename(cbz_path)}")
                _package_cbz(issue_dir, cbz_path)
                shutil.rmtree(issue_dir, ignore_errors=True)
                final_path = cbz_path
            elif self._fmt == "cbr":
                cbr_path = issue_dir + ".cbr"
                self.log_message.emit(f"Packaging → {os.path.basename(cbr_path)}")
                if _package_cbr(issue_dir, cbr_path):
                    shutil.rmtree(issue_dir, ignore_errors=True)
                    final_path = cbr_path
                else:
                    self.log_message.emit("  rar not available — saved as folder instead")

            self.issue_done.emit(title, final_path)

        self.finished_all.emit()


# ── Update checker ────────────────────────────────────────────────────────────

class UpdateCheckWorker(QThread):
    """Silently checks GitHub for a newer release and emits update_available."""
    update_available = Signal(str, str)  # latest_version, release_url

    def run(self):
        import urllib.request, json
        try:
            req = urllib.request.Request(
                _RELEASES_API,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": f"readcomics-cli/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "").lstrip("v")
            url = data.get("html_url", f"https://github.com/{_GITHUB_REPO}/releases")
            if tag and _version_gt(tag, __version__):
                self.update_available.emit(tag, url)
        except Exception:
            pass  # network errors are silently ignored


def _version_gt(a: str, b: str) -> bool:
    """Return True if version string a is strictly greater than b."""
    def _parts(v):
        try:
            return tuple(int(x) for x in v.split(".")[:3])
        except Exception:
            return (0, 0, 0)
    return _parts(a) > _parts(b)


# ── Mirror checker ────────────────────────────────────────────────────────────

class MirrorCheckWorker(QThread):
    """Probes candidate mirrors and emits the first reachable one."""
    mirror_found = Signal(str, list)   # active_url, all_mirrors (including newly discovered)
    mirror_failed = Signal()

    def __init__(self, candidates: list):
        super().__init__()
        self._candidates = list(candidates)

    def run(self):
        try:
            active, extra = detect_mirror(self._candidates)
            if active:
                all_mirrors = list(self._candidates)
                for m in extra:
                    if m not in all_mirrors:
                        all_mirrors.append(m)
                self.mirror_found.emit(active, all_mirrors)
            else:
                self.mirror_failed.emit()
        except Exception:
            logger.exception("Mirror detection failed")
            self.mirror_failed.emit()


# ── Path helpers ──────────────────────────────────────────────────────────────

def _safe_dirname(name: str) -> str:
    """Strip path-traversal sequences and filesystem-unsafe chars from a directory name."""
    name = re.sub(r'\s*:\s*', ' - ', name)        # colon → space-dash-space (e.g. "Title: Sub" → "Title - Sub")
    name = re.sub(r'[/\\*?"<>|]', '_', name)      # replace remaining filesystem-unsafe chars
    name = re.sub(r'\.\.+', '.', name)             # collapse .. sequences
    name = name.strip('. ')                         # strip leading/trailing dots/spaces
    return name or "Unknown"


# ── Comic detail cache ────────────────────────────────────────────────────────

def _cache_dir() -> Path:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "readcomics" / "comic_cache"


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _cache_load(url: str) -> dict | None:
    path = _cache_dir() / f"{_cache_key(url)}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Cache load failed for %s", url)
        return None


def _cache_save(url: str, info: dict, cover_data: bytes, issues: list) -> None:
    d = _cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_cache_key(url)}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "url": url,
                "info": info,
                "cover_b64": base64.b64encode(cover_data).decode("ascii") if cover_data else "",
                "issues": issues,
                "cached_at": time.time(),
            }, f, ensure_ascii=False)
    except Exception:
        logger.exception("Cache save failed for %s", url)


# ── Packaging helpers ─────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _image_files(directory: str) -> list:
    return sorted(p for p in Path(directory).iterdir() if p.suffix.lower() in _IMAGE_EXTS)


def _package_cbz(issue_dir: str, out_path: str) -> bool:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in _image_files(issue_dir):
            zf.write(img, img.name)
    return True


def _package_cbr(issue_dir: str, out_path: str) -> bool:
    images = [str(p) for p in _image_files(issue_dir)]
    if not images:
        return False
    try:
        result = subprocess.run(
            ["rar", "a", "-ep", "--", out_path] + images,
            capture_output=True,
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, headless: bool = True):
        super().__init__()
        self.setWindowTitle(f"ReadComics v{__version__}")
        self.setMinimumSize(1000, 650)
        self.resize(1280, 800)

        self._headless = headless
        self._scraper = ComicScraper(headless=headless)
        self._search_worker: SearchWorker | None = None
        self._detail_worker: ComicDetailWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._update_worker: UpdateCheckWorker | None = None
        self._mirror_worker: MirrorCheckWorker | None = None
        self._comics: list = []
        self._current_comic: dict | None = None
        self._current_info: dict | None = None
        self._pending_info: dict | None = None
        self._pending_cover: bytes = b""
        self._pending_comic_url: str = ""
        self._skip_cache_save: bool = False

        self._build_ui()
        self._connect_signals()
        self._start_update_check()
        self._start_mirror_check()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # Search bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for a comic title…")
        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(90)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)

        # Mirror selector
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("color: #313244;")
        search_row.addSpacing(4)
        search_row.addWidget(sep)
        search_row.addSpacing(4)
        search_row.addWidget(QLabel("Mirror:"))
        self.mirror_combo = QComboBox()
        self.mirror_combo.addItems(KNOWN_MIRRORS)
        self.mirror_combo.setCurrentText(KNOWN_MIRRORS[-1])
        self.mirror_combo.setMinimumWidth(210)
        self.mirror_combo.setToolTip(
            "Active mirror — the app probes both on startup and uses the first reachable one.\n"
            "Change manually if the auto-detected mirror is slow or broken."
        )
        search_row.addWidget(self.mirror_combo)
        self.mirror_btn = QPushButton("⟳")
        self.mirror_btn.setObjectName("secondary")
        self.mirror_btn.setFixedWidth(42)
        self.mirror_btn.setToolTip("Re-detect available mirrors")
        search_row.addWidget(self.mirror_btn)

        root.addLayout(search_row)

        # Three-panel splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: search results ──────────────────────────────────────────────
        left_box = QGroupBox("Comics")
        ll = QVBoxLayout(left_box)
        ll.setContentsMargins(6, 14, 6, 6)
        ll.setSpacing(4)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Year ↓", "Year ↑", "Name", "Status"])
        self.sort_combo.setFixedWidth(110)
        self.sort_combo.setToolTip(
            "Sort order for search results\n"
            "Year ↓ = newest first  |  Year ↑ = oldest first"
        )
        sort_row.addWidget(self.sort_combo)
        sort_row.addStretch()
        ll.addLayout(sort_row)

        self.comics_list = QListWidget()
        self.comics_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.comics_list.setWordWrap(True)
        self.comics_list.setTextElideMode(Qt.ElideNone)
        ll.addWidget(self.comics_list)
        splitter.addWidget(left_box)

        # ── Middle: comic details ─────────────────────────────────────────────
        mid_box = QGroupBox("Details")
        ml = QVBoxLayout(mid_box)
        ml.setContentsMargins(6, 14, 6, 6)
        ml.setSpacing(4)

        cache_row = QHBoxLayout()
        cache_row.addStretch()
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.setObjectName("secondary")
        self.clear_cache_btn.setFixedWidth(100)
        self.clear_cache_btn.setToolTip("Delete all locally cached comic details and issue lists")
        cache_row.addWidget(self.clear_cache_btn)
        ml.addLayout(cache_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        detail_container = QWidget()
        dvl = QVBoxLayout(detail_container)
        dvl.setContentsMargins(4, 4, 4, 4)
        dvl.setAlignment(Qt.AlignTop)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.cover_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        dvl.addWidget(self.cover_label)

        self.info_label = QLabel("Select a comic to view details.")
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)
        self.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.info_label.setMinimumWidth(1)  # lets the label shrink to container width and wrap
        dvl.addWidget(self.info_label)
        dvl.addStretch()

        scroll.setWidget(detail_container)
        ml.addWidget(scroll)
        splitter.addWidget(mid_box)

        # ── Right: issues list ────────────────────────────────────────────────
        right_box = QGroupBox("Issues")
        rl = QVBoxLayout(right_box)
        rl.setContentsMargins(6, 14, 6, 6)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Select:"))
        self.sel_all_btn = QPushButton("All")
        self.sel_all_btn.setObjectName("secondary")
        self.sel_all_btn.setFixedWidth(55)
        self.sel_none_btn = QPushButton("None")
        self.sel_none_btn.setObjectName("secondary")
        self.sel_none_btn.setFixedWidth(65)
        sel_row.addWidget(self.sel_all_btn)
        sel_row.addWidget(self.sel_none_btn)
        sel_row.addStretch()
        rl.addLayout(sel_row)

        self.issues_list = QListWidget()
        self.issues_list.setWordWrap(True)
        self.issues_list.setTextElideMode(Qt.ElideNone)
        rl.addWidget(self.issues_list)
        splitter.addWidget(right_box)

        splitter.setSizes([280, 420, 320])
        root.addWidget(splitter, stretch=1)

        # ── Bottom panel ──────────────────────────────────────────────────────
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        opts = QHBoxLayout()
        self.archive_chk = QCheckBox("Save as:")
        self.archive_chk.setToolTip("Package downloaded images into an archive")
        opts.addWidget(self.archive_chk)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["CBZ", "CBR"])
        self.fmt_combo.setEnabled(False)
        self.fmt_combo.setToolTip("CBZ = ZIP archive  |  CBR = RAR archive (requires rar binary)")
        opts.addWidget(self.fmt_combo)
        opts.addSpacing(12)
        opts.addWidget(QLabel("Delay:"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 30)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(0)
        self.delay_spin.setSuffix(" s")
        self.delay_spin.setFixedWidth(80)
        self.delay_spin.setToolTip("Random pause between image downloads (±50%) — set > 0 to avoid bot detection")
        opts.addWidget(self.delay_spin)
        opts.addSpacing(12)
        opts.addWidget(QLabel("Output:"))
        self.output_edit = QLineEdit(os.path.abspath("downloads"))
        opts.addWidget(self.output_edit, stretch=1)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.setFixedWidth(80)
        opts.addWidget(self.browse_btn)
        opts.addSpacing(12)
        self.download_btn = QPushButton("⬇  Download")
        self.download_btn.setFixedWidth(130)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setVisible(False)
        opts.addWidget(self.download_btn)
        opts.addWidget(self.cancel_btn)
        bl.addLayout(opts)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        bl.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(90)
        self.log_text.setPlaceholderText("Download log…")
        bl.addWidget(self.log_text)

        root.addWidget(bottom)

        self.statusBar().showMessage("Ready — search for a comic to get started.")

    def _connect_signals(self):
        self.search_btn.clicked.connect(self._do_search)
        self.search_input.returnPressed.connect(self._do_search)
        self.mirror_combo.currentTextChanged.connect(self._on_mirror_changed)
        self.mirror_btn.clicked.connect(self._start_mirror_check)
        self.sort_combo.currentTextChanged.connect(self._apply_sort)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.comics_list.currentRowChanged.connect(self._on_comic_selected)
        self.sel_all_btn.clicked.connect(self._select_all)
        self.sel_none_btn.clicked.connect(self._select_none)
        self.archive_chk.toggled.connect(self.fmt_combo.setEnabled)
        self.browse_btn.clicked.connect(self._browse_output)
        self.download_btn.clicked.connect(self._do_download)
        self.cancel_btn.clicked.connect(self._cancel_download)

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self._abort_detail_worker()
        self.comics_list.clear()
        self._clear_detail()
        self.issues_list.clear()
        self._set_ui_searching(True)
        self.statusBar().showMessage(f'Searching for "{query}"…')

        self._search_worker = SearchWorker(self._scraper, query)
        self._search_worker.results_ready.connect(self._on_search_done)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_done(self, results: list):
        self._set_ui_searching(False)
        self._comics = results
        self._apply_sort()
        if not results:
            self.statusBar().showMessage("No comics found — try a different query.")
        else:
            self.statusBar().showMessage(f"Found {len(results)} comic(s).")

    def _apply_sort(self, _ignored=None):
        """Sort self._comics per the current sort_combo selection and rebuild the list."""
        if not self._comics:
            return
        prev_url = self._current_comic.get("url") if self._current_comic else None

        sort_key = self.sort_combo.currentText()

        def year_key(comic):
            year_str = comic.get("publication_hint", "")
            if not year_str:
                cached = _cache_load(comic["url"])
                if cached:
                    year_str = cached.get("info", {}).get("year", "")
            m = re.search(r'\b(19|20)\d{2}\b', year_str)
            return int(m.group()) if m else 0

        def status_key(comic):
            status = comic.get("status_hint", "")
            if not status:
                cached = _cache_load(comic["url"])
                if cached:
                    status = cached.get("info", {}).get("status", "")
            return status.lower()

        if sort_key == "Year ↓":
            self._comics.sort(key=year_key, reverse=True)
        elif sort_key == "Year ↑":
            self._comics.sort(key=year_key)
        elif sort_key == "Name":
            self._comics.sort(key=lambda c: c["title"].lower())
        elif sort_key == "Status":
            self._comics.sort(key=status_key)

        self.comics_list.blockSignals(True)
        self.comics_list.clear()
        new_sel_row = -1
        for i, comic in enumerate(self._comics):
            item = QListWidgetItem(comic["title"])
            if "ongoing" in comic.get("status_hint", "").lower():
                item.setForeground(QColor("#a6e3a1"))
            else:
                item.setForeground(QColor("#cdd6f4"))
            self._set_item_tooltip(item, comic)
            self.comics_list.addItem(item)
            if comic["url"] == prev_url:
                new_sel_row = i
        if new_sel_row >= 0:
            self.comics_list.setCurrentRow(new_sel_row)
        self.comics_list.blockSignals(False)

    def _on_search_error(self, msg: str):
        self._set_ui_searching(False)
        self.statusBar().showMessage(f"Search failed: {msg}")

    # ── Comic selection ───────────────────────────────────────────────────────

    def _on_comic_selected(self, row: int):
        if row < 0 or row >= len(self._comics):
            return
        self._abort_detail_worker()
        self._clear_detail()
        self.issues_list.clear()
        comic = self._comics[row]
        self._current_comic = comic

        cached = _cache_load(comic["url"])
        if cached:
            info = cached.get("info", {})
            cover_b64 = cached.get("cover_b64", "")
            cover_data = base64.b64decode(cover_b64) if cover_b64 else b""
            issues = cached.get("issues", [])
            self._skip_cache_save = True
            self._on_info_ready(info, cover_data)
            self._on_issues_ready(issues)
            self._skip_cache_save = False
            self._pending_info = None
            self._pending_cover = b""
            self._pending_comic_url = ""
            return

        self.statusBar().showMessage(f"Loading: {comic['title']}…")
        worker = ComicDetailWorker(comic, headless=self._headless)
        self._detail_worker = worker
        worker.info_ready.connect(self._on_info_ready)
        worker.issues_ready.connect(self._on_issues_ready)
        worker.error.connect(self._on_detail_error)
        worker.start()

    def _on_info_ready(self, info: dict, cover_data: bytes):
        if not self._current_comic:
            return

        # Color the comic list entry green when the comic is ongoing.
        row = self.comics_list.currentRow()
        if row >= 0:
            item = self.comics_list.item(row)
            if item:
                if "ongoing" in info.get("status", "").lower():
                    item.setForeground(QColor("#a6e3a1"))  # Catppuccin green
                else:
                    item.setForeground(QColor("#cdd6f4"))  # default text colour

        if cover_data:
            pm = QPixmap()
            pm.loadFromData(cover_data)
            if not pm.isNull():
                self.cover_label.setPixmap(pm.scaledToWidth(200, Qt.SmoothTransformation))

        title = html.escape(self._current_comic.get("title", ""))
        lines = [f"<b style='font-size:14px;color:#cdd6f4;'>{title}</b>"]
        if info.get("publisher"):
            lines.append(f"<b>Publisher:</b> {html.escape(info['publisher'])}")
        if info.get("status"):
            lines.append(f"<b>Status:</b> {html.escape(info['status'])}")
        if info.get("year"):
            lines.append(f"<b>Year:</b> {html.escape(info['year'])}")
        if info.get("genres"):
            lines.append(f"<b>Genres:</b> {html.escape(info['genres'])}")
        if info.get("summary"):
            lines.append(f"<br><span style='color:#a6adc8;font-size:12px;'>{html.escape(info['summary'])}</span>")
        self.info_label.setText("<br>".join(lines))
        self.statusBar().showMessage(f"Loading issues for {title}…")
        self._current_info = info
        self._pending_info = info
        self._pending_cover = cover_data
        self._pending_comic_url = self._current_comic.get("url", "")
        if row >= 0 and row < len(self._comics):
            item = self.comics_list.item(row)
            if item:
                self._update_item_tooltip(item, self._comics[row]["title"], info)

    def _on_issues_ready(self, issues: list):
        self.issues_list.clear()
        for issue in issues:
            item = QListWidgetItem(issue["title"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, issue)
            item.setForeground(QColor("#cdd6f4"))
            self.issues_list.addItem(item)
        n = len(issues)
        self.statusBar().showMessage(f"{n} issue{'s' if n != 1 else ''} available.")
        row = self.comics_list.currentRow()
        if row >= 0 and row < len(self._comics):
            item = self.comics_list.item(row)
            if item and self._pending_info is not None:
                self._update_item_tooltip(item, self._comics[row]["title"], self._pending_info, n)
        if not self._skip_cache_save and self._pending_info is not None and self._pending_comic_url:
            _cache_save(self._pending_comic_url, self._pending_info, self._pending_cover, issues)
            self._pending_info = None
            self._pending_cover = b""
            self._pending_comic_url = ""

    def _on_detail_error(self, msg: str):
        self.statusBar().showMessage(f"Error loading comic: {msg}")

    # ── Issue selection ───────────────────────────────────────────────────────

    def _select_all(self):
        for i in range(self.issues_list.count()):
            self.issues_list.item(i).setCheckState(Qt.Checked)

    def _select_none(self):
        for i in range(self.issues_list.count()):
            self.issues_list.item(i).setCheckState(Qt.Unchecked)

    # ── Output directory ──────────────────────────────────────────────────────

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)

    # ── Download ──────────────────────────────────────────────────────────────

    def _do_download(self):
        selected = []
        for i in range(self.issues_list.count()):
            item = self.issues_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))

        if not selected:
            QMessageBox.information(self, "No Selection", "Check at least one issue to download.")
            return

        output_dir = self.output_edit.text().strip() or "downloads"
        fmt = self.fmt_combo.currentText().lower() if self.archive_chk.isChecked() else "folder"
        delay = self.delay_spin.value()

        if fmt == "cbr" and shutil.which("rar") is None:
            QMessageBox.warning(
                self, "RAR Unavailable",
                "The rar binary was not found on your system.\n"
                "Install it (e.g. sudo pacman -S rar) or choose CBZ instead.",
            )
            return

        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Starting…")
        self._set_ui_downloading(True)

        publisher = (self._current_info or {}).get("publisher", "")
        comic_title = (self._current_comic or {}).get("title", "")
        self._download_worker = DownloadWorker(
            self._scraper, selected, output_dir, fmt, delay,
            publisher=publisher, comic_title=comic_title,
        )
        self._download_worker.progress_update.connect(self._on_progress)
        self._download_worker.issue_done.connect(
            lambda t, p: self._append_log(f"✓  {t}  →  {p}")
        )
        self._download_worker.issue_failed.connect(
            lambda t, e: self._append_log(f"✗  {t}: {e}")
        )
        self._download_worker.log_message.connect(self._append_log)
        self._download_worker.finished_all.connect(self._on_download_done)
        self._download_worker.start()

    def _cancel_download(self):
        if self._download_worker:
            self._download_worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.statusBar().showMessage("Cancelling…")

    def _on_progress(self, idx: int, total: int, done: int, n: int, label: str):
        pct = int((idx - 1) / total * 100 + done / max(n, 1) / total * 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"[{idx}/{total}] {label} — {done}/{n} pages")
        self.statusBar().showMessage(f"Downloading [{idx}/{total}]: {label}")

    def _on_download_done(self):
        self._set_ui_downloading(False)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Complete")
        self.statusBar().showMessage("Download complete.")

    def _append_log(self, msg: str):
        self.log_text.append(msg)

    # ── UI state helpers ──────────────────────────────────────────────────────

    def _set_ui_searching(self, active: bool):
        self.search_btn.setEnabled(not active)
        self.search_input.setEnabled(not active)

    def _set_ui_downloading(self, active: bool):
        self.download_btn.setVisible(not active)
        self.cancel_btn.setVisible(active)
        self.cancel_btn.setEnabled(True)
        self.archive_chk.setEnabled(not active)
        self.fmt_combo.setEnabled(not active and self.archive_chk.isChecked())
        self.delay_spin.setEnabled(not active)
        self.output_edit.setEnabled(not active)
        self.browse_btn.setEnabled(not active)

    def _clear_detail(self):
        self.cover_label.clear()
        self.info_label.setText("Select a comic to view details.")
        self._current_comic = None

    def _update_item_tooltip(self, item: QListWidgetItem, title: str, info: dict, n_issues: int = 0) -> None:
        parts = [f"<b>{html.escape(title)}</b>"]
        if info.get("status"):
            parts.append(f"Status: {html.escape(info['status'])}")
        if info.get("year"):
            parts.append(f"Year: {html.escape(info['year'])}")
        if info.get("genres"):
            parts.append(f"Genres: {html.escape(info['genres'])}")
        if n_issues:
            parts.append(f"Issues: {n_issues}")
        item.setToolTip("<br>".join(parts))

    def _set_item_tooltip(self, item: QListWidgetItem, comic: dict) -> None:
        cached = _cache_load(comic["url"])
        if cached:
            info = cached.get("info", {})
            n = len(cached.get("issues", []))
            self._update_item_tooltip(item, comic["title"], info, n)
        else:
            # Use hints extracted directly from the search-page tooltip HTML.
            parts = [f"<b>{html.escape(comic['title'])}</b>"]
            if comic.get("status_hint"):
                parts.append(f"Status: {html.escape(comic['status_hint'])}")
            if comic.get("publication_hint"):
                parts.append(f"Publication: {html.escape(comic['publication_hint'])}")
            if comic.get("summary_hint"):
                summary = comic["summary_hint"]
                if len(summary) > 200:
                    summary = summary[:200] + "…"
                parts.append(f"<i>{html.escape(summary)}</i>")
            item.setToolTip("<br>".join(parts))

    def _clear_cache(self) -> None:
        d = _cache_dir()
        n = len(list(d.glob("*.json"))) if d.exists() else 0
        if n == 0:
            self.statusBar().showMessage("Cache is already empty.")
            return
        reply = QMessageBox.question(
            self, "Clear Cache",
            f"Delete cached details for {n} comic{'s' if n != 1 else ''}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            shutil.rmtree(d, ignore_errors=True)
            self.statusBar().showMessage(f"Cleared cache ({n} comic{'s' if n != 1 else ''} removed).")

    def _abort_detail_worker(self):
        if self._detail_worker is None:
            return
        if self._detail_worker.isRunning():
            self._detail_worker.cancel()
        # Always disconnect specific slots — avoids both double-callbacks on the next
        # load and the PySide6 RuntimeWarning from calling disconnect() with no args.
        for sig, slot in (
            (self._detail_worker.info_ready,   self._on_info_ready),
            (self._detail_worker.issues_ready, self._on_issues_ready),
            (self._detail_worker.error,        self._on_detail_error),
        ):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    # ── Update check ──────────────────────────────────────────────────────────

    def _start_update_check(self):
        self._update_worker = UpdateCheckWorker()
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, latest: str, url: str):
        self.statusBar().showMessage(
            f"Update available: v{latest} — visit {url}"
        )

    # ── Mirror detection ──────────────────────────────────────────────────────

    def _start_mirror_check(self):
        candidates = [self.mirror_combo.itemText(i) for i in range(self.mirror_combo.count())]
        self.mirror_btn.setEnabled(False)
        self.statusBar().showMessage("Checking mirrors…")
        self._mirror_worker = MirrorCheckWorker(candidates)
        self._mirror_worker.mirror_found.connect(self._on_mirror_found)
        self._mirror_worker.mirror_failed.connect(self._on_mirror_failed)
        self._mirror_worker.start()

    def _on_mirror_found(self, active: str, all_mirrors: list):
        self.mirror_btn.setEnabled(True)
        existing = {self.mirror_combo.itemText(i) for i in range(self.mirror_combo.count())}
        for m in all_mirrors:
            if m not in existing:
                self.mirror_combo.addItem(m)
        # Apply without firing _on_mirror_changed (which would show a redundant message)
        self.mirror_combo.blockSignals(True)
        self.mirror_combo.setCurrentText(active)
        self.mirror_combo.blockSignals(False)
        self._scraper.base_url = active
        self.statusBar().showMessage(f"Mirror: {active}")
        logger.debug("Active mirror: %s", active)

    def _on_mirror_failed(self):
        self.mirror_btn.setEnabled(True)
        self.statusBar().showMessage(
            "No mirror reachable — check your connection or select a mirror manually."
        )
        logger.warning("All mirrors unreachable")

    def _on_mirror_changed(self, url: str):
        if url:
            self._scraper.base_url = url
            self.statusBar().showMessage(f"Mirror set to: {url}")
            logger.debug("Mirror changed to: %s", url)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._abort_detail_worker()
        if self._detail_worker and self._detail_worker.isRunning():
            self._detail_worker.wait(2000)
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
            self._download_worker.quit()
            self._download_worker.wait(3000)
        try:
            self._scraper.close()
        except Exception:
            pass
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ReadComics GUI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging to stderr")
    parser.add_argument("--no-headless", action="store_true", help="Show the Playwright browser window (debug)")
    args, qt_args = parser.parse_known_args()
    _setup_logging(args.verbose)
    logger.debug("GUI starting")

    app = QApplication(sys.argv[:1] + qt_args)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    window = MainWindow(headless=not args.no_headless)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
