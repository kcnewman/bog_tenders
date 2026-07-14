# bog-tenders

Fetch and parse Bank of Ghana GOG T-Bill auction result PDFs.

Download PDFs from the BOG website by computing tender dates from a reference
point (Tender 2000 = March 27, 2026, tenders every 7 days). Then parse them
into an Excel tracker.

## Install

```bash
pip install -e .

# options
pip install -e ".[fast,parse]"
```

Or run directly without installing:

```bash
python -m bog_tenders download --year 2025
```

## Usage

### Download PDFs

```bash
# all tenders for a year (stops at today's date)
bog-tenders download --year 2025

# range of years
bog-tenders download --year 2024-2026

# single tender
bog-tenders download --tender 2000

# custom output dir, skip SSL verification
bog-tenders download --year 2025 -o ./pdfs -k
```

### Parse PDFs into Excel

```bash
# create new tracker
bog-tenders parse build results.xlsx ./pdfs

# append new PDFs to existing tracker
bog-tenders parse append results.xlsx ./pdfs

# search directories recursively, show debug output
bog-tenders parse build results.xlsx ./pdfs --recursive -v
```

### Options

#### `download`

| Flag | Description |
|------|-------------|
| `-y`, `--year` | Year (`2025`) or range (`2024-2026`) |
| `-t`, `--tender` | Fetch a specific tender number |
| `-o`, `--output` | Output directory (default: `downloads`) |
| `-d`, `--delay` | Seconds between requests (default: `0.5`) |
| `-k`, `--no-verify-ssl` | Skip SSL certificate verification (on by default) |

#### `parse`

| Flag | Description |
|------|-------------|
| `mode` | `build` (new) or `append` (existing tracker) |
| `tracker` | Path to the `.xlsx` file |
| `paths` | PDF files and/or directories |
| `--recursive` | Search directories recursively |
| `-v`, `--verbose` | Debug output |

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

Already-downloaded files are skipped automatically. Parsed PDFs are
de-duplicated on (tender_no, ISIN) and sorted chronologically in the Excel
tracker.
