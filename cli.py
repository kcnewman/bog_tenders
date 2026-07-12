"""CLI and fetch orchestration."""

from __future__ import annotations

import argparse
import time
import warnings
from pathlib import Path
from typing import cast

from . import http
from .tenders import tender_date, tender_range_for_year
from .urls import pdf_url, month_variants


def fetch_tender(tender_number: int, output_dir: Path, delay: float) -> bool:
    """Probe for a single tender PDF and download it. Returns True if found."""
    d = tender_date(tender_number)
    filename = f"Auctresults-{tender_number}.pdf"
    filepath = output_dir / filename

    if filepath.exists():
        print(f"  {tender_number:>5}  {d}  [exists]")
        return True

    print(f"  {tender_number:>5}  {d}  probing...", end=" ", flush=True)

    for md in month_variants(d):
        url = pdf_url(tender_number, md)
        result = http.probe_url(url, delay)
        if result:
            suffix = "x" if result == "ok-x" else ""
            fname = f"Auctresults-{tender_number}{suffix}.pdf"
            label = f"{md.month:02d}{suffix}"
            print(f"OK ({label})", end=" ", flush=True)
            dl_url = url if result == "ok" else url.rsplit(".pdf", 1)[0] + "x.pdf"
            if http.download_file(dl_url, output_dir / fname):
                print(f"-> {fname}")
                return True
            return False

    print("miss")
    return False


def fetch_year(year: int, output_dir: Path, delay: float) -> int:
    """Fetch all tenders for a given year. Returns count found."""
    candidates = tender_range_for_year(year)
    print(f"\n{'='*50}")
    print(f"  GOG T-Bill results for {year}")
    print(f"{'='*50}")
    print(f"  probing {len(candidates)} tenders ({candidates[0]}..{candidates[-1]})\n")

    found = 0
    for n in candidates:
        if fetch_tender(n, output_dir, delay):
            found += 1
        time.sleep(delay)

    missed = len(candidates) - found
    print(f"\n  {year}: {found} found, {missed} not found")
    return found


def main() -> None:
    p = argparse.ArgumentParser(
        prog="bog-tenders",
        description="Fetch Bank of Ghana GOG T-Bill auction result PDFs",
    )
    p.add_argument("--year", "-y", help="Year (2025) or range (2024-2026)")
    p.add_argument("--tender", "-t", type=int, help="Fetch a specific tender number")
    p.add_argument("--output", "-o", default="downloads", help="Output dir (default: downloads)")
    p.add_argument("--delay", "-d", type=float, default=0.5, help="Seconds between requests (default: 0.5)")
    p.add_argument("-k", "--no-verify-ssl", action="store_true", help="Skip SSL certificate verification")
    args = p.parse_args()

    year = cast("str | None", args.year)
    tender = cast("int | None", args.tender)
    output = cast("str", args.output)
    delay = cast("float", args.delay)
    no_verify_ssl = cast("bool", args.no_verify_ssl)

    if not year and not tender:
        p.error("specify --year or --tender")

    if no_verify_ssl:
        http.verify_ssl = False
        if not http.has_requests:
            warnings.warn("SSL verification disabled")

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)

    if tender is not None:
        d = tender_date(tender)
        print(f"Fetching tender {tender} ({d})...")
        fetch_tender(tender, out, delay)
    elif year is not None and "-" in year:
        a, b = year.split("-", 1)
        for y in range(int(a), int(b) + 1):
            fetch_year(y, out, delay)
    elif year is not None:
        fetch_year(int(year), out, delay)
