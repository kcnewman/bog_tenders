# bog-tenders

Fetch Bank of Ghana GOG T-Bill auction result PDFs.

Probes the BOG website for PDFs by computing tender dates from a reference point
(Tender 2000 = March 27, 2026, tenders every 7 days) and trying the expected
URL pattern plus adjacent-month fallbacks.

## Install

```bash
pip install -e .

# with requests (faster, optional)
pip install -e ".[fast]"
```

Or run directly without installing:

```bash
python -m bog_tenders --year 2025
```

## Usage

```bash
# all tenders for a year (stops at today's date)
bog-tenders --year 2025

# range of years
bog-tenders --year 2024-2026

# single tender
bog-tenders --tender 2000

# custom output dir, skip SSL verification
bog-tenders --year 2025 -o ./pdfs -k
```

### Options

| Flag | Description |
|------|-------------|
| `-y`, `--year` | Year (`2025`) or range (`2024-2026`) |
| `-t`, `--tender` | Fetch a specific tender number |
| `-o`, `--output` | Output directory (default: `downloads`) |
| `-d`, `--delay` | Seconds between requests (default: `0.5`) |
| `-k`, `--no-verify-ssl` | Skip SSL certificate verification (on by default) |

## How it works

The BOG stores GOG T-Bill results as PDFs at:

```
https://www.bog.gov.gh/wp-content/uploads/{YYYY}/{MM}/Auctresults-{N}.pdf
```

Given a known reference (Tender 2000 = March 27, 2026), the tool calculates
the approximate date for any tender number by stepping 7 days per tender. It
then probes the URL, trying the expected month and adjacent months to handle
date drift from holidays. The `x`-suffix variant (`Auctresults-{N}x.pdf`)
is also checked as a fallback.

Already-downloaded files are skipped automatically.
