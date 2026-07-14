"""CLI orchestration for parsing PDFs into Excel."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from . import excel
from .notice import AuctionRow, ParseError, parse_pdf


def discover_pdfs(paths: Iterable[str], recursive: bool = False) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            matches = sorted(p.glob(pattern))
            if not matches:
                print(f"warning: {p}: no PDFs found", file=sys.stderr)
            found.update(matches)
        elif p.is_file():
            found.add(p)
        else:
            print(f"warning: {p}: path does not exist, skipping", file=sys.stderr)
    return sorted(found)


def collect_rows(pdf_paths: list[Path]) -> list[AuctionRow]:
    rows: list[AuctionRow] = []
    for path in pdf_paths:
        try:
            rows.extend(parse_pdf(path))
        except ParseError as exc:
            print(f"warning: {path.name}: skipped — {exc}", file=sys.stderr)
    return rows


def main(args: argparse.Namespace) -> None:
    pdf_paths = discover_pdfs(args.paths, recursive=args.recursive)
    if not pdf_paths:
        print("error: no PDF files found in the given paths", file=sys.stderr)
        raise SystemExit(1)

    rows = collect_rows(pdf_paths)

    if args.mode == "build":
        n = excel.build(args.tracker, rows)
        if not n:
            raise SystemExit(1)
    else:
        if not args.tracker.exists():
            print(f"{args.tracker} does not exist yet — building fresh")
            excel.build(args.tracker, rows)
        else:
            excel.append(args.tracker, rows)
