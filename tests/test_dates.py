from datetime import date

from tenders.dates import tender_date, tender_for_date


def test_tender_date_2000():
    assert tender_date(2000) == date(2026, 3, 27)


def test_tender_date_2001():
    assert tender_date(2001) == date(2026, 4, 3)


def test_tender_date_1999():
    assert tender_date(1999) == date(2026, 3, 20)


def test_tender_for_date():
    assert tender_for_date(date(2026, 3, 27)) == 2000
