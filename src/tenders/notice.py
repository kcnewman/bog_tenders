from __future__ import annotations

import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import pdfplumber

_ALLOTTED = r"(?:(?:([\d.]+)\s*[–-]\s*([\d.]+))|([\d.]+(?![\d.])))"

ROW_RE = re.compile(
    r"(GHGGOGI?\d+)\s+"
    r"(\d+\s*(?:Year\s+)?T/Note|\d+\s+Day\s+(?:T/)?Bill)\s+"
    r"GH¢?\s*([\d,]+(?:\.\d+)+)\s+GH¢?\s*([\d,]+(?:\.\d+)+)\s+"
    r"([\d.]+)\s*[–-]\s*([\d.]+)\s+" + _ALLOTTED + r"\s+" + _ALLOTTED + r"\s*"
    r"(\d+\.\d+)(?:\s+(\d+\.\d+))?"
)
NOTICE_RE = re.compile(r"NOTICE TO BANKS AND PUBLIC NO\.?\s*(\S+)")
TENDER_RE = re.compile(
    r"RESULTS OF TENDER\s*(\d+)\s*HELD ON\s*(\d+)\w*\s*(\w+)[,.]?\s+(\d{4})"
)
ISSUE_RE = re.compile(r"SECURITIES TO BE ISSUED ON\s*(\d+)\w*\s*(\w+)[,.]?\s+(\d{4})")
TARGET_RE = re.compile(
    r"TARGET FOR 91"
    r"(?:,\s*182\s+AND\s+364-DAY| AND 182-DAY)"
    r"\s+T/BILLS:\s*GH¢?\s*([\d,]+(?:\.\d+)?)\s*Million"
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
    by_top: dict[int, list[tuple[float, str]]] = {}
    for c in chars:
        by_top.setdefault(round(c["top"]), []).append((c["x0"], c["text"]))
    for top in sorted(by_top):
        items = sorted(by_top[top], key=lambda x: x[0])
        line = "".join(text for _, text in items)
        if "TARGET FOR 91" in line:
            m = re.search(r"T/BILLS:.*?([\d,]+\.\d+)\s*Million", line)
            if m:
                return _to_float(m.group(1))
    return None


def _to_float(s: str) -> float:
    s = s.replace(",", "")
    if s.count(".") > 1:
        s = s[: s.rindex(".")].replace(".", "") + s[s.rindex(".") :]
    return float(s.rstrip("."))


def _clean_text(text: str) -> str:
    text = re.sub(r"(\d+\.\d{4})\.(\d+\.\d{4})", r"\1-\2", text)
    text = re.sub(r"(\d+\.\d{4})-\s+(?=\1(?:-|\s))", r"", text)
    text = re.sub(r"(?<=\d)-\s+(?=\d)", "", text)
    text = re.sub(
        r"(GH¢[\d,]+\.\d+\s+GH¢[\d,]+\.\d+\s+)(\d+\.\d{4})(?=\s+\d)",
        r"\1\2-\2",
        text,
    )
    return text


def _fix_wa_if_from_range(
    row: AuctionRow, m: re.Match[str], combined: str, line: str
) -> None:
    if m.group(14) is not None:
        return
    after = combined[m.end(13) : m.end(13) + 15]
    if not after.startswith(("-", "–")):
        return
    post_bid = line.split(m.group(6), 1)[-1]
    singles = re.findall(r"\d+\.\d{4}", post_bid)
    if len(singles) >= 2:
        row.weighted_avg_discount = _to_float(singles[-2])
        row.weighted_avg_interest = _to_float(singles[-1])
    else:
        row.weighted_avg_discount = 0.0


def parse_pdf(path: Path) -> list[AuctionRow]:
    try:
        with pdfplumber.open(path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text() or ""
            chars = page.chars
    except Exception as exc:
        raise ParseError(f"could not read PDF ({exc})") from exc
    text = _clean_text(text)

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

    def _build_row(m: re.Match[str]) -> AuctionRow:
        return AuctionRow(
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
            weighted_avg_interest=_to_float(m.group(14)) if m.group(14) else 0.0,
            target_ghs_m=target,
        )

    lines = text.split("\n")
    rows = []
    for i, line in enumerate(lines):
        if not line.startswith("GHGGOG"):
            continue
        m = ROW_RE.search(line)
        if m:
            rows.append(_build_row(m))
            continue
        for offset in range(1, min(4, len(lines) - i)):
            combined = line + " " + lines[i + offset]
            m = ROW_RE.search(combined)
            if m:
                row = _build_row(m)
                _fix_wa_if_from_range(row, m, combined, line)
                rows.append(row)
                break

    if len(rows) not in (2, 3):
        raise ParseError(f"expected 2 or 3 tenor rows, found {len(rows)}")
    return rows
