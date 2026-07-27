from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from . import network
from .dates import tender_date
from .download import fetch_tender, fetch_year

console = Console()


def _run_download(args: argparse.Namespace) -> None:
    year = cast("str | None", args.year)
    tender = cast("int | None", args.tender)
    output = cast("str", args.output)
    workers = cast("int", args.workers)
    no_verify_ssl = cast("bool", args.no_verify_ssl)
    if not year and not tender:
        console.print("[red]error:[/] specify --year or --tender")
        raise SystemExit(1)
    if no_verify_ssl:
        network.verify_ssl = False
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    if tender is not None:
        d = tender_date(tender)
        ok = fetch_tender(tender, out)
        label = Text("YES", style="green") if ok else Text("NO", style="red")
        console.print(f"  {tender}  ({d}) — {label}")
    else:
        end = date.today()
        assert year is not None
        if "-" in year:
            start, end_year = year.split("-", 1)
            years = list(range(int(start), int(end_year) + 1))
        else:
            years = [int(year)]
        total_found = 0
        total_count = 0
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for y in years:
                candidates_end = end if y == years[-1] else None
                task = progress.add_task(f"  {y}", total=0)
                found, total = fetch_year(
                    y,
                    out,
                    workers,
                    end_date=candidates_end,
                    progress=progress,
                    task_id=task,
                )
                total_found += found
                total_count += total
        table = Table.grid(padding=(0, 2))
        table.add_column()
        table.add_column(justify="right")
        table.add_column(style="dim")
        table.add_row(
            Text.assemble(("Total", "bold"), " tenders"),
            str(total_count),
            f"({total_found} found, {total_count - total_found} missed)",
        )
        console.print()
        console.print(table)


def main() -> None:
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
    dl.add_argument(
        "-k", "--no-verify-ssl", action="store_true", help="Skip SSL verification"
    )
    pr = sub.add_parser("parse", help="Parse PDFs into Excel tracker")
    pr.add_argument("tracker", type=Path, help="Output .xlsx file")
    pr.add_argument("paths", nargs="+", help="PDF files and/or directories")
    pr.add_argument(
        "--recursive", action="store_true", help="Search directories recursively"
    )
    pr.add_argument(
        "-n", "--new", action="store_true", help="Force build new tracker (ignore existing)"
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
        from .excel import main as parse_main

        parse_main(args)
    else:
        parser.print_help()
