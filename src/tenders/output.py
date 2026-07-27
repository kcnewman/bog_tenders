from __future__ import annotations

import csv
import json
from pathlib import Path

from .notice import FIELD_NAMES, HEADERS, AuctionRow


def write_csv(path: Path, rows: list[AuctionRow]) -> int:
    rows = sorted(rows, key=_sort_key)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for row in rows:
            w.writerow(getattr(row, name) for name in FIELD_NAMES)
    return len(rows)


def write_json(path: Path, rows: list[AuctionRow]) -> int:
    rows = sorted(rows, key=_sort_key)
    data = [{name: getattr(r, name) for name in FIELD_NAMES} for r in rows]
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return len(rows)


def _sort_key(row: AuctionRow) -> tuple[int, str]:
    if row.tender_no is not None:
        try:
            return (int(row.tender_no), row.isin)
        except (TypeError, ValueError):
            pass
    return (0, row.isin)
