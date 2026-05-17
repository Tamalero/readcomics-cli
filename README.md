# ReadComics

A desktop GUI for browsing and downloading comics from [rcostation.xyz](https://rcostation.xyz).

Automatic mirror detection, cover art previews, CBZ/CBR packaging, and a dark Catppuccin Mocha theme.

---

## Screenshots

![Search results with comic details](docs/screenshot-results.png)

![Main window](docs/screenshot-empty.png)

---

## Download & Install

### Windows — no setup required

1. Download `ReadComics-Windows.zip` from the [Releases](https://github.com/Tamalero/readcomics-cli/releases) page.
2. Extract the zip anywhere (e.g. `C:\Apps\ReadComics\`).
3. Double-click **`ReadComics.exe`** to launch.

Everything is bundled: Python, PySide6, Playwright, and Firefox. No installation needed.

> **Note:** Windows SmartScreen may show a warning the first time you run the app because the executable is not code-signed. Click **More info → Run anyway** to proceed.

---

### Linux — AppImage, no setup required

1. Download `ReadComics-x86_64.AppImage` from the [Releases](https://github.com/Tamalero/readcomics-cli/releases) page.
2. Make it executable and run:

```sh
chmod +x ReadComics-x86_64.AppImage
./ReadComics-x86_64.AppImage
```

Everything is bundled: Python 3.12, PySide6, Playwright, and Firefox. No installation needed.

> **Delta updates** — if you already have a previous version you can use [AppImageUpdate](https://github.com/AppImageCommunity/AppImageUpdate) with the `.zsync` file from the release to download only the changed bytes.

---

### From source (Linux/macOS — requires Python 3.10+ and [fish shell](https://fishshell.com/))

```sh
git clone https://github.com/Tamalero/readcomics-cli.git
cd readcomics-cli
fish start.fish
```

`start.fish` does everything automatically:

- Creates a Python virtual environment if one does not exist.
- Installs all dependencies from `requirements.txt`.
- Downloads the Playwright Firefox browser (one-time, ~80 MB).
- Launches the GUI.

#### Launcher flags

| Flag | Effect |
|---|---|
| `--verbose` / `-v` | Show full pip/playwright output and write debug logs to stderr |
| `--no-headless` | Show the Firefox browser window (useful for debugging scraping) |

---

### Build the Windows version yourself

If you prefer to build from source on Windows, you only need **Python 3.10+** installed ([python.org](https://www.python.org/downloads/) — check *Add to PATH* during install). Then open PowerShell in the repo folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File build-windows.ps1
```

The script will:
1. Create a virtual environment and install all Python packages.
2. Download Playwright Firefox (~80 MB, cached for re-runs).
3. Run PyInstaller to bundle everything.
4. Assemble the final `dist\ReadComics\` folder.

Zip `dist\ReadComics\` and distribute — the folder is fully self-contained.

---

## Using the app

### 1 — Mirror detection

When the app starts it automatically probes all known mirrors and selects the first one that is actually serving the site.

- The active mirror is shown in the **Mirror** drop-down in the top bar.
- Use the drop-down to switch mirrors manually at any time.
- Click **⟳** to re-probe mirrors (useful if the current mirror goes down mid-session).
- If the site advertises a backup domain on its homepage, that domain is automatically added to the list.

### 2 — Search

Type a comic title in the search box and press **Search** or hit Enter. Results appear in the **Comics** column.

- Comics with **Ongoing** status are highlighted in green.
- Use the **Sort** drop-down above the list to order results by **Year ↓** (newest first, default), **Year ↑**, **Name**, or **Status**.
- Hover over any comic to see its status, publication date, and summary without clicking.

### 3 — Browse details

Click any comic to load its cover art, metadata, and full issue list:

- **Publisher**, **Status**, **Year**, **Genres**, and **Summary** appear in the **Details** column.
- Detail data is cached locally — clicking the same comic a second time is instant.
- The **Issues** column lists every available issue, all checked by default.
- Click **Clear Cache** (top-right of the Details column) to force a fresh reload.

### 4 — Select issues

Use the **All** / **None** buttons to check or uncheck everything, or tick individual issues manually.

### 5 — Configure download options

| Option | Description |
|---|---|
| **Save as** checkbox | When checked, package images into an archive instead of a folder |
| **CBZ** | ZIP archive renamed `.cbz` — works everywhere, no extra software needed |
| **CBR** | RAR archive — requires the `rar` binary (Linux: `sudo pacman -S rar` / `sudo apt install rar`) |
| **Delay** | Seconds between individual image downloads. `0` = fast concurrent mode. `> 0` = sequential with ±50 % random jitter to reduce rate-limiting. |
| **Output** | Folder where comics are saved. Click **Browse…** to pick one. |

Downloads are organised as:

```
<output>/
└── <Publisher>/
    └── <Comic Title>/
        ├── <Comic Title> Issue #1/
        │   ├── 001.jpg
        │   ├── 002.jpg
        │   └── …
        └── <Comic Title> Issue #2/
            └── …
```

When **Save as CBZ/CBR** is selected the image folder is replaced by a single archive file:

```
<output>/<Publisher>/<Comic Title>/<Comic Title> Issue #1.cbz
```

### 6 — Download

Click **⬇ Download**. Progress is shown in the bar and the log panel below it.

- Issues that already exist on disk are **skipped automatically** — safe to re-run after an interruption.
- Click **Cancel** to stop mid-download cleanly.

---

## CLI fallback (Linux/macOS)

A Rich-powered terminal interface is also available for headless or scripting use:

```sh
python main.py                        # interactive session
python main.py -s "Batman"            # skip the search prompt
python main.py -o ~/Comics            # custom output directory
python main.py --no-headless          # show the browser window
```

---

## Why Firefox?

The site uses Cloudflare protection and blocks all Chromium-based browsers at the network level (returns 404 on every comic page). Playwright Firefox is the only browser that works and is bundled in both the Windows and Linux distributions.

---

## Dependencies

| Package | Purpose |
|---|---|
| [PySide6](https://pypi.org/project/PySide6/) | Qt6 GUI framework |
| [Playwright](https://playwright.dev/python/) | Headless Firefox for pages behind Cloudflare |
| [httpx](https://www.python-httpx.org/) | HTTP client for image downloads and mirror probing |
| [Rich](https://github.com/Textualize/rich) | Terminal tables and progress bars (CLI mode) |
| [Pillow](https://python-pillow.org/) | Icon generation during build |

---

## License

This project is for educational and personal use only.
