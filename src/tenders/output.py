from __future__ import annotations

import csv
import json
from pathlib import Path

from .notice import FIELD_NAMES, HEADERS, AuctionRow, row_sort_key


def _sorted_data(rows: list[AuctionRow]) -> list[dict[str, object]]:
    return [
        {n: getattr(r, n) for n in FIELD_NAMES} for r in sorted(rows, key=row_sort_key)
    ]


def write_csv(path: Path, rows: list[AuctionRow]) -> int:
    data = _sorted_data(rows)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        w.writeheader()
        w.writerows(data)
    return len(rows)


def write_json(path: Path, rows: list[AuctionRow]) -> int:
    with open(path, "w") as f:
        json.dump(_sorted_data(rows), f, indent=2, default=str)
    return len(rows)
