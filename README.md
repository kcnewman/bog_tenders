# bog-tenders

Fetch and parse Bank of Ghana GOG T-Bill auction result PDFs into an Excel tracker.

## Install

```bash
pip install -e .
```

Or run directly:

```bash
python -m bog_tenders download --year 2025
```

## Usage

### Download

```bash
# single tender
bog-tenders download --tender 1943

# full year (stops at today)
bog-tenders download --year 2025

# year range
bog-tenders download --year 2024-2026

# custom output, 8 concurrent workers
bog-tenders download --year 2025 -o ./pdfs -w 8
```

Results are saved as `Auctresults-{N}.pdf` in the output directory (default: `auction reports`).

### Parse

```bash
# create new tracker
bog-tenders parse build results.xlsx ./pdfs

# append to existing tracker
bog-tenders parse append results.xlsx ./pdfs --recursive
```

## How it works

Tender dates start from a known reference (Tender 2000 = March 27, 2026) and step 7 days per tender. The tool probes the expected PDF URL, tries adjacent months near month boundaries, and checks the `x`-suffix variant as a fallback. If no direct PDF is found, the auction results page is scraped for a download link.
