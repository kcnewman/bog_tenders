from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import cast

from rich.table import Table
from rich.text import Text

from . import __version__, console, make_progress
from .dates import tender_date
from .download import fetch_tender, fetch_year


class TendersCLI:
    EXT_MAP = {".xlsx": "xlsx", ".csv": "csv", ".json": "json"}

    def run(self) -> None:
        if len(sys.argv) == 1:
            self._build_parser().print_help()
            return
        if "--version" in sys.argv:
            print(f"tenders {__version__}")
            return
        if sys.argv[1] not in ("download", "parse", "-h", "--help"):
            sys.argv.insert(1, "download")
        args = self._build_parser().parse_args()
        (self._download if args.command == "download" else self._parse)(args)

    def _build_parser(self) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="tenders", description="BOG GOG T-Bill auction results tool"
        )
        p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
        s = p.add_subparsers(dest="command")
        dl = s.add_parser("download", help="Download PDFs from BOG website")
        dl.add_argument("--year", "-y", help="Year (2025) or range (2024-2026)")
        dl.add_argument("--tender", "-t", type=int, help="Specific tender number")
        dl.add_argument("--output", "-o", default="auction reports", help="Output dir")
        dl.add_argument(
            "--workers", "-w", type=int, default=6, help="Concurrent downloads"
        )
        pr = s.add_parser("parse", help="Parse PDFs into structured output")
        pr.add_argument("tracker", type=Path)
        pr.add_argument("paths", nargs="+")
        pr.add_argument(
            "--format", choices=("xlsx", "csv", "json"), help="Output format"
        )
        pr.add_argument("-n", "--new", action="store_true", help="Force new file")
        return p

    @staticmethod
    def _print_summary(
        years: list[int], found: int, total: int, missed: dict[int, list[int]]
    ) -> None:
        console.clear()
        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column()
        t.add_column(justify="right")
        t.add_column(style="dim")
        t.add_row(
            Text.assemble(("Total", "bold"), " tenders"),
            str(total),
            f"({found} found, {total - found} missed)",
        )
        if missed:
            t.add_section()
            for y in years:
                m = missed.get(y)
                if m:
                    t.add_row(f"  {y}", "", ", ".join(str(n) for n in sorted(m)))
        console.print(t)

    def _download(self, args: argparse.Namespace) -> None:
        out = Path(cast("str", args.output))
        out.mkdir(parents=True, exist_ok=True)
        workers: int = cast("int", args.workers)

        tn: int | None = cast("int | None", args.tender)
        if tn is not None:
            ok = fetch_tender(tn, out)
            label = Text("YES", style="green") if ok else Text("NO", style="red")
            console.print(f"  {tn}  ({tender_date(tn)}) — ", label)
            return

        yr: str | None = cast("str | None", args.year)
        if yr is None:
            console.print("[red]error:[/] specify --year or --tender")
            raise SystemExit(1)

        if "-" in yr:
            ss, ee = yr.split("-", 1)
            years = list(range(int(ss), int(ee) + 1))
        else:
            years = [int(yr)]
        end = date.today()
        found = total = 0
        missed: dict[int, list[int]] = {}
        with make_progress() as progress:
            for y in years:
                task = progress.add_task(f"  {y}", total=0)
                f, t, m = fetch_year(
                    y,
                    out,
                    workers,
                    end_date=end if y == years[-1] else None,
                    progress=progress,
                    task_id=task,
                )
                found += f
                total += t
                if m:
                    missed[y] = m
        self._print_summary(years, found, total, missed)

    def _parse(self, args: argparse.Namespace) -> None:
        fmt = args.format or self.EXT_MAP.get(args.tracker.suffix.lower(), "xlsx")
        if fmt == "xlsx":
            from .excel import main as xl_main

            xl_main(args)
            return

        from . import output
        from .excel import collect_rows, discover_pdfs

        pdfs = discover_pdfs(args.paths)
        if not pdfs:
            console.print("[red]error:[/] no PDF files found")
            raise SystemExit(1)
        rows = collect_rows(pdfs)
        writer = output.write_csv if fmt == "csv" else output.write_json
        n = writer(args.tracker, rows)
        console.print(f"wrote [bold]{n}[/] rows to {args.tracker}")


main = TendersCLI().run
