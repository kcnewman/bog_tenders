from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import cast

from rich.table import Table
from rich.text import Text

from . import console, make_progress
from .dates import tender_date
from .download import fetch_tender, fetch_year


def _parse_year_range(year: str) -> list[int]:
    if "-" in year:
        start, end_yr = year.split("-", 1)
        return list(range(int(start), int(end_yr) + 1))
    return [int(year)]


def _print_summary(
    years: list[int],
    total_found: int,
    total_count: int,
    missed_by_year: dict[int, list[int]],
) -> None:
    console.clear()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column()
    table.add_column(justify="right")
    table.add_column(style="dim")
    table.add_row(
        Text.assemble(("Total", "bold"), " tenders"),
        str(total_count),
        f"({total_found} found, {total_count - total_found} missed)",
    )
    if missed_by_year:
        table.add_section()
        for y in years:
            m = missed_by_year.get(y)
            if m:
                table.add_row(f"  {y}", "", ", ".join(str(n) for n in sorted(m)))
    console.print(table)


def _run_download(args: argparse.Namespace) -> None:
    year = cast("str | None", args.year)
    tender = cast("int | None", args.tender)
    workers = cast("int", args.workers)
    out = Path(cast("str", args.output))
    out.mkdir(parents=True, exist_ok=True)
    if tender is not None:
        d = tender_date(tender)
        ok = fetch_tender(tender, out)
        label = Text("YES", style="green") if ok else Text("NO", style="red")
        console.print(f"  {tender}  ({d}) — {label}")
        return
    if year is None:
        console.print("[red]error:[/] specify --year or --tender")
        raise SystemExit(1)
    end = date.today()
    years = _parse_year_range(year)
    total_found = 0
    total_count = 0
    missed_by_year: dict[int, list[int]] = {}
    with make_progress() as progress:
        for y in years:
            candidates_end = end if y == years[-1] else None
            task = progress.add_task(f"  {y}", total=0)
            found, total, missed = fetch_year(
                y, out, workers, end_date=candidates_end, progress=progress, task_id=task
            )
            total_found += found
            total_count += total
            if missed:
                missed_by_year[y] = missed
    _print_summary(years, total_found, total_count, missed_by_year)


def _infer_format(path: Path) -> str:
    suffix = path.suffix.lower()
    for fmt in (".xlsx", ".csv", ".json"):
        if suffix == fmt:
            return fmt.lstrip(".")
    return "xlsx"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tenders", description="Bank of Ghana GOG T-Bill auction results tool"
    )
    sub = parser.add_subparsers(dest="command")
    dl = sub.add_parser("download", help="Download PDFs from BOG website")
    dl.add_argument("--year", "-y", help="Year (2025) or range (2024-2026)")
    dl.add_argument("--tender", "-t", type=int, help="Fetch a specific tender number")
    dl.add_argument("--output", "-o", default="auction reports", help="Output dir")
    dl.add_argument(
        "--workers", "-w", type=int, default=6, help="Concurrent downloads (default: 6)"
    )
    pr = sub.add_parser("parse", help="Parse PDFs into structured output")
    pr.add_argument("tracker", type=Path, help="Output file (.xlsx, .csv, .json)")
    pr.add_argument("paths", nargs="+", help="PDF files and/or directories")
    pr.add_argument(
        "--format", choices=("xlsx", "csv", "json"), help="Output format (inferred from extension if omitted)"
    )
    pr.add_argument(
        "-n", "--new", action="store_true", help="Force build new tracker (ignore existing)"
    )
    pr.add_argument("-v", "--verbose", action="store_true", help="Debug output")
    return parser


def main() -> None:
    parser = _build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        return
    if sys.argv[1] not in ("download", "parse", "-h", "--help"):
        sys.argv.insert(1, "download")
    args = parser.parse_args()
    if args.command == "download":
        _run_download(args)
    elif args.command == "parse":
        format_ = args.format or _infer_format(args.tracker)
        if format_ == "xlsx":
            from .excel import main as parse_main

            parse_main(args)
        else:
            from . import output
            from .excel import collect_rows, discover_pdfs

            pdf_paths = discover_pdfs(args.paths)
            if not pdf_paths:
                console.print("[red]error:[/] no PDF files found")
                raise SystemExit(1)
            rows = collect_rows(pdf_paths)
            writer = output.write_csv if format_ == "csv" else output.write_json
            n = writer(args.tracker, rows)
            console.print(f"wrote [bold]{n}[/] rows to {args.tracker}")
