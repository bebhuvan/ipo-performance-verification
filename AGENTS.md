# Runbook for an AI agent (or a person) verifying this analysis

Read `README.md` first. It explains the data, sources and methods. This file gives the order of work and what counts as a pass.

## Ground rules

- **Truth sources.** The truth sources are the official NSE and BSE files: daily bhavcopies, listing notices and corporate-action records. Every other source is a cross-check.
- **Where the numbers come from.** Every number in `report/ipo-performance.html` comes from `data/verified/report_data.json`, which is built only from files in `data/verified/`. If a check disagrees with a published number, report both values and the source file. Do not silently fix one side.
- **Credentials.** No credentials are needed for the checks. Kite (Zerodha) was used only as a cross-check and is optional.
- **Timing.** Exchange sites throttle heavy use. The download helper in `verify/_bhav.py` sleeps 0.4 s between requests and caches everything in `verify/.cache/`. A full run downloads about 3,400 files; allow 30 to 60 minutes the first time.

## Steps

```bash
pip install -r requirements.txt

# 1. Arithmetic and internal consistency (offline, seconds)
python verify/check_calculations.py
#    Pass: "0 failure(s)". It recomputes listing returns, every summary table, horizon and
#    listing-year tables, and all index windows from data/inputs/indices/.

# 2. Listing-day prices against the exchanges (network)
python verify/check_listing_closes.py --n 60      # sample across every board x year
python verify/check_listing_closes.py --all       # all 1,486 IPOs
#    Pass: every located IPO matches exactly and is a first-day row. A few "not located" rows
#    are expected where the dataset lacks an identifier; check those by hand (see README).

# 3. Size buckets (network for the share-count sample)
python verify/check_size.py --n 30
#    Pass: AMFI cutoffs rebuild from the raw AMFI spreadsheets, 450/450 buckets recompute,
#    sampled share counts match NSE's listing-day market-cap file.

# 4. Post-listing prices and corporate-action factors, spot check (network)
python verify/check_post_listing_prices.py --n 40 --horizon 1y
python verify/check_post_listing_prices.py --n 40 --horizon to_date --seed 5

# 5. Full independent rebuild of the post-listing returns (network, long)
python verify/reproduce_post_listing.py
#    Downloads every trading day's bhavcopy on both exchanges, follows each stock by ISIN,
#    re-tests every corporate-action factor against the raw price move, rebuilds dividends
#    from data/inputs/stocks_events/, and compares every IPO x horizon row with the published
#    file. It writes verify/post_listing_reproduced.csv and, if any rows differ,
#    verify/post_listing_differences.csv.
```

## Expected results at handoff (30 September 2026)

| Check | Result when handed off |
|---|---|
| `check_calculations.py` | 37 of 37 pass |
| `check_listing_closes.py --n 60` | 56 sampled, 56 exact |
| `check_size.py --n 20` | AMFI cutoffs rebuilt for 17 periods; 450 of 450 buckets; 20 of 20 share counts |
| `check_post_listing_prices.py` | 30 of 30 at 1 year; 30 of 30 to date |
| `reproduce_post_listing.py` | 1,486 IPOs followed; 229 of 229 factors confirmed; 7,899 of 7,899 rows identical |

## Beyond the scripts

These are the checks most likely to find something the scripts cannot.

1. **Universe completeness.**
   - Get NSE's and BSE's own lists of past IPOs (Main Board and SME) for 2020–2026, and SEBI's annual counts.
   - Reconcile them year by year with `data/verified/ipo_cohort_verified.csv` plus `exclusions.csv`.
   - Expected differences are REITs, InvITs, follow-on offers and the 12 exclusions. Anything else is a finding.
2. **Hard cases** (listed in README, "How to verify independently"). Check each in the raw bhavcopy by hand.
3. **Trafiksol ITS** is excluded as a non-listing. Find the BSE notice.
4. **The SME opening cap** seen from 2025 (no SME IPO opened above +90%). Find the exchange circular and its effective date.
5. **Stale SME prices.** Recompute the SME headline numbers treating the 38 stale or stopped SME stocks as −100%, and report the sensitivity.
6. **Issue size.** The dataset does not use issue size (money raised), because the source records are inconsistent. A verified issue-size column, taken from exchange issue documents, would allow a "money raised" and "money left on the table" section.

## Changing the analysis

- `scripts/pipeline/` holds the original build scripts. They use absolute paths from the original machine and a Kite token, so treat them as a specification.
- `verify/reproduce_post_listing.py` is the portable version of the post-listing step. To change the method (horizons, benchmark, treatment of stale stocks), edit it and compare the output with `data/verified/post_listing_returns.csv`.
- The report page is `report/ipo_report.template.html`. Replace the `__DATA__` placeholder with the contents of `report_data.json` to rebuild it. It loads d3 7.9.0 from cdnjs with a pinned integrity hash.
