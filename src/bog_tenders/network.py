from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (compatible; BOGFetch/1.0)"
verify_ssl = False

BASE_URL = "https://www.bog.gov.gh/wp-content/uploads"
AUCTION_PAGE = "https://www.bog.gov.gh/gog_auction_results"


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
    return (
        f"{BASE_URL}/{d.year:04d}/{d.month:02d}/Auctresults-{tender_number}{suffix}.pdf"
    )


def probe_urls_for_tender(tender_number: int, d: date) -> list[str]:
    urls: list[str] = []
    for md in month_variants(d):
        urls.append(pdf_url(tender_number, md))
        urls.append(pdf_url(tender_number, md, suffix="x"))
    return urls


def auction_page_url(tender_number: int) -> str:
    return f"{AUCTION_PAGE}/results-of-gog-tender-{tender_number}/"


def url_exists(url: str) -> bool:
    try:
        r = requests.head(
            url,
            timeout=10,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=verify_ssl,
        )
        return r.status_code == 200
    except Exception:
        return False


def download_file(url: str, filepath: Path) -> bool:
    try:
        r = requests.get(
            url,
            timeout=30,
            stream=True,
            headers={"User-Agent": USER_AGENT},
            verify=verify_ssl,
        )
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
        r = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
            verify=verify_ssl,
        )
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


def extract_download_url(html: str) -> str | None:
    class _LinkFinder(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.url: str | None = None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag != "a" or self.url is not None:
                return
            attr_dict = dict(attrs)
            classes = (attr_dict.get("class") or "").split()
            if "jet-button__instance" in classes:
                self.url = attr_dict.get("href")

    parser = _LinkFinder()
    parser.feed(html)
    return parser.url
