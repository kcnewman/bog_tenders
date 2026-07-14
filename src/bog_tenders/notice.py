"""Auction notice PDF parsing."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path

import pdfplumber

ROW_RE = re.compile(
    r"(GHGGOGI\d+)\s+(\d+\s*Day Bill)\s+"
    r"GH¢\s*([\d,]+\.\d+)\s+GH¢\s*([\d,]+\.\d+)\s+"
    r"([\d.]+)\s*[–-]\s*([\d.]+)\s+"
    r"([\d.]+)\s*[–-]\s*([\d.]+)\s+"
    r"([\d.]+)\s*[–-]\s*([\d.]+)\s+"
    r"([\d.]+)\s+([\d.]+)"
)
NOTICE_RE = re.compile(r"NOTICE TO BANKS AND PUBLIC NO\.\s*(\S+)")
TENDER_RE = re.compile(
    r"RESULTS OF TENDER\s*(\d+)\s*HELD ON\s*(\d+)\w*\s+(\w+)\.?\s+(\d{4})"
)
ISSUE_RE = re.compile(r"SECURITIES TO BE ISSUED ON\s*(\d+)\w*\s+(\w+)\.?\s+(\d{4})")
TARGET_RE = re.compile(
    r"TARGET FOR 91,\s*182 AND 364-DAY T/BILLS:\s*GH¢\s*([\d,]+\.\d+)\s*Million"
)

EXPECTED_TENORS = 3


class ParseError(Exception):
    """Raised when a PDF doesn't match the expected notice layout."""


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
    target_next_tender_ghs_m: float | None

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
    "Target Next Tender (GH¢M)",
]


def _to_float(s: str) -> float:
    return float(s.rstrip(".").replace(",", ""))


def parse_pdf(path: Path) -> list[AuctionRow]:
    try:
        with pdfplumber.open(path) as pdf:
            text = pdf.pages[0].extract_text() or ""
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
    target = _to_float(target_m.group(1)) if target_m else None

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
            allotted_discount_low=_to_float(m.group(7)),
            allotted_discount_high=_to_float(m.group(8)),
            allotted_interest_low=_to_float(m.group(9)),
            allotted_interest_high=_to_float(m.group(10)),
            weighted_avg_discount=_to_float(m.group(11)),
            weighted_avg_interest=_to_float(m.group(12)),
            target_next_tender_ghs_m=target,
        )
        for m in ROW_RE.finditer(text)
    ]

    if len(rows) != EXPECTED_TENORS:
        raise ParseError(f"expected {EXPECTED_TENORS} tenor rows, found {len(rows)}")
    return rows
