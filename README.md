# tenders

CLI tool for downloading and parsing Bank of Ghana GOG T-Bill auction result PDFs
into structured Excel, CSV, or JSON output.

## Install

```bash
pipx install git+https://github.com/kcnewman/tender.git
```

Or with `uv`:

```bash
uv tool install git+https://github.com/kcnewman/tender.git
```

Or for development:

```bash
uv sync
```

## Usage

### Download

```bash
# single tender
tenders download --tender 1943

# full year
tenders download --year 2025

# year range
tenders download --year 2024-2026

# custom output directory, 8 concurrent workers
tenders download --year 2025 -o ./pdfs -w 8
```

Files are saved as `Auctresults-{N}.pdf` (default output: `auction reports`).
Already-downloaded files are skipped automatically.

### Parse

```bash
# Excel (auto-detected from extension)
tenders parse results.xlsx auction reports/

# CSV
tenders parse results.csv auction reports/ --format csv

# JSON
tenders parse results.json auction reports/

# force new file (overwrite existing)
tenders parse --new results.xlsx auction reports/
```

The `--format` flag is optional — it's inferred from the file extension.

## Output fields

| Column | Description |
|---|---|
| Notice No | BOG notice reference |
| Tender No | Auction tender number |
| Tender Date | Auction date |
| Issue Date | Security issue date |
| ISIN | Security identifier |
| Tenor | Term (91/182/364 Day Bill, 1 Year T/Note) |
| Bids Tendered (GH¢M) | Total bids received (millions) |
| Bids Accepted (GH¢M) | Total bids accepted (millions) |
| Bid Rate Range Low/High (%) | Range of accepted bid rates |
| Allotted Discount Low/High (%) | Discount rate range of allotted securities |
| Allotted Interest Low/High (%) | Interest rate range of allotted securities |
| Weighted Avg Discount/Interest (%) | Weighted average rates |
| Target (GH¢M) | BOG target amount |

## Logic

Tender dates are derived from a known reference (Tender 2000 = March 27, 2026)
with a 7-day interval per tender. The tool probes the expected PDF URL, scanning
adjacent months near month boundaries and an `x`-suffix variant as fallback.
If no direct PDF exists, the auction announcement page is scraped for a download
link.
