# IPO listing cohort, 2020–2026

This folder is a portable handoff for analysis in Claude. It contains one row
per **published, listed IPO record** with a listing date from 1 January 2020
through **28 September 2026**. The 2026 cohort is year to date. The export is
derived from the site's published V4 issue index and its identity-checked
performance snapshot; it does not fetch live data.

## Start here

- `ipo_cohort.csv` — full population, including issues without a verified
  listing-day close. Filter `cohort_include = 1` for a listing-close-return
  chart or summary. Keep the other rows when reporting coverage.
- `ipo_cohort.jsonl` — the same records with integer and Boolean-like fields
  preserved as JSON numbers; useful for code-based analysis.
- `ipo_cohort.xlsx` — the same cohort plus Coverage and Unmatched sheets for
  inspection. The CSV/JSONL files are the authoritative exports for scripts.
- `coverage_by_year_board.csv` — published records, verified closes, duplicate
  observations, usable cohort rows, and missing closes by listing year and
  Main/SME board.
- `unmatched_issues.csv` — records requiring a verified listing close. A
  missing price is not evidence that the IPO did not list.
- `manifest.json` — source and export checksums plus reconciled row counts.
- `METHODOLOGY.md` — selection, return calculation, source hierarchy and
  limitations.
- `DATA_DICTIONARY.md` — column definitions and units.
- `CLAUDE_HANDOFF.md` — a concise brief you can paste into Claude.

## Current coverage

The exported population has **1,544** listed IPO records. **1,439** have a
verified listing-day close; **20** of those are duplicate observations of an
IPO already represented by another issue ID. The analysis cohort therefore
has **1,419** rows. **105** records lack a verified close. The coverage file
breaks these counts down by year and board. The numbers are counts of records
in this site's published index, not proof that its universe includes every
Indian IPO.

## Rebuild inside this repository

```bash
.venv/bin/python analysis/ipo-2020-2026/build_handoff.py
```

The builder checks the issue-price and listing-date anchor of every matched
row against the performance snapshot. If the snapshot changes, review the new
`manifest.json`, coverage, and exclusions before using the refreshed export.
The Excel workbook is a convenience copy made from the exported rows.
