# ReadComics

A desktop GUI for browsing and downloading comics from [rcostation.xyz](https://rcostation.xyz).

Automatic mirror detection, cover art previews, CBZ/CBR packaging, and a dark Catppuccin Mocha theme.

---

## Screenshots

![Search results with comic details](docs/screenshot-results.png)

![Main window](docs/screenshot-empty.png)

---

## Install

### AppImage — no setup required (Linux)

1. Download `ReadComics-x86_64.AppImage` from the [Releases](https://github.com/Tamalero/readcomics-cli/releases) page.
2. Make it executable and run:

```sh
chmod +x ReadComics-x86_64.AppImage
./ReadComics-x86_64.AppImage
```

Everything is bundled: Python 3.12, PySide6, Playwright, and Firefox. No installation needed.

> **Delta updates** — if you already have a previous version you can use [AppImageUpdate](https://github.com/AppImageCommunity/AppImageUpdate) with the `.zsync` file from the release to download only the changed bytes.

---

### From source (requires Python 3.10+ and [fish shell](https://fishshell.com/))

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

## Using the GUI

### 1 — Mirror detection

When the app starts it automatically probes all known mirrors and selects the first one that is actually serving the site (not just reachable — it checks that the search form is present in the response).

- The active mirror is shown in the **Mirror** drop-down in the top bar.
- Use the drop-down to switch mirrors manually at any time.
- Click **⟳** to re-probe mirrors (useful if the current mirror stops working mid-session).
- If the site advertises a backup domain on its homepage, that domain is automatically added to the list.

### 2 — Search

Type a comic title in the search box and press **Search** or hit Enter. Results appear in the **Comics** column on the left.

- Comics whose status is **Ongoing** are highlighted in green.

### 3 — Browse details

Click any comic in the list to load its cover art, metadata, and full issue list:

- **Publisher**, **Status**, **Year**, **Genres**, and a short **Summary** appear in the **Details** column.
- The **Issues** column on the right lists every available issue, all checked by default.

### 4 — Select issues

Use the **All** / **None** buttons to check or uncheck everything, or tick individual issues manually.

### 5 — Configure download options

| Option | Description |
|---|---|
| **Save as** checkbox | When checked, package downloaded images into an archive |
| **CBZ** | ZIP archive renamed to `.cbz` — works everywhere, no extra software needed |
| **CBR** | RAR archive — requires the `rar` binary (`sudo pacman -S rar` / `sudo apt install rar`) |
| **Delay** | Seconds to wait between individual image downloads (0 = fast concurrent mode, > 0 = sequential with ±50 % random jitter to avoid rate-limiting) |
| **Output** | Directory where comics are saved. Click **Browse…** to pick a folder. |

Downloads are organised as:

```
<output>/<Comic Title>/<Issue Title>/001.jpg, 002.jpg, …
```

CBZ/CBR archives are placed at `<output>/<Comic Title>/<Issue Title>.cbz` and the image folder is removed.

### 6 — Download

Click **⬇ Download**. Progress is shown in the bar and the log panel below it. Click **Cancel** to stop mid-download cleanly.

---

## CLI fallback

A Rich-powered terminal interface is also available for headless or scripting use:

```sh
python main.py                        # interactive session
python main.py -s "Batman"            # skip the search prompt
python main.py -o ~/Comics            # custom output directory
python main.py --no-headless          # show the browser window
```

---

## Why Firefox?

The site blocks all Chromium-based browsers at the network level (returns 404 on every request). Playwright Firefox is required and is bundled in the AppImage.

---

## Dependencies

| Package | Purpose |
|---|---|
| [PySide6](https://pypi.org/project/PySide6/) | Qt6 GUI framework |
| [Playwright](https://playwright.dev/python/) | Headless Firefox for pages behind Cloudflare |
| [httpx](https://www.python-httpx.org/) | HTTP client for image downloads and mirror probing |
| [Rich](https://github.com/Textualize/rich) | Terminal tables and progress bars (CLI mode) |
| [Pillow](https://python-pillow.org/) | Cover art rendering in the terminal (CLI mode) |

---

## License

This project is for educational and personal use only.
