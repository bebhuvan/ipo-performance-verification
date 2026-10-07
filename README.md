# Indian IPO performance, 2020–2026: data and verification

This repository holds the dataset and method behind a report on how Indian IPOs performed on listing day and afterwards. The listing dataset covers 1,515 IPOs listed on NSE and BSE between 1 January 2020 and 6 October 2026: 463 Main Board and 1,052 SME. Post-listing returns, benchmark comparisons and size classifications retain the original 1,486-IPO cohort and 28 September 2026 price cutoff. It is meant for independent verification: every number in the report can be traced to a file here, and every file here traces back to an official exchange record or a named source.

Original verification: 30 September 2026. Listing-only update: 7 October 2026. The repository is self-contained. Every input that is not an official exchange download is included as a snapshot, and the scripts in `verify/` re-download the exchange files themselves. If you are an AI agent asked to check or rerun this analysis, follow `AGENTS.md`.

## Latest listing update: 7 October 2026

Added **29 IPOs listed from 29 September to 6 October**: 13 Main Board and 16 SME. The 2026 YTD counts are now **94 Main Board and 167 SME**. Today's session was still open when the update ran; 7 October listing closes are not included.

- **Evidence:** fresh official NSE `public-past-issues` and BSE `MoreCompanyN` IPO-performance responses, plus all ten listing-day NSE/BSE bhavcopies, frozen in `data/inputs/updates/2026-10-07/`. `sources.json` gives download URLs; `additions.json` records ISINs, both exchange rows and issue-price sources. No third-party listing prices were used for these additions.
- **Identity and prices:** NSE candidates require one symbol/series match and previous close equal to the feed's explicit final issue price. BSE candidates require one scrip-code match, first-day previous close zero, and close equal to the BSE performance feed. Dual listings are joined by exact ISIN and date; their final issue prices must agree. NSE close takes precedence. BSE-only final issue prices are supported by the official BSE performance feed, without a second prospectus check.
- **Excluded new securities:** bhavcopy first-day flags alone are insufficient to identify IPOs. New rows without an official equity IPO-feed record, debt series and ETFs do not enter the additions. The GSPLTRANS first-day row is not counted. This update does not certify universe completeness.
- **Source discrepancy:** Runwal's NSE displayed price range ends at ₹302, while its explicit final issue price, NSE first-day previous close and BSE issue-price field all give ₹305. Both source fields are preserved; ₹305 is used in the calculation.
- **Calculated:** listing close / final issue price − 1, half-up rounding to whole basis points. Counts, annual medians, shares above issue, opening comparisons and listing distributions were rebuilt for all 1,515 rows. Across all years the listing-close median is 12.0% for Main Board and 9.8% for SME.
- **Separate coverage:** the 29 additions have no post-listing returns, market-adjusted listing returns or size classification yet. Those sections still cover the original 1,486 IPOs through 28 September. Report charts, table notes and `report_data.json` expose the different cutoffs and denominators; blanks are not zeros. `as_of` remains the post-listing cutoff; `listing_as_of` is 6 October. No new Kite check was performed.

Reproduce the listing-only update from the frozen inputs (idempotent), then rebuild the report:

```bash
python3 scripts/update_listings.py --snapshot data/inputs/updates/2026-10-07
python3 scripts/pipeline/build_report_data.py
python3 verify/check_update.py
python3 verify/check_calculations.py
python3 verify/check_listing_closes.py --all --since 2026-09-28
```

`data/verified/update_manifest.json` records totals, section cutoffs and SHA-256 hashes. The original export's manifest and historical results below remain frozen evidence of the initial build.

## Contents

1. [What the report says](#what-the-report-says)
2. [Repository layout](#repository-layout)
3. [How the dataset was built](#how-the-dataset-was-built)
4. [Data sources](#data-sources)
5. [Methods](#methods)
6. [What we found wrong in the starting data](#what-we-found-wrong-in-the-starting-data)
7. [How well the sources agree](#how-well-the-sources-agree)
8. [Limitations and open items](#limitations-and-open-items)
9. [How to verify independently](#how-to-verify-independently)
10. [File dictionary](#file-dictionary)

## What the report says

The report is `report/ipo-performance.html`. Open it in a browser; it loads one charting library from cdnjs. The HTML report is included in this public repository.

- **Listing day.** The median Main Board IPO closed 12.0% above its issue price, and 72.6% closed above it. The median SME IPO closed 9.8% above, and 74.6% above it. The market barely moved between offer close and listing (median Nifty 500 move 0.1%), so the gain belongs to the IPO.
- **After listing.** For the 230 Main Board IPOs listed at least two years, the median return from the listing-day close, with dividends reinvested, was +1.5% at two years. The Nifty 500 TRI returned a median 29.6% over the same windows.
- **Beating the market.** From the listing-day close to 28 September 2026, 39.5% of Main Board IPOs and 38.5% of SME IPOs with at least a year of history beat the Nifty 500.
- **Listing year matters most.** SME IPOs from 2020 and 2021 beat the index (57% and 62%). Those from 2024 have lost a median 20.6% a year since listing, and 57% trade below issue.
- **SME opening cap.** Since January 2025, no SME IPO opened more than 90% above issue, and 33 opened at exactly +90%. Before 2025, 60 opened higher. The 2025–26 SME listing gains are therefore not like-for-like with 2024's.

## Repository layout

```
data/
  verified/                  the verified dataset (what the report is built from)
    ipo_cohort_verified.csv          one row per IPO: listing prices, sources, cross-checks
    exclusions.csv                   12 records removed from the starting data, with reasons
    size_and_benchmark.csv           market cap at issue, size bucket, listing-day index move
    post_listing_returns.csv         one row per IPO x horizon (1m..3y, to_date)
    corporate_action_events_applied.csv  every split/bonus/rights factor applied, with evidence
    corporate_actions_check.csv      NSE corporate-action records fetched for cross-checking
    post_issue_shares_exact.csv      27 share counts from listing notices / prospectus
    amfi_cutoffs.csv                 AMFI market-cap rank cutoffs (100/250/500/750), 2018-2026
    verification_detail.csv          raw per-IPO matching results (bhavcopy + Kite), before cleaning
    report_data.json                 every number the report page shows
    VERIFICATION_LOG.md              the working log written during verification
  summaries/                 year x board tables, horizon tables, listing-year tables, size table
  inputs/
    codex_export/            the starting dataset (built by an earlier Codex run from the site's pipeline)
    cross_check_sources/     two third-party spreadsheets used as cross-checks; the split/bonus calendar zip
    indices/                 daily Nifty 500 price and TRI, Nifty 100 / Midcap 150 / Smallcap 250 / SME Emerge, BSE SME IPO
    amfi/                    the 18 AMFI half-yearly market-cap spreadsheets (SOURCE_URLS.txt lists where each came from)
    stocks_events/           yearly corporate-action snapshots 2020-2026 from stocks.events (dividends, splits, bonuses, rights)
    nse_symbolchange.csv     NSE's symbol-change file, used to follow renamed stocks
report/                      the report page and its template
verify/                      independent check and reproduction scripts (run these; see AGENTS.md)
scripts/pipeline/            the scripts that built the dataset (reference; paths are from the original machine)
```

## How the dataset was built

1. **Starting point.** A Codex-built export of 1,544 IPO records (`data/inputs/codex_export/`). Its checksums, counts and return arithmetic all reproduced against its own `manifest.json`.
2. **Cross-checks against two spreadsheets.** Source B, the "WIP" workbook, agreed closely with the export. Source C disagreed so often that it was set aside as unreliable (details below).
3. **Independent verification of every listing price.** For each IPO we downloaded the official NSE and BSE bhavcopies for its listing date and located the security by ISIN, symbol or scrip code, or as a first-day row. A first-day row on NSE has a previous close equal to the issue price; on BSE, a previous close of zero. We then compared the close.
4. **Cleaning.**
   - Removed 12 records: 11 duplicates of IPOs already present, mostly renames, and one IPO with no first-day trade.
   - Filled 76 listing closes the export lacked.
   - Corrected 2 board labels and 1 issue price.
   - Applied a fixed exchange rule (below).
5. **Third source.** Kite Connect historical candles were checked against the result.
6. **Benchmark and size.**
   - Nifty 500 moves came from the data bank's Nifty Indices series.
   - Company size used AMFI's half-yearly rank lists. Share counts came from NSE's daily market-cap files, from exchange listing notices for boundary cases, and otherwise from share counts traced back through corporate actions.
7. **Post-listing returns.**
   - Daily raw closes came from the official bhavcopies of both exchanges for every trading day from 2020 to 28 September 2026.
   - Corporate actions were adjusted using official exchange records (via stocks.events) and Kite, each event confirmed by the actual price move on its ex-date.
   - Dividends were reinvested for Main Board total returns.
8. **Report.** Every figure in the page comes from `report_data.json`, which `scripts/pipeline/build_report_data.py` generates from the verified files only.

## Data sources

| Source | Used for | Where | Notes |
|---|---|---|---|
| NSE CM bhavcopy | Listing-day and daily closes, previous close (issue-price check), ISIN | `nsearchives.nseindia.com/content/historical/EQUITIES/…/cmDDMONYYYYbhav.csv.zip` (to 5 Jul 2024); `…/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` (from 8 Jul 2024) | Public, no login. Covers EQ, BE and SME (SM/ST) series. |
| BSE equity bhavcopy | Same, for BSE | `www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_DDMMYY.zip` (old); `…/BhavCopy_BSE_CM_0_0_0_YYYYMMDD_F_0000.CSV` (new) | Public. SME groups M/MT/TS. |
| NSE daily PR bundle (MCAP file) | Shares outstanding on listing day, from February 2024 | `nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PRddmmyy.zip`; the MCAPDDMMYYYY.csv member | MCAP exists in the bundle only from 1 Feb 2024. "Issue Size" column = shares outstanding. |
| NSE symbol-change file | Following renamed NSE symbols | `nsearchives.nseindia.com/content/equities/symbolchange.csv` | Misses some renames (Burger King → RBA, DU Digital → DUGLOBAL); handled by ISIN continuation. |
| stocks.events | Splits, bonuses, consolidations, rights terms, dividend amounts (NSE and BSE) | `https://stocks.events/data/years/YYYY.json` (see `/data` and `/methodology`); snapshot in `data/inputs/stocks_events/` | Built only from official NSE and BSE corporate-action files; keyed by ISIN issuer stem. 2020–2026 marked full coverage. |
| NSE corporate actions (MCP) | Cross-check of splits/bonuses; dividend text | `https://mcp.nseindia.in/bhavcopy/cm/mcp`, tool `get_corporate_actions` | Starts ~Nov 2020; misses many SME-period bonuses. |
| Split/bonus calendar | Cross-check of splits/bonuses | `data/inputs/cross_check_sources/corp_actions_adjustment.zip` | From the owner's other project; NSE bulk feed + BSE gap-fill. Shares NSE's SME blind spot. |
| Zerodha Kite Connect | Independent listing-day candles; adjusted daily history (split/bonus steps) | `api.kite.trade/instruments/historical/{token}/day` | Needs an API key and a daily access token. Kite's adjusted prices also reflect dividends and rights, so they are a cross-check, not the source. |
| Nifty Indices | Nifty 500 price and total-return index, other Nifty indices | niftyindices.com history; snapshot in `data/inputs/indices/` | TRI to 25 Sep 2026; carried to 28 Sep with the price index. BSE SME IPO index from bseindia.com history. |
| AMFI | Market-cap rank cutoffs for size buckets | `https://www.amfiindia.com/otherdata/categorisation-of-stocks`; the 18 spreadsheets are in `data/inputs/amfi/` | Jan–Jun 2018 to Jan–Jun 2026. Cutoffs in `amfi_cutoffs.csv`, rebuilt by `verify/check_size.py`. |
| NSE / BSE listing notices; NSE final prospectus | Exact post-issue share counts for 27 boundary cases | URLs and quoted evidence in `post_issue_shares_exact.csv` | 26 from listing notices; NSE's own IPO from its prospectus. |
| Source B spreadsheet | Cross-check of universe and listing closes | `data/inputs/cross_check_sources/source_B_IPO_Listing_analysis_WIP.xlsx` | Third-party compilation; errors documented below. |
| Source C spreadsheet | Cross-check (rejected) | `data/inputs/cross_check_sources/source_C_ipo_companies_data.xlsx` | SME dates one day early; most Main Board "listing prices" are not the close. |

## Methods

**Universe.**
- IPOs with a listing date from 1 Jan 2020 to 28 Sep 2026, taken from the site's issue index.
- REITs, InvITs and follow-on offers are excluded.
- Board labels come from the exchange: NSE Emerge series SM/ST, or BSE SME groups M/MT/TS, mean SME.

**Listing return.**
- Listing-day close ÷ issue price − 1, rounded half-up to whole basis points. Unadjusted.
- Exchange rule: use the NSE close when the IPO traded on NSE on listing day, otherwise the BSE close. For 10 Main Board IPOs this differs from the starting data, which used BSE. Median effect 0.2 points; largest 5.7 points (Burger King: NSE ₹135.00 vs BSE ₹138.40).

**Market adjustment on listing day.**
- The Nifty 500's move from offer-close date to listing date.
- 83 offer-close dates were estimated: 80 as opening date + 2 trading days (a rule exact in 82% of known cases), and 3 by T+3.

**Size.**
- Market cap at issue = post-issue shares × issue price.
- Buckets: Large = AMFI rank 1–100, Mid = 101–250, Small = 251–500, Micro = beyond 500 (a convention; SEBI does not define micro).
- The AMFI list used is the latest one whose period ended at least 7 days before listing.
- Share counts, in order of preference:
  - the listing-day NSE MCAP (607 IPOs);
  - exact listing-notice or prospectus counts (27);
  - otherwise, the 1 Feb 2024 NSE MCAP divided by the split/bonus multiplier between listing and that date.
- The estimate's accuracy, tested on 604 IPOs with exact counts: median error 0%, 90th percentile 2.1%, same bucket in 604 of 604 cases.
- Share issuance after listing makes older estimates slightly high, so the Micro count is a floor.
- Every SME IPO is treated as micro: the largest measured was ₹800 crore at issue, against a rank-500 cutoff that never fell below ~₹1,694 crore.

**Post-listing returns.**
- Horizons: 21, 63, 126, 252, 504 and 756 exchange trading days, plus listing to 28 Sep 2026.
- The price used is the close on the horizon day, or the last trade before it. A last trade more than 10 trading days earlier is flagged "stale / stopped trading", and the IPO is kept at its last price. There is no survivorship filter.
- Two starting points: the issue price (the allottee) and the listing-day close (the listing-day buyer).

**Corporate actions.**
- Candidate share events (split, bonus, consolidation) come from stocks.events plus clean split/bonus steps in Kite's adjusted history.
- Each event must match the raw overnight price move: gap × factor within 25% of 1, tested from 3 trading days before to 5 after the recorded date, since some records carry the record date.
- Where sources disagree, the ratio closest to the raw move wins. Same-day split and bonus are combined; duplicates are applied once.
- Rights issues use the theoretical ex-rights price from the official terms (for example "13:118 at Rs 310").
- 232 events applied. The price factor matches Kite's overall factor within 2% for 960 of 982 IPOs. The rest are Kite's dividend adjustments and two confirmed Kite history glitches (Ksolves, Likhitha).

**Dividends and benchmark.**
- Main Board: total return (dividends reinvested at the previous close) against the Nifty 500 TRI.
- SME: price return against the Nifty 500 price index, because SME dividends are negligible.
- Over 2020–2026 the Nifty 500's dividend return was about 1.16% a year. Main Board IPOs paid a mean 0.26% a year and a median of 0.
- Excess return = IPO return − index return over the IPO's own dates.

**Listing-year tables.** Annualised return from the listing-day close to 28 Sep 2026, for IPOs listed at least a year. "Ahead of index" compares each IPO with the index over its own window.

## What we found wrong in the starting data

The Codex export's prices were right: every one of the 1,409 closes we could compare matched the official bhavcopy on the same exchange to the paisa. The problems were in the list of IPOs and in coverage.

| Problem | Count | Examples |
|---|---|---|
| Same IPO counted twice in return statistics (both records `cohort_include = 1`) | 9 pairs | Burger King / Restaurant Brands Asia, IRFC, IKIO, Abans, Radiant Cash, Sah Polymers / Aeroflex Neu, Landmark, Monarch Surveyors, Network People |
| "Unmatched" records that were renamed duplicates of priced IPOs | ~26 | Zomato / Eternal, Macrotech / Lodha, Barbeque-Nation / United Foodbrands, Ami Organics / Acutaas |
| Listed IPOs with no close in the export (fetch failures, not non-listings) | 76 | 55 SME listings from 2026, 11 from 2021, 3 from 2020 |
| Wrong issue price on a duplicate record | 1 | Radiant Cash ₹99 (true ₹94; NSE previous close confirms) |
| Main Board label on SME stocks | 2 | Global Longlife Hospital, Shashwat Furnishing (BSE group MT) |
| Record for an IPO with no first-day trade | 1 | Trafiksol ITS (reported cancelled before listing; confirm with the BSE notice before citing) |
| Main Board prices taken from BSE where NSE traded | 10 | See the exchange rule above |

`data/verified/exclusions.csv` lists the 12 removed records. `ipo_cohort_verified.csv` has a `codex_status` and a `note` for every row.

## How well the sources agree

| Check | Result |
|---|---|
| Codex export vs its own manifest (checksums, counts, arithmetic) | All reproduce |
| Codex closes vs official bhavcopy, same exchange | 1,409 of 1,409 equal to the paisa |
| Verified closes vs Kite listing-day candle | 1,260 exact; 201 differ only by a uniform later split/bonus factor (open and close scaled together); 25 no current Kite instrument |
| NSE previous close on listing day vs issue price | All NSE rows agree after the Radiant correction |
| Verified closes vs source B | 1,424 of 1,472 shared IPOs exact. Of the 48 differences: 17 are BSE vs NSE; the rest are source B errors (issue price in the close column, next-day close, wrong ISINs) |
| Universe vs source B | Both 1,498 before our last exclusions; source B's extra rows are REITs, InvITs and follow-ons |
| Offer-close dates vs data bank NSE IPO history | 949 of 949 agree |
| Size estimate vs exact share counts | 604 of 604 same bucket; 22 boundary estimates within −9% to 0% of listing-notice counts |
| Split/bonus: stocks.events vs derived events (before merging) | 1,439 of 1,481 agree; all 42 disagreements resolved by the raw price test |
| Adjusted price factor vs Kite | 960 of 982 within 2% |

## Limitations and open items

- **Universe.** Not certified as every Indian IPO. It is the site's issue index after cleaning, and it agrees with source B row for row. A reconciliation against NSE's and BSE's own past-issue lists would close this.
- **Issue size (₹) not used.** Only 229 of 774 records reconcile with shares offered × price: there are unit errors, and "shares offered" excludes the anchor portion. So money raised and money left on the table are not in the report.
- **Stale SME prices.** 38 SME stocks stopped trading or trade rarely; they are held at their last traded price. Treating them as total losses would lower the SME results.
- **Changing mix across horizons.** 3-year figures cover only 2020–2023 listings. The fixed-group tables follow the same IPOs throughout.
- **Old share-count estimates.** Share issuance between listing and February 2024 is not removed from pre-2024 estimates, so their market caps may be slightly high.
- **Dividends.** Dividends before November 2020 rely on stocks.events alone. BSE-only Main Board IPOs (CAMS, Protean, NSDL, NSE) are in the same source, but dividends there were not separately cross-checked.
- **Trafiksol ITS.** The exclusion rests on the absence of any first-day trade. The cancellation should be confirmed from the BSE notice before citing it.
- **SME opening cap.** Observed in the data, not yet matched to the exchange circular.

## How to verify independently

Requirements: Python 3.10+ and `pip install -r requirements.txt` (pandas, numpy, requests, openpyxl, python-dateutil). The network checks download official files and cache them in `verify/.cache/`. No login or API key is needed.

```bash
python verify/check_calculations.py                          # offline: every published table, return and index window recomputed
python verify/check_listing_closes.py --n 60                 # sample across every board x year; re-downloads listing-day bhavcopies
python verify/check_listing_closes.py --all                  # all 1,486 IPOs
python verify/check_size.py --n 30                           # AMFI cutoffs from raw spreadsheets, 450 buckets, sampled share counts vs NSE MCAP
python verify/check_post_listing_prices.py --n 40 --horizon 1y   # horizon-date closes and corporate-action factors vs bhavcopies
python verify/reproduce_post_listing.py                      # full independent rebuild of post-listing returns (30-60 min first run)
```

Results when handed off:

| Script | Result |
|---|---|
| `check_calculations.py` | 37 of 37 checks pass |
| `check_listing_closes.py --n 60` | 56 sampled, 56 exact |
| `check_size.py --n 20` | AMFI cutoffs rebuilt for 17 periods, 450 of 450 buckets, 20 of 20 share counts |
| `check_post_listing_prices.py` | 30 of 30 at 1 year; 30 of 30 to date, half the sample drawn from IPOs with corporate actions |
| `reproduce_post_listing.py` | 7,899 of 7,899 rows reproduce; see below |

### Reproduction result

Run on 30 September 2026, rebuilding every post-listing number from about 3,350 freshly read NSE and BSE bhavcopies:

- **Tracking:** all 1,486 IPOs were followed by ISIN.
- **Corporate actions:** all 229 split, bonus and rights factors re-tested against the raw price move on their ex-date were confirmed.
- **Row by row:** all 7,899 published IPO x horizon rows reproduce, with the same raw close, the same return from listing (within 0.05 points) and the same excess over the index.
- **Headline figures:** they reproduce exactly. Main Board: 1-year median +0.7% with 41.1% ahead of the index; 2-year median +1.5% with 34.3% ahead. SME: 1-year median −1.3% with 41.3% ahead; 2-year median +12.4% with 43.8% ahead.

The reproduction follows stocks by ISIN, while the original pipeline follows them by symbol and scrip code, so agreement also rules out tracking errors from renames and migrations. It does reuse the list of applied corporate-action events, although it re-tests each one. An event missing from that list would not be caught; a manual check of splits and bonuses for a sample of stocks, against exchange records, would.

Suggested checks beyond the scripts:
1. **Universe.** Compare yearly counts with NSE's and BSE's past-issue lists (Main Board and SME) and with SEBI annual data. Differences should be explainable as REITs, InvITs, follow-ons, or the exclusions.
2. **Hard cases by hand in the bhavcopies.**
   - Burger King / RBA: rename, NSE vs BSE close.
   - Radiant Cash: issue price ₹94.
   - Abans, Sah Polymers, IKIO: manual lookups.
   - DU Digital: 20× split/bonus after an unlisted rename.
   - Varanium Cloud: bonus + split on the same day.
   - Mos Utility and Upsurge Seeds: duplicate or misdated bonus records.
   - Utkarsh SFB, SAR Televenture, Dhariwalcorp, Stallion: rights issues.
   - Likhitha, Ksolves: records one day off, and Kite glitches.
3. **Size.** Pick IPOs near a cutoff (`size_and_benchmark.csv`) and compare `shares_out` with the listing notice.
4. **Benchmark.** Recompute a few Nifty 500 window returns from niftyindices.com history.
5. **SME opening cap.** Find the NSE/BSE circular that caps SME opening prices and confirm its effective date.

`scripts/pipeline/` contains the scripts that produced the data, in run order:
`verify_bhav.py` → `verify_kite.py` → `build_verified.py` → `size_classify.py` → `ca_adjust.py` → `anchor_feb2024.py` → `fetch_panel.py` → `kite_steps.py` → `post_listing.py` → `summarise_post.py` → `build_report_data.py`.
They read paths on the original machine and a Kite token from a local `.env` (not included). Treat them as a precise description of the method. The portable equivalent of the post-listing step is `verify/reproduce_post_listing.py`.

## File dictionary

**`data/verified/ipo_cohort_verified.csv`** (1,515 rows)

| Column | Meaning |
|---|---|
| `issue_id` | Stable ID from the site's issue index |
| `company_name`, `board_type`, `listing_date`, `listing_year` | Identity; board as corrected from the exchange series/group |
| `issue_price_inr` | Final issue price |
| `venue` | NSE + BSE, NSE only, BSE only (from listing-day bhavcopies) |
| `price_exchange` | Exchange whose close is used (NSE if it traded there) |
| `listing_open_inr`, `listing_close_inr` | Official listing-day open and close on `price_exchange` |
| `return_bps`, `return_pct` | Listing return, close vs issue |
| `close_basis` | How the close was sourced (bhavcopy, manual bhavcopy lookup, or starting-data close reproduced by Kite) |
| `codex_close`, `codex_status` | Starting-data close and how it compares |
| `nse_symbol`, `nse_series`, `nse_close`, `bse_symbol`, `bse_series`, `bse_close` | Listing-day rows on each exchange |
| `kite_check` | exact / differs by later split-bonus adjustment / no Kite instrument |
| `note` | Corrections and manual resolutions |

**`data/verified/post_listing_returns.csv`** (one row per IPO and horizon)

| Column | Meaning |
|---|---|
| `horizon`, `horizon_date`, `price_date`, `status` | Horizon, target date, date of the price used, and freshness flag |
| `raw_close` | Unadjusted exchange close on `price_date` |
| `cum_factor` | Split/bonus/rights factor since listing (shares or entitlements per listing-day share) |
| `adj_close` | `raw_close × cum_factor`: value of one listing-day share, price only |
| `tr_factor` | Dividend reinvestment factor since listing |
| `ret_from_issue`, `ret_from_listing` | Price return (%) |
| `tr_from_issue`, `tr_from_listing` | Total return (%) |
| `basis` | Main Board: total return vs Nifty 500 TRI. SME: price return vs Nifty 500 price index |
| `r_issue`, `r_listing` | The return on that basis |
| `idx_issue`, `idx_listing` | Index return over the same window (from offer close or listing date) |
| `x_issue`, `x_listing` | Excess return, percentage points |
| `years` | Listing date to `horizon_date`, in years |

**`data/verified/size_and_benchmark.csv`**: `offer_close_date` and `close_date_basis`; `nifty500_pct` (index move, offer close to listing); `excess_nifty500_pct`; `shares_out` and `shares_basis`; `mcap_issue_cr`; `amfi_period_end`; `size_bucket`; `share_mult_used` and `share_mult_basis` (the split/bonus adjustment used for estimated share counts).

**`data/verified/corporate_action_events_applied.csv`**: `ex_date` (where the price move occurred), `recorded_date` (the source's date), `factor`, `source`, `alternatives` (every candidate ratio), `raw_gap` (actual close ÷ previous close), `accepted`.

**`data/verified/verification_detail.csv`**: raw matching output before cleaning. It includes matches later rejected; for example, loose "previous close = issue price" matches that hit bonds or unrelated stocks. Use `ipo_cohort_verified.csv` for the cleaned values.
