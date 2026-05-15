import os
import threading
from urllib.parse import urljoin, urlparse

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


class ComicScraper:
    """Scrapes rcostation.xyz for comic search, issue listing, and page downloading."""

    def __init__(self, base_url="https://rcostation.xyz", headless=True):
        self.base_url = base_url
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._browser_tid = None
        self._browser_lock = threading.Lock()
        self._ctx = None          # one shared context per thread (preserves cookies/session)
        self._ctx_tid = None
        self._ctx_lock = threading.Lock()
        self._http = httpx.Client(timeout=30, follow_redirects=True)

    # ---------- Context manager ----------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ---------- Lazy browser ----------

    @property
    def browser(self):
        with self._browser_lock:
            current_tid = threading.get_ident()
            if self._browser is not None and self._browser_tid != current_tid:
                # Owning thread has exited; its greenlet context is dead — recreate.
                try:
                    self._browser.close()
                except Exception:
                    pass
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._browser = None
                self._playwright = None
            if self._browser is None:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.firefox.launch(headless=self._headless)
                self._browser_tid = current_tid
        return self._browser

    @property
    def _session_ctx(self):
        """One browser context per thread so cookies/session are shared across pages."""
        with self._ctx_lock:
            current_tid = threading.get_ident()
            if self._ctx is not None and self._ctx_tid != current_tid:
                try:
                    self._ctx.close()
                except Exception:
                    pass
                self._ctx = None
            if self._ctx is None:
                self._ctx = self.browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                self._ctx_tid = current_tid
        return self._ctx

    def _new_page(self):
        return self._session_ctx.new_page()

    # ---------- Search ----------

    def search(self, query):
        """
        Search for comics by keyword.

        The site's submit button has onclick="return false;" so we bypass it
        by calling formSearch.submit() directly from JS, which ignores button
        event handlers and POST-submits the form to the server.

        Returns a list of dicts: [{"title": str, "url": str, "thumbnail": str}]
        """
        page = self._new_page()
        try:
            page.goto(self.base_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            search_input = page.locator("#keyword")
            search_input.wait_for(state="visible", timeout=10000)
            search_input.fill(query)
            search_input.press("Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            try:
                page.wait_for_selector("a[href*='/Comic/']", timeout=10000)
            except PlaywrightTimeout:
                return []

            items = page.eval_on_selector_all(
                "a[href*='/Comic/']",
                """els => els.map(e => {
                    const img = e.querySelector('img');
                    // Collect every plausible title source and keep the longest one,
                    // since the hover tooltip is usually the most complete string.
                    const candidates = [
                        e.getAttribute('title'),
                        img && img.getAttribute('alt'),
                        e.querySelector('p, span, h4, h3, .title, .name') &&
                            e.querySelector('p, span, h4, h3, .title, .name').textContent,
                        e.textContent,
                    ].map(s => (s || '').trim()).filter(Boolean);
                    const text = candidates.reduce((a, b) => b.length > a.length ? b : a, '');
                    return {
                        href: (new URL(e.getAttribute('href') || e.href, document.baseURI)).pathname,
                        text: text,
                        thumb: img ? img.src : ''
                    };
                })""",
            )

            results = []
            seen = set()
            for item in items:
                href = item.get("href", "")
                if not href:
                    continue
                raw_path = href.split("?")[0]
                parts = raw_path.strip("/").split("/")
                if len(parts) != 2 or parts[0].lower() != "comic":
                    continue
                link = urljoin(self.base_url, raw_path)
                if link in seen:
                    continue
                seen.add(link)
                title = " ".join(item.get("text", "").split())
                if not title:
                    slug = urlparse(link).path.rstrip("/").split("/")[-1]
                    title = slug.replace("-", " ").replace("_", " ")
                    title = " ".join(title.split())
                thumb = item.get("thumb", "")
                if thumb and not thumb.startswith("http"):
                    thumb = urljoin(self.base_url, thumb)
                results.append({"title": title, "url": link, "thumbnail": thumb})

            return results
        finally:
            page.close()

    # ---------- Comic info ----------

    def get_comic_info(self, comic_url):
        """
        Fetch metadata for a comic: cover image URL, summary, genres, status, etc.

        Returns a dict with keys: cover, summary, genres, status, year, publisher.
        All values are strings (empty string if not found).
        """
        page = self._new_page()
        try:
            page.goto(comic_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass

            info = page.evaluate("""() => {
                const result = {cover: '', summary: '', genres: '', status: '', year: '', publisher: ''};

                const imgs = document.querySelectorAll('img');
                for (const img of imgs) {
                    if (img.src && img.src.includes('/Uploads/') && img.naturalWidth > 50) {
                        result.cover = img.src;
                        break;
                    }
                }

                const bc = document.querySelector('.barContent');
                if (bc) {
                    const paragraphs = bc.querySelectorAll('p');
                    for (const p of paragraphs) {
                        const label = p.querySelector('span.info');
                        if (!label) continue;
                        const key = (label.textContent || '').trim().toLowerCase().replace(':', '');

                        if (key === 'genres' || key === 'genre') {
                            const links = p.querySelectorAll('a');
                            const genres = [];
                            for (const a of links) {
                                const t = (a.textContent || '').trim();
                                if (t && t !== '.') genres.push(t);
                            }
                            result.genres = genres.join(', ');
                        } else {
                            let val = p.textContent || '';
                            val = val.replace(label.textContent || '', '').trim();
                            val = val.replace(/^[:\\s]+/, '').trim();
                            val = val.split('\\n')[0].replace(/\\u00a0/g, ' ').trim();

                            if (key === 'status')           result.status = val;
                            if (key === 'year of release')  result.year = val;
                            if (key === 'publisher')        result.publisher = val;
                        }
                    }

                    for (const p of paragraphs) {
                        if (p.querySelector('span.info')) continue;
                        const text = (p.textContent || '').trim();
                        if (text.length > 40) {
                            result.summary = text;
                            break;
                        }
                    }
                }

                return result;
            }""")

            return info if isinstance(info, dict) else {
                "cover": "", "summary": "", "genres": "", "status": "", "year": "", "publisher": ""
            }
        finally:
            page.close()

    # ---------- Issues ----------

    def get_issues(self, comic_url):
        """
        Get the list of issues for a comic.

        Returns a list of dicts: [{"title": str, "url": str}, ...]
        """
        page = self._new_page()
        try:
            page.goto(comic_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass
            page.wait_for_selector("a[href]", timeout=10000)

            items = page.eval_on_selector_all(
                "a[href]",
                """els => els.map(e => ({
                    href: (new URL(e.getAttribute('href') || e.href, document.baseURI)).pathname,
                    text: (e.textContent || '').trim()
                }))""",
            )

            parsed_comic = urlparse(comic_url)
            comic_path = parsed_comic.path.rstrip("/")
            comic_slug = None
            if "/Comic/" in comic_path:
                try:
                    comic_slug = comic_path.split("/Comic/")[1]
                except Exception:
                    pass

            issues = []
            seen = set()
            for item in items:
                href = item.get("href", "")
                if not href:
                    continue
                raw_path = href.split("?")[0]
                link = urljoin(self.base_url, raw_path)
                path = urlparse(link).path.rstrip("/")

                # Accept any link that lives under /Comic/{slug}/ — the old
                # "/Issue-" check was case-sensitive and broke on variant slugs.
                is_under_comic = (
                    comic_slug
                    and path.lower().startswith(f"/comic/{comic_slug.lower()}/")
                    and path != comic_path
                )
                if not is_under_comic:
                    continue

                if link in seen:
                    continue
                seen.add(link)

                title = " ".join(item.get("text", "").split())
                if not title:
                    slug = path.split("/")[-1]
                    title = slug.replace("-", " ").replace("_", " ")
                    title = " ".join(title.split())

                issues.append({"title": title, "url": link})

            return issues
        finally:
            page.close()

    # ---------- Page images ----------

    def get_issue_image_urls(self, issue_url):
        """
        Navigate to the issue in all-pages mode (readType=1), scroll to trigger
        lazy-loading, then collect all real image URLs.

        Returns a list of image URL strings, one per comic page.
        """
        separator = "&" if "?" in issue_url else "?"
        all_pages_url = f"{issue_url}{separator}readType=1"

        page = self._new_page()
        try:
            page.goto(all_pages_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            try:
                page.wait_for_selector("div#divImage img", timeout=15000)
            except PlaywrightTimeout:
                return []

            page.evaluate("""async () => {
                const imgs = document.querySelectorAll('div#divImage img');
                for (const img of imgs) {
                    img.scrollIntoView({behavior: 'instant'});
                    await new Promise(r => setTimeout(r, 250));
                }
                for (const img of imgs) {
                    if (img.src.includes('blank.gif') || !img.src) {
                        img.scrollIntoView({behavior: 'instant'});
                        await new Promise(r => setTimeout(r, 300));
                    }
                }
                const deadline = Date.now() + 15000;
                while (Date.now() < deadline) {
                    const blanks = [...imgs].filter(
                        i => i.style.display !== 'none' && (i.src.includes('blank.gif') || !i.src)
                    );
                    if (blanks.length === 0) break;
                    blanks[0].scrollIntoView({behavior: 'instant'});
                    await new Promise(r => setTimeout(r, 500));
                }
            }""")

            image_urls = page.evaluate("""() => {
                const imgs = document.querySelectorAll('div#divImage img');
                const urls = [];
                for (const img of imgs) {
                    const src = img.src || '';
                    if (img.style.display === 'none') continue;
                    if (!src || src.includes('blank.gif')) continue;
                    urls.push(src);
                }
                return urls;
            }""")

            return image_urls if isinstance(image_urls, list) else []
        finally:
            page.close()

    # ---------- Download ----------

    def _download_single_page(self, img_url, filepath):
        """Download a single image to disk. Raises on failure."""
        if os.path.exists(filepath):
            return
        response = self._http.get(img_url)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)

    # ---------- Browser lifecycle ----------

    def reset_browser(self):
        """Tear down the current browser so the next call gets a fresh one.
        Call this at the start of every QThread.run() to avoid greenlet reuse."""
        with self._ctx_lock:
            if self._ctx:
                try:
                    self._ctx.close()
                except Exception:
                    pass
                self._ctx = None
            self._ctx_tid = None
        with self._browser_lock:
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self._browser_tid = None

    # ---------- Cleanup ----------

    def close(self):
        """Release all resources (browser, playwright, HTTP client)."""
        if self._ctx:
            try:
                self._ctx.close()
            except Exception:
                pass
            self._ctx = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        if self._http:
            try:
                self._http.close()
            except Exception:
                pass
