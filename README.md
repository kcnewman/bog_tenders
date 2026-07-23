# bog-tenders

CLI tool for downloading and parsing Bank of Ghana GOG T-Bill auction result PDFs
into structured Excel reports.

## Install

```bash
pip install -e .
```

## Usage

### Download

```bash
# single tender
bog-tenders download --tender 1943

# full year
bog-tenders download --year 2025

# year range
bog-tenders download --year 2024-2026

# custom output directory, 8 concurrent workers
bog-tenders download --year 2025 -o ./pdfs -w 8
```

Files are saved as `Auctresults-{N}.pdf` (default output: `auction reports`).

### Parse

```bash
# create new Excel tracker
bog-tenders parse build results.xlsx path/to/pdfs

# append to existing tracker
bog-tenders parse append results.xlsx path/to/pdfs --recursive
```

## Logic

Tender dates are derived from a known reference (Tender 2000 = March 27, 2026)
with a 7-day interval per tender. The tool probes the expected PDF URL, scanning
adjacent months near month boundaries and an `x`-suffix variant as fallback.
If no direct PDF exists, the auction announcement page is scraped for a download
link. Already-downloaded files are skipped automatically.
