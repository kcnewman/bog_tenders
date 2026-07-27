from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from rich.progress import Progress, TaskID

from . import console, network
from .dates import tender_date, tender_range_for_year


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


def fetch_year(
    year: int,
    output_dir: Path,
    workers: int,
    end_date: date | None = None,
    progress: Progress | None = None,
    task_id: TaskID | None = None,
) -> tuple[int, int]:
    candidates = tender_range_for_year(year, end_date)
    if not candidates:
        return 0, 0
    if progress is not None and task_id is not None:
        progress.update(task_id, total=len(candidates))
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
        console.log(
            f"[yellow]not found:[/] {', '.join(str(n) for n in missed)}",
            _stack_offset=2,
        )
    return found, len(candidates)
