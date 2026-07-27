from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import openpyxl
from rich.text import Text

from . import console, make_progress
from .notice import FIELD_NAMES, HEADERS, AuctionRow, ParseError, parse_pdf, row_sort_key


def discover_pdfs(paths: Iterable[str]) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            matches = sorted(p.glob("**/*.pdf"))
            if not matches:
                console.print(f"[yellow]warning:[/] {p}: no PDFs found")
            found.update(matches)
        elif p.is_file():
            found.add(p)
        else:
            console.print(f"[yellow]warning:[/] {p}: path does not exist, skipping")
    return sorted(found)


def collect_rows(
    pdf_paths: list[Path], progress: Any = None, task_id: Any = None
) -> list[AuctionRow]:
    rows: list[AuctionRow] = []
    for path in pdf_paths:
        try:
            rows.extend(parse_pdf(path))
        except ParseError as exc:
            console.print(f"[yellow]warning:[/] {path.name}: skipped — {exc}")
        if progress is not None and task_id is not None:
            progress.update(task_id, advance=1)
    return rows


def _flatten(rows: list[AuctionRow]) -> list[list[Any]]:
    return [[getattr(r, name) for name in FIELD_NAMES] for r in sorted(rows, key=row_sort_key)]


def _build(out_path: Path, rows: list[AuctionRow]) -> int:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Auction Results"
    ws.append(HEADERS)
    for data in _flatten(rows):
        ws.append(data)
    wb.save(out_path)
    n = len(rows)
    console.print(f"wrote [bold]{n}[/] rows to {out_path}")
    return n


def _append(out_path: Path, rows: list[AuctionRow]) -> int:
    wb = openpyxl.load_workbook(out_path)
    if "Auction Results" not in wb.sheetnames:
        console.print(f"[red]error:[/] '{out_path}' has no 'Auction Results' sheet")
        return 0
    ws = wb["Auction Results"]
    tender_col = FIELD_NAMES.index("tender_no") + 1
    isin_col = FIELD_NAMES.index("isin") + 1
    existing = {(ws.cell(row=r, column=tender_col).value, ws.cell(row=r, column=isin_col).value)
                for r in range(2, ws.max_row + 1)}
    new = [r for r in rows if r.key not in existing]
    skipped = len(rows) - len(new)
    for data in _flatten(new):
        ws.append(data)
    wb.save(out_path)
    console.print(f"added [bold]{len(new)}[/] rows to {out_path} [dim]({skipped} already present)[/]")
    return len(new)


def main(args: argparse.Namespace) -> None:
    pdfs = discover_pdfs(args.paths)
    if not pdfs:
        console.print("[red]error:[/] no PDF files found")
        raise SystemExit(1)
    with make_progress() as progress:
        task = progress.add_task("  Parsing PDFs", total=len(pdfs))
        rows = collect_rows(pdfs, progress=progress, task_id=task)
    if args.new or not args.tracker.exists():
        if not _build(args.tracker, rows):
            raise SystemExit(1)
    else:
        _append(args.tracker, rows)
