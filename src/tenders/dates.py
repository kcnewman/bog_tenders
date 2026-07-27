"""Tender number <-> date math.

Reference: Tender 2000 was held on March 27, 2026.
Tenders occur every 7 days.
"""

from __future__ import annotations

from datetime import date, timedelta

REFERENCE_TENDER = 2000
REFERENCE_DATE = date(2026, 3, 27)
DAYS_PER_TENDER = 7


def tender_date(tender_number: int) -> date:
    """Return the auction date for a given tender number."""
    delta = (tender_number - REFERENCE_TENDER) * DAYS_PER_TENDER
    return REFERENCE_DATE + timedelta(days=delta)


def tender_for_date(target: date) -> int:
    """Estimate the tender number closest to a given date."""
    delta = (target - REFERENCE_DATE).days
    return REFERENCE_TENDER + round(delta / DAYS_PER_TENDER)


def tender_range_for_year(year: int, end_date: date | None = None) -> list[int]:
    """Return the list of candidate tender numbers whose dates fall in `year`.

    If *end_date* is given, exclude tenders whose date is after it.
    """
    lo = tender_for_date(date(year, 1, 1)) - 2
    hi = tender_for_date(date(year, 12, 31)) + 2
    candidates = [n for n in range(lo, hi + 1) if tender_date(n).year == year]
    if end_date is not None:
        candidates = [n for n in candidates if tender_date(n) <= end_date]
    return candidates
