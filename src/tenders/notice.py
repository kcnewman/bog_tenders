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
    r"RESULTS OF TENDER\s*(\d+)\s*HELD ON\s*(\d+)(?:ST|ND|RD|TH)?\s*(\w+)[,.]?\s+(\d{4})",
    re.IGNORECASE,
)
ISSUE_RE = re.compile(
    r"SECURITIES TO BE ISSUED ON\s*(\d+)(?:ST|ND|RD|TH)?\s*(\w+)[,.]?\s+(\d{4})",
    re.IGNORECASE,
)
TARGET_RE = re.compile(
    r"TARGET FOR .*?GH¢\s*([\d,.\s]+)\s*Million"
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


def row_sort_key(row: AuctionRow) -> tuple[int, str]:
    if row.tender_no is not None:
        try:
            return (int(row.tender_no), row.isin)
        except (TypeError, ValueError):
            pass
    return (0, row.isin)


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


def _to_float(s: str) -> float:
    s = re.sub(r"[,\s]", "", s)
    if s.count(".") > 1:
        s = s[: s.rindex(".")].replace(".", "") + s[s.rindex(".") :]
    return float(s.rstrip("."))


def _clean_text(text: str) -> str:
    text = re.sub(r"(\d+\.\d{4})\.(\d+\.\d{4})", r"\1-\2", text)
    text = re.sub(r"(\d+\.\d{4})-\s+(?=\1(?:-|\s))", r"", text)
    text = re.sub(r"(?<=\d)-\s+(?=\d)", "-", text)
    text = re.sub(r"(GH¢[\d,]+\.\d+\s+GH¢[\d,]+\.\d+\s+)(\d+\.\d{4})(?=\s+\d)", r"\1\2-\2", text)
    text = re.sub(r"T\s*/\s*B\s*I\s*L\s*L", "T/BILL", text)
    text = re.sub(r"G\s*H\s*¢", "GH¢", text)
    text = re.sub(r"T\s*A\s*R\s*G\s*E\s*T", "TARGET", text)
    text = re.sub(r"D\s+A\s+Y", "DAY", text)
    text = re.sub(r"M\s*i\s*l\s*l\s*i\s*o\s*n", "Million", text)
    text = re.sub(r"A\s+N\s+D", "AND", text)
    return text


def _extract_target(chars: list[dict[str, Any]]) -> float | None:
    by_top: dict[int, list[tuple[float, str]]] = {}
    for c in chars:
        by_top.setdefault(round(c["top"]), []).append((c["x0"], c["text"]))
    sorted_tops = sorted(by_top)
    for i, top in enumerate(sorted_tops):
        line = "".join(t for _, t in sorted(by_top[top], key=lambda x: x[0]))
        if "TARGET" not in line or "T/BILL" not in line:
            continue
        m = re.search(r"GH¢\s*([\d,]+(?:\.\d+)?)", line)
        if m:
            return _to_float(m.group(1))
        for offset in (-1, 1):
            j = i + offset
            if 0 <= j < len(sorted_tops):
                adj = "".join(t for _, t in sorted(by_top[sorted_tops[j]], key=lambda x: x[0]))
                m = re.search(r"GH¢\s*([\d,]+(?:\.\d+)?)", adj)
                if m:
                    return _to_float(m.group(1))
    return None


def _range_or_single(
    m: re.Match[str], lo: int, hi: int, si: int
) -> tuple[float, float]:
    if m.group(si) is not None:
        v = _to_float(m.group(si))
        return v, v
    return _to_float(m.group(lo)), _to_float(m.group(hi))


def _fix_wa(row: AuctionRow, m: re.Match[str], combined: str, line: str) -> None:
    if m.group(14) is not None:
        return
    if not combined[m.end(13) : m.end(13) + 15].startswith(("-", "–")):
        return
    singles = re.findall(r"\d+\.\d{4}", line.split(m.group(6), 1)[-1])
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

    n_m, t_m, i_m, g_m = (
        r.search(text) for r in (NOTICE_RE, TENDER_RE, ISSUE_RE, TARGET_RE)
    )
    if not t_m:
        print(f"warning: {path.name}: tender number/date not found", file=sys.stderr)

    ctx = _ParseCtx(
        notice_no=n_m.group(1) if n_m else None,
        tender_no=t_m.group(1) if t_m else None,
        tender_date=f"{t_m.group(2)} {t_m.group(3)} {t_m.group(4)}" if t_m else None,
        issue_date=f"{i_m.group(1)} {i_m.group(2)} {i_m.group(3)}" if i_m else None,
        target=_to_float(g_m.group(1)) if g_m else _extract_target(chars),
    )

    lines = text.split("\n")
    rows: list[AuctionRow] = []
    for i, line in enumerate(lines):
        if not line.startswith("GHGGOG"):
            continue
        m = ROW_RE.search(line)
        if m:
            rows.append(ctx.build_row(m))
            continue
        for offset in range(1, min(4, len(lines) - i)):
            combined = line + " " + lines[i + offset]
            m = ROW_RE.search(combined)
            if not m:
                continue
            row = ctx.build_row(m)
            _fix_wa(row, m, combined, line)
            rows.append(row)
            break

    if len(rows) not in (2, 3):
        raise ParseError(f"expected 2 or 3 tenor rows, found {len(rows)}")
    return rows


@dataclass
class _ParseCtx:
    notice_no: str | None
    tender_no: str | None
    tender_date: str | None
    issue_date: str | None
    target: float | None

    def build_row(self, m: re.Match[str]) -> AuctionRow:
        g = m.group
        dl, dh = _range_or_single(m, 7, 8, 9)
        il, ih = _range_or_single(m, 10, 11, 12)
        return AuctionRow(
            self.notice_no,
            self.tender_no,
            self.tender_date,
            self.issue_date,
            g(1),
            g(2).replace("  ", " "),
            _to_float(g(3)),
            _to_float(g(4)),
            _to_float(g(5)),
            _to_float(g(6)),
            dl,
            dh,
            il,
            ih,
            _to_float(g(13)),
            _to_float(g(14)) if g(14) else 0.0,
            self.target,
        )
