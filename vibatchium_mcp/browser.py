"""Browser pool: N parallel headless Chrome sessions.

Real backend uses Playwright (lazy import, stealth args). Demo backend
returns scripted page data so agents can be developed/tested with no
browser installed.
"""
import logging
import time
import uuid

log = logging.getLogger(__name__)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# Scripted pages for the demo backend (url -> page data)
DEMO_PAGES = {
    "https://example.com": {
        "title": "Example Domain",
        "text": "Example Domain\nThis domain is for use in illustrative examples in documents.",
        "links": ["https://www.iana.org/domains/example"],
    },
    "https://news.example.com": {
        "title": "Example News",
        "text": "Example News\nLocal AI models beat cloud APIs on latency in new benchmark.",
        "links": ["https://news.example.com/ai", "https://news.example.com/about"],
    },
}


class Page:
    def __init__(self, url: str, title: str, text: str, links: list[str]):
        self.url = url
        self.title = title
        self.text = text
        self.links = links


class Session:
    def __init__(self, session_id: str, backend):
        self.id = session_id
        self.backend = backend
        self.created = time.time()
        self.current: Page | None = None
        self.history: list[str] = []


class DemoBackend:
    """No-browser backend: scripted responses, same interface as PlaywrightBackend."""

    name = "demo"

    def navigate(self, session: Session, url: str) -> Page:
        data = DEMO_PAGES.get(url, {
            "title": f"Demo page: {url}",
            "text": f"(demo) Rendered {url}\nNo browser installed — install playwright for live pages.",
            "links": [],
        })
        page = Page(url, data["title"], data["text"], data["links"])
        session.current = page
        session.history.append(url)
        return page

    def click(self, session: Session, selector: str) -> str:
        return f"(demo) clicked {selector} on {session.current.url if session.current else 'about:blank'}"

    def type(self, session: Session, selector: str, text: str) -> str:
        return f"(demo) typed {len(text)} chars into {selector}"

    def screenshot(self, session: Session, path: str) -> str:
        # Render a labelled placeholder PNG so the artifact is real
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (960, 600), (13, 17, 23))
            d = ImageDraw.Draw(img)
            url = session.current.url if session.current else "about:blank"
            d.text((30, 30), f"(demo screenshot) {url}", fill=(201, 209, 217))
            d.text((30, 60), "Install playwright + chromium for live captures.", fill=(139, 148, 158))
            img.save(path)
            return path
        except ImportError:
            with open(path, "wb") as f:
                f.write(b"demo-screenshot-placeholder")
            return path

    def close(self, session: Session) -> None:
        pass


class PlaywrightBackend:
    """Real backend: persistent headless Chromium per session (lazy import)."""

    name = "playwright"

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwright is not installed. Install with "
                "'pip install -r requirements-full.txt && playwright install chromium', "
                "or run with --demo."
            ) from e
        self._pw = sync_playwright().start()
        self._browsers: dict[str, object] = {}

    def _browser(self, session: Session):
        if session.id not in self._browsers:
            browser = self._pw.chromium.launch(headless=True, args=STEALTH_ARGS)
            ctx = browser.new_context(
                user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
                viewport={"width": 1366, "height": 768},
            )
            page = ctx.new_page()
            self._browsers[session.id] = (browser, ctx, page)
        return self._browsers[session.id][2]

    def navigate(self, session: Session, url: str) -> Page:
        page = self._browser(session)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        p = Page(url=page.url, title=page.title(),
                 text=page.inner_text("body")[:20000], links=[])
        session.current = p
        session.history.append(p.url)
        return p

    def click(self, session: Session, selector: str) -> str:
        self._browser(session).click(selector, timeout=10000)
        return f"clicked {selector}"

    def type(self, session: Session, selector: str, text: str) -> str:
        self._browser(session).fill(selector, text, timeout=10000)
        return f"typed into {selector}"

    def screenshot(self, session: Session, path: str) -> str:
        self._browser(session).screenshot(path=path)
        return path

    def close(self, session: Session) -> None:
        if session.id in self._browsers:
            browser, ctx, _ = self._browsers.pop(session.id)
            ctx.close()
            browser.close()


class SessionPool:
    """Owns N sessions; backend chosen once (playwright or demo)."""

    def __init__(self, max_sessions: int = 4, demo: bool = False):
        self.max_sessions = max_sessions
        self.demo = demo
        self.backend = DemoBackend()
        self.sessions: dict[str, Session] = {}
        if not demo:
            try:
                self.backend = PlaywrightBackend()
                log.info("Playwright backend ready")
            except RuntimeError as e:
                log.warning("%s Falling back to demo backend.", e)
                self.backend = DemoBackend()

    def open(self) -> Session:
        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError(f"Session limit reached ({self.max_sessions})")
        sid = "sess_" + uuid.uuid4().hex[:8]
        s = Session(sid, self.backend)
        self.sessions[sid] = s
        return s

    def get(self, session_id: str) -> Session:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise KeyError(f"Unknown session: {session_id}") from None

    def close(self, session_id: str) -> None:
        s = self.sessions.pop(session_id, None)
        if s:
            self.backend.close(s)

    def list(self) -> list[dict]:
        return [{"id": s.id, "url": s.current.url if s.current else None,
                 "age_s": round(time.time() - s.created, 1)}
                for s in self.sessions.values()]
