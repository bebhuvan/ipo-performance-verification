# Methodology and limits

## Selection

The population starts from `data/ipo_watch_v4/issues/index.json`. It includes
records whose published issue type is `IPO`, status is `Listed`, and listing
date is between **2020-01-01** and the published performance snapshot's
`as_of` date, **2026-09-28**, inclusive. The site bundle is dated
2026-09-29; the earlier performance cutoff controls this export so no issue
is included after the price snapshot's observation date.

Each row is joined by the issue ID to
`data/ipo_watch_v4/performance-snapshot.json`. That snapshot contains
identity-checked listing-day observations from the official NSE PR archive,
official BSE bhavcopy recovery, and guarded BSE IPO-performance records. Its
source label is carried in `listing_price_source`. A match must have the same
listing date and final issue price as the public issue index.

## Calculation

The only prepared return is the **unadjusted listing-day close return**:

`(listing_close_paise / issue_price_paise - 1) × 10,000`, rounded to the
nearest whole basis point, half up. `listing_close_return_pct` divides those
basis points by 100. Issue and listing prices are in integer paise; the INR
columns are display conversions. No return is assigned when a verified close
is absent. Opening prices are included when independently available, but
missing opens must not be filled from the closing price.

The snapshot retains some observations for two issue IDs describing the same
first-day economics. `duplicate_of_issue_id` identifies the secondary record;
`cohort_include = 0` excludes it from counts of IPOs, while retaining its
source-backed price for inspection. Use `cohort_include = 1` for return
statistics. Use **all** rows to report data coverage.

## Interpretation

- 2026 is year to date through 28 September. Do not compare its raw IPO count
  with a completed calendar year.
- Coverage varies by year and board. Missing 2020–2021 SME closes and 2026
  SME closes may bias any matched-only comparison. Show
  `coverage_by_year_board.csv` beside year/board results.
- NSE and BSE listing closes may differ. Retain `listing_price_source` and
  label mixed-exchange results; a single-exchange sensitivity analysis is
  preferable for claims about exchange-specific listing returns.
- The issue index is a present-day collection, not an independently certified
  point-in-time universe. Delistings, historical omissions, renames and
  relistings can affect completeness. Reconcile with exchange issue lists
  before claiming results for **all** Indian IPOs or running a backtest.
- Current-price change and long-run investment return are deliberately absent.
  Corporate actions, dividends and delistings have not been reconciled.
- The export contains no sector, subscription or DRHP-derived fields; do not
  infer those categories from names.

## Source locations

- Published issue index: `data/ipo_watch_v4/issues/index.json`
- Verified listing prices: `data/ipo_watch_v4/performance-snapshot.json`
- Bundle date and quality totals: `data/ipo_watch_v4/manifest.json`
- Historical price pipeline: `docs/NSE_PR_PERFORMANCE.md`
- Source precedence and parsing notes: `docs/data/SOURCES.md`

The `manifest.json` in this folder records SHA-256 hashes of the three input
files and every text export, so the handoff can be checked after copying.
