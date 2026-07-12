"""URL construction for BOG PDF files."""

from __future__ import annotations

from datetime import date

BASE_URL = "https://www.bog.gov.gh/wp-content/uploads"


def pdf_url(tender_number: int, d: date, suffix: str = "") -> str:
    """Build a PDF URL for a tender number and month."""
    return f"{BASE_URL}/{d.year:04d}/{d.month:02d}/Auctresults-{tender_number}{suffix}.pdf"


def month_variants(d: date) -> list[date]:
    """Return candidate month-dates to probe: expected month, then adjacents
    only when the date is near a month boundary."""
    y, m = d.year, d.month
    variants: list[date] = []
    for dm in (0, -1, 1):
        nm = m + dm
        if nm < 1 or nm > 12:
            continue
        if dm == -1 and d.day > 3:
            continue
        if dm == 1 and d.day < 29:
            continue
        variants.append(date(y, nm, 1))
    return variants
