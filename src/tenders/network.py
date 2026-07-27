from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import threading

import requests
from requests.adapters import HTTPAdapter
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (compatible; BOGFetch/1.0)"
verify_ssl = False
BASE_URL = "https://www.bog.gov.gh/wp-content/uploads"
AUCTION_PAGE = "https://www.bog.gov.gh/gog_auction_results"


class _SessionPool:
    _local = threading.local()

    @classmethod
    def get(cls) -> requests.Session:
        session = getattr(cls._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            session.verify = verify_ssl
            session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
            cls._local.session = session
        return session


def month_variants(d: date) -> list[date]:
    y, m = d.year, d.month
    variants: list[date] = []
    for dm in (0, -1, 1):
        nm = m + dm
        if nm < 1 or nm > 12:
            continue
        if dm == -1 and d.day > 3:
            continue
        if dm == 1 and d.day < 29:
            continue
        variants.append(date(y, nm, 1))
    return variants


def pdf_url(tender_number: int, d: date, suffix: str = "") -> str:
    return f"{BASE_URL}/{d.year:04d}/{d.month:02d}/Auctresults-{tender_number}{suffix}.pdf"


def probe_urls_for_tender(tender_number: int, d: date) -> list[str]:
    return [pdf_url(tender_number, md, s)
            for md in month_variants(d)
            for s in ("", "x")]


def auction_page_url(tender_number: int) -> str:
    return f"{AUCTION_PAGE}/results-of-gog-tender-{tender_number}/"


def url_exists(url: str) -> bool:
    try:
        return _SessionPool.get().head(url, timeout=10, allow_redirects=True).status_code == 200
    except Exception:
        return False


def download_file(url: str, filepath: Path) -> bool:
    try:
        r = _SessionPool.get().get(url, timeout=30, stream=True)
        if r.status_code != 200:
            return False
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    download error: {e}", file=sys.stderr)
        return False


def probe_urls(urls: list[str], max_workers: int = 8) -> str | None:
    if not urls:
        return None
    with ThreadPoolExecutor(max_workers=min(max_workers, len(urls))) as ex:
        fut_to_url = {ex.submit(url_exists, url): url for url in urls}
        for fut in as_completed(fut_to_url):
            if fut.result():
                return fut_to_url[fut]
    return None


def fetch_page(url: str) -> str | None:
    try:
        r = _SessionPool.get().get(url, timeout=30)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


class _LinkFinder(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.url: str | None = None
        self.fallback: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_dict = dict(attrs)
        href = attr_dict.get("href") or ""
        if self.url is None:
            if "jet-button__instance" in (attr_dict.get("class") or "").split():
                self.url = href
        if self.fallback is None and href.lower().endswith(".pdf"):
            self.fallback = href


def extract_download_url(html: str) -> str | None:
    parser = _LinkFinder()
    parser.feed(html)
    return parser.url or parser.fallback
