"""HTTP operations: probe, download, SSL config."""

from __future__ import annotations

import ssl
import sys
import time
import urllib.request
from pathlib import Path

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore[union-attr]
except ImportError:
    pass

USER_AGENT = "Mozilla/5.0 (compatible; BOGFetch/1.0)"
has_requests = _requests is not None
verify_ssl = False  # BOG's cert chain doesn't verify on many systems


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def url_exists(url: str) -> bool:
    """HEAD request — returns True if server responds 200."""
    try:
        if has_requests:
            assert _requests is not None
            r = _requests.head(
                url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
                verify=verify_ssl,
            )
            return r.status_code == 200
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": USER_AGENT}
        )
        resp = urllib.request.urlopen(req, timeout=10, context=_ssl_context())
        return resp.status == 200
    except Exception:
        return False


def download_file(url: str, filepath: Path) -> bool:
    """Download a file to disk. Returns True on success."""
    try:
        if has_requests:
            assert _requests is not None
            r = _requests.get(
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
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=30, context=_ssl_context())
        with open(filepath, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    download error: {e}", file=sys.stderr)
        return False


def probe_url(url: str, delay: float) -> str | None:
    """Check a URL, then its x-suffix variant. Return 'ok', 'ok-x', or None."""
    if url_exists(url):
        return "ok"
    time.sleep(delay)
    url_x = url.rsplit(".pdf", 1)[0] + "x.pdf"
    if url_exists(url_x):
        return "ok-x"
    time.sleep(delay)
    return None
