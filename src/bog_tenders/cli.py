from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from . import network
from .tenders import tender_date, tender_range_for_year

console = Console()


def fetch_tender(tender_number: int, output_dir: Path) -> bool:
    d = tender_date(tender_number)
    filepath = output_dir / f"Auctresults-{tender_number}.pdf"
    if filepath.exists():
        return True
    hit = network.probe_urls(network.probe_urls_for_tender(tender_number, d))
    if hit and network.download_file(hit, filepath):
        return True
    html = network.fetch_page(network.auction_page_url(tender_number))
    if html:
        dl_url = network.extract_download_url(html)
        if dl_url and network.download_file(dl_url, filepath):
            return True
    return False


def fetch_year(year: int, output_dir: Path, workers: int, end_date: date | None = None,
               progress: Progress | None = None, task_id: TaskID | None = None) -> int:
    candidates = tender_range_for_year(year, end_date)
    if not candidates:
        return 0
    found = 0
    missed: list[int] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut_to_n = {ex.submit(fetch_tender, n, output_dir): n for n in candidates}
        for fut in as_completed(fut_to_n):
            n = fut_to_n[fut]
            if fut.result():
                found += 1
            else:
                missed.append(n)
            if progress is not None and task_id is not None:
                progress.update(task_id, advance=1)
    if missed:
        console.log(f"[yellow]not found:[/] {', '.join(str(n) for n in missed)}", _stack_offset=2)
    return found


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
        years = [int(y) for y in (year.split("-") if "-" in year else [year])]
        total_found = 0
        total_count = 0
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(), TaskProgressColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(), console=console,
        ) as progress:
            for y in years:
                candidates = tender_range_for_year(y, end if y == years[-1] else None)
                task = progress.add_task(f"  {y}", total=len(candidates))
                found = fetch_year(y, out, workers,
                                   end_date=end if y == years[-1] else None,
                                   progress=progress, task_id=task)
                total_found += found
                total_count += len(candidates)
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
    parser = argparse.ArgumentParser(prog="bog-tenders",
                                     description="Bank of Ghana GOG T-Bill auction results tool")
    sub = parser.add_subparsers(dest="command")
    dl = sub.add_parser("download", help="Download PDFs from BOG website")
    dl.add_argument("--year", "-y", help="Year (2025) or range (2024-2026)")
    dl.add_argument("--tender", "-t", type=int, help="Fetch a specific tender number")
    dl.add_argument("--output", "-o", default="auction reports", help="Output dir")
    dl.add_argument("--workers", "-w", type=int, default=6, help="Concurrent downloads (default: 6)")
    dl.add_argument("-k", "--no-verify-ssl", action="store_true", help="Skip SSL verification")
    pr = sub.add_parser("parse", help="Parse PDFs into Excel tracker")
    pr.add_argument("mode", choices=["build", "append"], help="Create new or append")
    pr.add_argument("tracker", type=Path, help="Output .xlsx file")
    pr.add_argument("paths", nargs="+", help="PDF files and/or directories")
    pr.add_argument("--recursive", action="store_true", help="Search directories recursively")
    pr.add_argument("-v", "--verbose", action="store_true", help="Debug output")
    if len(sys.argv) > 1 and sys.argv[1].startswith("-") and sys.argv[1] not in ("-h", "--help"):
        sys.argv.insert(1, "download")
    args = parser.parse_args()
    if args.command == "download":
        _run_download(args)
    elif args.command == "parse":
        from .parse import main as parse_main
        parse_main(args)
    else:
        parser.print_help()
