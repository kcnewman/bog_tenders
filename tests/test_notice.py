from __future__ import annotations

from pathlib import Path

import pytest

from tenders.notice import _clean_text, _to_float, parse_pdf


def test_to_float_simple():
    assert _to_float("13.5011") == 13.5011


def test_to_float_with_commas():
    assert _to_float("2,361.36") == 2361.36


def test_to_float_trailing_dot():
    assert _to_float("100.") == 100.0


def test_to_float_multi_dot():
    assert _to_float("12.7000.13.1000") == 12700013.1


def test_clean_text_dot_range():
    result = _clean_text("12.7000.13.1000")
    assert "12.7000-13.1000" in result


def test_clean_text_dangling_fragment():
    result = _clean_text("24.4100- 24.4100-25.6434")
    assert "24.4100-25.6434" in result


def test_clean_text_collapse_dash_space():
    result = _clean_text("13.0000- 13.2800")
    assert "13.0000-13.2800" in result


PDF_DIR = Path("auction reports")


@pytest.mark.parametrize(
    "fname,expected_rows",
    [
        ("Auctresults-1701.pdf", 2),
        ("Auctresults-1794.pdf", 3),
        ("Auctresults-1865.pdf", 3),
            ("Auctresults-1575.pdf", 2),  # 1 Year T/Note row has no WA values
        ("Auctresults-1809.pdf", 2),
    ],
)
def test_parse_pdf_row_count(fname, expected_rows):
    pdf = PDF_DIR / fname
    if not pdf.exists():
        pytest.skip(f"{fname} not found")
    rows = parse_pdf(pdf)
    assert len(rows) == expected_rows


def test_parse_1701_wa_values():
    pdf = PDF_DIR / "Auctresults-1701.pdf"
    if not pdf.exists():
        pytest.skip("PDF not found")
    rows = parse_pdf(pdf)
    by_isin = {r.isin: r for r in rows}
    row = by_isin["GHGGOG060302"]
    assert row.weighted_avg_discount == 13.1608
    assert row.weighted_avg_interest == 14.0878


def test_parse_1794_wa_values():
    pdf = PDF_DIR / "Auctresults-1794.pdf"
    if not pdf.exists():
        pytest.skip("PDF not found")
    rows = parse_pdf(pdf)
    by_isin = {r.isin: r for r in rows}
    row = by_isin["GHGGOG066275"]
    assert row.weighted_avg_discount == 15.6883
    assert row.weighted_avg_interest == 16.3287


def test_parse_1865_wa_values():
    pdf = PDF_DIR / "Auctresults-1865.pdf"
    if not pdf.exists():
        pytest.skip("PDF not found")
    rows = parse_pdf(pdf)
    by_isin = {r.isin: r for r in rows}
    row = by_isin["GHGGOG071564"]
    assert row.weighted_avg_discount == 23.8039
    assert row.weighted_avg_interest == 31.2404
