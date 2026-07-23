from __future__ import annotations

import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import pdfplumber

_ALLOTTED = r"(?:(?:([\d.]+)\s*[–-]\s*([\d.]+))|([\d.]+))"

ROW_RE = re.compile(
    r"(GHGGOGI?\d+)\s+(\d+\s*Day Bill)\s+"
    r"GH¢\s*([\d,]+(?:\.\d+)+)\s+GH¢\s*([\d,]+(?:\.\d+)+)\s+"
    r"([\d.]+)\s*[–-]\s*([\d.]+)\s+" + _ALLOTTED + r"\s+" + _ALLOTTED + r"\s+"
    r"([\d.]+)\s+([\d.]+)"
)
NOTICE_RE = re.compile(r"NOTICE TO BANKS AND PUBLIC NO\.\s*(\S+)")
TENDER_RE = re.compile(
    r"RESULTS OF TENDER\s*(\d+)\s*HELD ON\s*(\d+)\w*\s+(\w+)\.?\s+(\d{4})"
)
ISSUE_RE = re.compile(r"SECURITIES TO BE ISSUED ON\s*(\d+)\w*\s+(\w+)\.?\s+(\d{4})")
TARGET_RE = re.compile(
    r"TARGET FOR 91"
    r"(?:,\s*182\s+AND\s+364-DAY| AND 182-DAY)"
    r"\s+T/BILLS:\s*GH¢\s*([\d,]+(?:\.\d+)?)\s*Million"
)


class ParseError(Exception): ...


@dataclass
class AuctionRow:
    notice_no: str | None
    tender_no: str | None
    tender_date: str | None
    issue_date: str | None
    isin: str
    tenor: str
    bids_tendered_ghs_m: float
    bids_accepted_ghs_m: float
    bid_rate_range_low: float
    bid_rate_range_high: float
    allotted_discount_low: float
    allotted_discount_high: float
    allotted_interest_low: float
    allotted_interest_high: float
    weighted_avg_discount: float
    weighted_avg_interest: float
    target_ghs_m: float | None

    @property
    def key(self) -> tuple[str | None, str]:
        return (self.tender_no, self.isin)


FIELD_NAMES = [f.name for f in fields(AuctionRow)]
HEADERS = [
    "Notice No",
    "Tender No",
    "Tender Date",
    "Issue Date",
    "ISIN",
    "Tenor",
    "Bids Tendered (GH¢M)",
    "Bids Accepted (GH¢M)",
    "Bid Rate Range Low (%)",
    "Bid Rate Range High (%)",
    "Allotted Discount Low (%)",
    "Allotted Discount High (%)",
    "Allotted Interest Low (%)",
    "Allotted Interest High (%)",
    "Weighted Avg Discount (%)",
    "Weighted Avg Interest (%)",
    "Target (GH¢M)",
]


def _extract_target_amount(chars: list[dict[str, Any]]) -> float | None:
    lines: dict[float, list[tuple[float, str]]] = {}
    for c in chars:
        top = round(c["top"])
        lines.setdefault(top, []).append((c["x0"], c["text"]))
    line_strings: dict[float, str] = {}
    for top in lines:
        items = sorted(lines[top], key=lambda x: x[0])
        line_strings[top] = "".join(item[1] for item in items)
    target_tops = [top for top, text in line_strings.items() if "TARGET FOR 91" in text]
    if not target_tops:
        return None
    target_top = target_tops[0]
    nearby = [c for c in chars if abs(round(c["top"]) - target_top) <= 1]
    merged = sorted(nearby, key=lambda c: (c["x0"], c["top"]))
    text = "".join(str(c["text"]) for c in merged)
    m = re.search(r"T/BILLS:.*?([\d,]+\.\d+)\s*Million", text)
    return _to_float(m.group(1)) if m else None


def _to_float(s: str) -> float:
    s = s.rstrip(".").replace(",", "")
    parts = s.split(".")
    if len(parts) > 2:
        s = "".join(parts[:-1]) + "." + parts[-1]
    return float(s)


def parse_pdf(path: Path) -> list[AuctionRow]:
    try:
        with pdfplumber.open(path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text() or ""
            chars = page.chars
    except Exception as exc:
        raise ParseError(f"could not read PDF ({exc})") from exc

    notice_m = NOTICE_RE.search(text)
    tender_m = TENDER_RE.search(text)
    issue_m = ISSUE_RE.search(text)
    target_m = TARGET_RE.search(text)

    if not tender_m:
        print(f"warning: {path.name}: tender number/date not found", file=sys.stderr)

    notice_no = notice_m.group(1) if notice_m else None
    tender_no = tender_m.group(1) if tender_m else None
    tender_date = (
        f"{tender_m.group(2)} {tender_m.group(3)} {tender_m.group(4)}"
        if tender_m
        else None
    )
    issue_date = (
        f"{issue_m.group(1)} {issue_m.group(2)} {issue_m.group(3)}" if issue_m else None
    )
    if target_m:
        target = _to_float(target_m.group(1))
    else:
        target = _extract_target_amount(chars)

    def _range_or_single(
        m: re.Match[str], low_idx: int, high_idx: int, single_idx: int
    ) -> tuple[float, float]:
        if m.group(single_idx) is not None:
            v = _to_float(m.group(single_idx))
            return v, v
        return _to_float(m.group(low_idx)), _to_float(m.group(high_idx))

    rows = [
        AuctionRow(
            notice_no=notice_no,
            tender_no=tender_no,
            tender_date=tender_date,
            issue_date=issue_date,
            isin=m.group(1),
            tenor=m.group(2).replace("  ", " "),
            bids_tendered_ghs_m=_to_float(m.group(3)),
            bids_accepted_ghs_m=_to_float(m.group(4)),
            bid_rate_range_low=_to_float(m.group(5)),
            bid_rate_range_high=_to_float(m.group(6)),
            allotted_discount_low=_range_or_single(m, 7, 8, 9)[0],
            allotted_discount_high=_range_or_single(m, 7, 8, 9)[1],
            allotted_interest_low=_range_or_single(m, 10, 11, 12)[0],
            allotted_interest_high=_range_or_single(m, 10, 11, 12)[1],
            weighted_avg_discount=_to_float(m.group(13)),
            weighted_avg_interest=_to_float(m.group(14)),
            target_ghs_m=target,
        )
        for m in ROW_RE.finditer(text)
    ]

    if len(rows) not in (2, 3):
        raise ParseError(f"expected 2 or 3 tenor rows, found {len(rows)}")
    return rows
