"""CLI and fetch orchestration."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import cast

from . import network
from .tenders import tender_date, tender_range_for_year
from .urls import month_variants, pdf_url


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
        result = network.probe_url(url, delay)
        if result:
            suffix = "x" if result == "ok-x" else ""
            fname = f"Auctresults-{tender_number}{suffix}.pdf"
            label = f"{md.month:02d}{suffix}"
            print(f"OK ({label})", end=" ", flush=True)
            dl_url = url if result == "ok" else url.rsplit(".pdf", 1)[0] + "x.pdf"
            if network.download_file(dl_url, output_dir / fname):
                print(f"-> {fname}")
                return True
            return False

    print("miss")
    return False


def fetch_year(
    year: int, output_dir: Path, delay: float, end_date: date | None = None
) -> int:
    """Fetch all tenders for a given year. Returns count found."""
    candidates = tender_range_for_year(year, end_date)
    label = f" (up to {end_date})" if end_date else ""
    print(f"\n{'=' * 50}")
    print(f"  GOG T-Bill results for {year}{label}")
    print(f"{'=' * 50}")
    print(f"  probing {len(candidates)} tenders ({candidates[0]}..{candidates[-1]})\n")

    found = 0
    for n in candidates:
        if fetch_tender(n, output_dir, delay):
            found += 1
        time.sleep(delay)

    missed = len(candidates) - found
    print(f"\n  {year}: {found} found, {missed} not found")
    return found


def _run_download(args: argparse.Namespace) -> None:
    year = cast("str | None", args.year)
    tender = cast("int | None", args.tender)
    output = cast("str", args.output)
    delay = cast("float", args.delay)
    no_verify_ssl = cast("bool", args.no_verify_ssl)

    if not year and not tender:
        print("error: specify --year or --tender", file=sys.stderr)
        raise SystemExit(1)

    if no_verify_ssl:
        network.verify_ssl = False

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)

    if tender is not None:
        d = tender_date(tender)
        print(f"Fetching tender {tender} ({d})...")
        fetch_tender(tender, out, delay)
    elif year is not None and "-" in year:
        a, b = year.split("-", 1)
        end = date.today()
        for y in range(int(a), int(b) + 1):
            fetch_year(y, out, delay, end_date=end if y == int(b) else None)
    elif year is not None:
        fetch_year(int(year), out, delay, end_date=date.today())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bog-tenders",
        description="Bank of Ghana GOG T-Bill auction results tool",
    )
    sub = parser.add_subparsers(dest="command")

    dl = sub.add_parser("download", help="Download PDFs from BOG website")
    dl.add_argument("--year", "-y", help="Year (2025) or range (2024-2026)")
    dl.add_argument("--tender", "-t", type=int, help="Fetch a specific tender number")
    dl.add_argument(
        "--output", "-o", default="downloads", help="Output dir (default: downloads)"
    )
    dl.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0.5,
        help="Seconds between requests (default: 0.5)",
    )
    dl.add_argument(
        "-k",
        "--no-verify-ssl",
        action="store_true",
        help="Skip SSL certificate verification",
    )

    pr = sub.add_parser("parse", help="Parse PDFs into Excel tracker")
    pr.add_argument(
        "mode",
        choices=["build", "append"],
        help="Create new or append to existing tracker",
    )
    pr.add_argument("tracker", type=Path, help="Output .xlsx file")
    pr.add_argument("paths", nargs="+", help="PDF files and/or directories")
    pr.add_argument(
        "--recursive",
        action="store_true",
        help="Search directories recursively",
    )
    pr.add_argument("-v", "--verbose", action="store_true", help="Debug output")

    if (
        len(sys.argv) > 1
        and sys.argv[1].startswith("-")
        and sys.argv[1] not in ("-h", "--help")
    ):
        sys.argv.insert(1, "download")

    args = parser.parse_args()

    if args.command == "download":
        _run_download(args)
    elif args.command == "parse":
        from .parse import main as parse_main

        parse_main(args)
    else:
        parser.print_help()
