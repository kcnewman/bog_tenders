from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (compatible; BOGFetch/1.0)"
BASE_URL = "https://www.bog.gov.gh/wp-content/uploads"
AUCTION_PAGE = "https://www.bog.gov.gh/gog_auction_results"

_verify_ssl = os.environ.get("TENDERS_VERIFY_SSL", "").lower() in ("1", "true", "yes")
_ssl_warned = False


def _warn_insecure() -> None:
    global _ssl_warned
    if not _verify_ssl and not _ssl_warned:
        _ssl_warned = True
        print(
            "warning: SSL verification disabled; set TENDERS_VERIFY_SSL=1 to enable",
            file=sys.stderr,
        )


def configure_ssl(verify: bool) -> None:
    global _verify_ssl
    _verify_ssl = verify
    _SessionPool.clear()


class _SessionPool:
    _local = threading.local()

    @classmethod
    def get(cls) -> requests.Session:
        _warn_insecure()
        session = getattr(cls._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            session.verify = _verify_ssl
            session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
            cls._local.session = session
        return session

    @classmethod
    def clear(cls) -> None:
        cls._local.session = None


def month_variants(d: date) -> list[date]:
    return [
        date(d.year, m, 1)
        for m in (d.month, d.month - 1, d.month + 1)
        if 1 <= m <= 12
        and not (m == d.month - 1 and d.day > 3)
        and not (m == d.month + 1 and d.day < 29)
    ]


def pdf_url(tender_number: int, d: date, suffix: str = "") -> str:
    return (
        f"{BASE_URL}/{d.year:04d}/{d.month:02d}/Auctresults-{tender_number}{suffix}.pdf"
    )


def probe_urls_for_tender(tender_number: int, d: date) -> list[str]:
    return [
        pdf_url(tender_number, md, s) for md in month_variants(d) for s in ("", "x")
    ]


def auction_page_url(tender_number: int) -> str:
    return f"{AUCTION_PAGE}/results-of-gog-tender-{tender_number}/"


def url_exists(url: str) -> bool:
    try:
        return (
            _SessionPool.get().head(url, timeout=10, allow_redirects=True).status_code
            == 200
        )
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
        self.url = self.fallback = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_dict = dict(attrs)
        href = attr_dict.get("href") or ""
        if (
            self.url is None
            and "jet-button__instance" in (attr_dict.get("class") or "").split()
        ):
            self.url = href
        if self.fallback is None and href.lower().endswith(".pdf"):
            self.fallback = href


def extract_download_url(html: str) -> str | None:
    parser = _LinkFinder()
    parser.feed(html)
    return parser.url or parser.fallback
