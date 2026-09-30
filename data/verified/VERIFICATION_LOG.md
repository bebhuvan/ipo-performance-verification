# Verification of the 2020–2026 IPO listing cohort

Done on 30 September 2026. The Codex export in the parent folder is left unchanged;
this folder holds the independently verified cohort and the evidence for it.

## Result

`ipo_cohort_verified.csv` has **1,486 IPOs** listed from 1 January 2020 to 28
September 2026. Every one has a listing-day close taken from an official
exchange end-of-day file (bhavcopy). Coverage is complete for every year and board.

| Check | Outcome |
|---|---|
| Codex export vs its `manifest.json` | All checksums, counts and return arithmetic reproduce exactly |
| Codex closes vs official bhavcopy, same exchange | 1,409 of 1,409 comparable closes equal to the paisa |
| Kite daily candles vs verified close | 1,260 exact; 201 differ only by a uniform later split/bonus factor (open and close scaled together); 25 have no current Kite instrument |
| Issue prices vs NSE listing-day previous close | All NSE rows agree except Radiant Cash's duplicate record (₹99 vs true ₹94) |
| WIP workbook (source B) | 1,424 of 1,472 shared IPOs agree exactly. The 48 differences are the workbook using BSE where we use NSE (17), putting the issue price in the close column, or recording the next day's close |
| `ipo_companies_data 1.xlsx` (source C) | Not usable for validation: SME dates are one day early, and most Main Board "listing prices" are not the day's close |

## What changed from the Codex export

1. **12 records excluded** (`exclusions.csv`). Nine duplicate pairs were counted twice in
   Codex's return statistics, each with `cohort_include = 1` on both records. Examples:
   Burger King/Restaurant Brands Asia, IRFC, IKIO, Abans, Radiant Cash and Sah
   Polymers/Aeroflex Neu. Two unmatched records were renamed duplicates (Suumaya/Rangoli
   and DMR). Trafiksol ITS has no first-day trade on either exchange.
2. **76 missing closes filled** from official bhavcopies. This covers 55 SME listings from
   2026, 11 from 2021 and 3 from 2020. Codex's 2020–21 and 2026 SME gaps were fetch
   failures; the IPOs did list.
3. **Exchange rule made explicit.** We use the NSE close when the IPO traded on NSE on
   listing day and the BSE close otherwise, which covers BSE SME listings. This changes 10
   Main Board closes where Codex used BSE. The median absolute effect is 0.2 percentage
   points and the largest is 5.7 (Burger King, now Restaurant Brands Asia: NSE ₹135.00 vs BSE ₹138.40).
4. **Board labels come from the exchange.** NSE Emerge series SM/ST and BSE SME groups
   M/MT/TS mark an SME listing. Global Longlife Hospital and Shashwat Furnishing were
   labelled Main Board but are BSE SME stocks (group MT).
5. **Venue.** Every IPO is searched on both exchanges by ISIN. Main Board: 446 listed on
   NSE and BSE, and 4 on BSE only (CAMS, Protean, NSDL and NSE itself). SME: 552 on NSE
   Emerge and 484 on BSE SME.
6. About 26 unmatched records were renamed duplicates. That is why Codex's coverage table
   overstated what was missing.

## Method

- **Identity.** An IPO is located in its listing-date bhavcopy by ISIN, by symbol or BSE
  scrip code, or as a first-day row: on NSE the previous close equals the issue price, and
  on BSE the previous close is zero. Two looser matching rules picked up bonds and
  unrelated stocks. Those matches are accepted only when a second source (Codex or Kite)
  reproduces the price to the paisa. Five IPOs were resolved by hand from the cached files;
  see the `note` column.
- **Return.** `(listing close / issue price − 1) × 10,000`, rounded half up to whole basis
  points. It is unadjusted and covers listing day only.
- **Sources.** NSE CM bhavcopy (`nsearchives.nseindia.com`, old and UDiFF formats), BSE
  equity bhavcopy (`bseindia.com`, old and new formats), and Kite Connect historical daily
  candles. The cached raw files were kept in the session scratchpad and can be re-fetched
  with `scripts/verify_bhav.py`.

## Limits

- The universe is the site's issue index after de-duplication. It agrees with the WIP
  workbook row for row except for REITs, InvITs and follow-on offers (correctly excluded)
  and a few edge dates, but it has not been reconciled against an exchange-certified list
  of all IPOs. Do not describe the results as covering every Indian IPO.
- NSE and BSE closes can differ. The rule above is fixed; `nse_close` and `bse_close` are
  both kept so a single-exchange sensitivity check is possible.
- 2026 runs to 28 September only.
- No post-listing, long-run or adjusted returns are computed here.

## Files

- `ipo_cohort_verified.csv`: one row per IPO, with price provenance (`price_exchange`,
  `close_basis`, `codex_status`, `kite_check`, `note`)
- `exclusions.csv`: the 12 removed records and why
- `summary_by_year_board.csv`: count, median, share above, at and below issue, and
  quartiles, with Codex's original figures alongside
- `distribution_by_year_board.csv`: return buckets
- `verification_detail.csv`: raw per-issue match results from bhavcopy and Kite
- `scripts/`: `verify_bhav.py` → `verify_kite.py` → `build_verified.py`. The Kite step
  reads the token from `.env`.

## Benchmark and size (added 30 September 2026)

Output files: `size_and_benchmark.csv` (per IPO), `benchmark_by_year_board.csv`,
`main_board_by_size.csv` and `amfi_cutoffs.csv`.

**Benchmark window.** From the offer-close date to the listing-day close. The issue price
is fixed at close, and the money stays locked until listing. The median window is
5 calendar days.
- 1,403 offer-close dates are published. The data bank's NSE IPO history agrees with 949
  of 949 that it covers.
- 80 are estimated as the opening date plus 2 trading days. This rule is exact for 82%
  of known cases, and an error of a day or two moves an index return by about 0.1 point.
- 3 IPOs listed on 28 September use listing minus 3 trading days (T+3).

**Index.** The primary benchmark is the Nifty 500 (price return; dividends are negligible
over about 5 days). The size-matched sensitivity uses:
- Nifty 100 for large caps;
- Nifty Midcap 150 for mid caps;
- Nifty Smallcap 250 for small and micro caps (the data bank has Nifty Microcap 250 only
  from June 2026);
- NIFTY SME Emerge for NSE SME listings and BSE SME IPO for BSE SME listings.

The IPO indices are not used as the primary benchmark because they are built from recent
IPOs. Excess return = IPO listing return − index return, in percentage points.

**Size.** This follows SEBI's categorisation through AMFI's semi-annual lists: rank 1–100
is large, 101–250 is mid, and 251 onward is small. "Micro" (rank beyond 500) is a
convention; SEBI does not define it.
- Market cap is taken at the issue price: post-issue shares × issue price.
- It is compared with the AMFI list in force at listing, meaning the latest six-month
  period ending at least 7 days before the listing date.
- Shares come from the listing-day NSE MCAP file for 607 IPOs (the file exists from
  February 2024).
- For 378 IPOs, shares are estimated as current NSE shares (28 September 2026, traced
  through NSE symbol changes) divided by the cumulative split/bonus factor (NSE listing
  close ÷ Kite adjusted close).
- Tested on 604 IPOs where the exact count is known, the estimate has a median error of
  0%, is within 2.1% for 90% of them, and gives the same bucket in 604 of 604 cases.
- Every SME IPO with a known market cap is micro: the maximum is ₹800 crore, against a
  rank-500 cutoff that never fell below about ₹1,700 crore. BSE SME listings without a
  market cap raised at most ₹190 crore each and are treated as micro.
- 5 Main Board IPOs are unclassified: CAMS, Protean, NSDL and NSE (BSE only), and
  Restaurant Brands Asia (symbol changed, rights dilution). Their post-issue share counts
  should come from their prospectuses.

**Corporate-action check.** Splits, bonuses, rights issues and buybacks since listing were
pulled for all 994 NSE-listed IPOs from NSE's corporate-actions service
(`mcp.nseindia.in`, `get_corporate_actions`). They are saved in
`corporate_actions_check.csv`.
- **Listing-day returns and benchmark windows are unaffected.** Both end at the first
  listing-day trade, and no ex-date can fall in between.
- **Share-count estimates depend on these events.** Without the adjustment, 16 of 176
  estimated Main Board IPOs would land in the wrong bucket.
- **NSE's list is incomplete.** It starts in November 2020 and misses several bonuses. For
  example, it misses Lodha's 1:1 bonus and HMA Agro's ₹10→₹1 split, both of which Kite's
  prices reflect exactly.
- **The rule used:** Kite's price factor is accepted as a share multiplier when it matches
  NSE's recorded events or is a clean split/bonus ratio. Otherwise it is treated as a
  price-only adjustment, such as a dividend or rights issue, and NSE's split/bonus product
  is used instead (`scripts/ca_adjust.py`). Of the 378 estimated share counts, 305 have
  Kite and NSE agreeing, 55 are Kite-only clean ratios and 18 are price-only factors.
- **The rule changed one bucket.** UTI AMC moves from Small to Mid: Kite's factor of 1.154
  is not a split or bonus. The buckets for Lodha and HMA Agro depend on trusting Kite, and
  both use exact 2.00 and 10.00 factors.
- 10 Main Board IPOs are within 5% of a bucket cutoff. The estimate's error is below 2.1%
  for 90% of cases, and every one of 604 test cases landed in the correct bucket.

**Share-count anchor, revised.** A third source was tested: the site's split/bonus calendar
(`corp_actions_adjustment.zip`, built from NSE's bulk corporate-actions feed with BSE
gap-fills). Each source was scored against the true change in share count, taken from NSE
MCAP files: listing day to today for 604 IPOs, and 1 February 2024 to today for 378 older
IPOs.
- Kite matched the true multiplier within 10% for 584 of 604 IPOs, NSE's list for 574 and
  the calendar for 572.
- The two NSE-based sources miss many bonuses issued while a company was on the SME
  segment.
- None of the three captures new share issuance (QIPs, preferential allotments, ESOPs,
  mergers). Swiggy has 23% more shares than at listing, Zomato/Eternal 11% more.
  Estimating from today's share count therefore overstates market cap for older IPOs.
- Pre-February-2024 IPOs are therefore now anchored on the 1 February 2024 MCAP, the
  earliest available. That count is divided by the split/bonus multiplier between listing
  and that date, measured as the NSE raw close ÷ Kite adjusted close on 1 February 2024.
  The factor is snapped to a clean ratio, and the calendar is used where Kite has no
  instrument.
- This removed up to 2.7 years of dilution and moved 5 Main Board IPOs from Small to Micro:
  Mrs. Bectors, Easy Trip, Tega, Fusion Micro Finance and Fedbank. Fusion's old estimate
  had included its later rights issue.
- Mrs. Bectors (₹1,694 crore) sits on the rank-500 cutoff (₹1,694.4 crore) and should be
  read as borderline.
- Residual bias: any new shares issued between listing and February 2024 still inflate the
  estimate, which can only push an IPO into a larger bucket. The Main Board micro count is
  therefore a lower bound.

**Exact share counts for boundary cases.** 27 IPOs were looked up in primary documents
(`post_issue_shares_exact.csv`). These are the 22 estimates within 10% of a size cutoff and
the 5 previously unclassified IPOs.
- 26 counts come from the "No. of securities" line in the NSE or BSE listing notice.
- NSE's own count comes from its final prospectus (Capital Structure, 247.5 crore shares of
  ₹1). It listed only on BSE, and BSE's 2026 notices were not reachable.
- For the 22 estimates, the exact count was within −9% to 0% of the estimate. 14 matched
  within 1%, and every deviation was downward, as the dilution bias predicts.
- Three buckets changed. Shyam Metalics moves from Mid to Small: the listing notice
  records 18.8 million shares cancelled in a merger. Data Patterns and CMS Info Systems
  move from Small to Micro.
- The five new classifications are NSE Large; CAMS, NSDL and Restaurant Brands Asia
  (Burger King) Small; and Protean Micro.
- All 450 Main Board IPOs are now classified: 15 Large, 30 Mid, 97 Small and 308 Micro.

## Post-listing returns (added 30 September 2026)

Output files: `post_listing_returns.csv` (one row per IPO and horizon),
`post_listing_by_horizon_{mainboard,sme}.csv`, `post_listing_fixed_cohort_2y_{mainboard,sme}.csv`,
`vintage_{mainboard,sme}.csv` and `corporate_action_events_applied.csv`.

- **Prices.** Raw daily closes come from the official bhavcopies for every trading day from
  2020 to 28 September 2026, on both exchanges. NSE from June 2022 to 17 September 2026 is
  taken from the data bank's `nse_bhavcopy`; the rest was downloaded.
- **Tracking.** Each IPO is followed on the exchange whose listing close is used. NSE stocks
  are followed by symbol, through NSE's symbol-change file and ISIN-stem continuation for
  renames missing from that file (Burger King → RBA, DU Digital → DUGLOBAL). BSE stocks are
  followed by scrip code.
- **Horizons.** 21, 63, 126, 252, 504 and 756 exchange trading days, plus listing to
  28 September 2026. The price used is the close on the horizon day, or the last trade before
  it. A last trade more than 10 trading days earlier is flagged "stale / stopped trading", and
  the IPO is kept at its last price.
- **Corporate actions.** Splits, bonuses and consolidations come from stocks.events (built
  from official NSE and BSE files), combined with split/bonus steps from Kite's adjusted
  history.
  - Every event must match the raw overnight price move: the adjusted move must be within
    25%, tested from 3 trading days before to 5 after the recorded date. Where sources
    disagree, the ratio that best matches the raw move is used.
  - Same-day split plus bonus is combined, and duplicates are applied once.
  - Rights issues use the theoretical ex-rights price from the official terms.
  - 232 events were applied. The price factor matches Kite's overall adjustment within 2%
    for 960 of 982 IPOs; the rest are Kite's dividend adjustments and two confirmed Kite
    glitches (Ksolves and Likhitha).
- **Dividends.** Amounts are the stocks.events `div_amount`, reinvested at the previous close.
  The Main Board is reported as total return against the Nifty 500 TRI; the TRI is carried
  from 25 to 28 September with the price index. SME is reported as price return against the
  Nifty 500 price index. Dividends add a mean of 0.4 points at one year and 3.9 points at
  three years for the Main Board, and the median is about zero.
- **Interpretation.** Each horizon includes only the IPOs that have reached it, so the mix
  changes across columns. The fixed-cohort tables follow the same 2-year group throughout.
  In the listing-year tables, "beat index since listing" compares each IPO with the index
  over its own window.

## Report (30 September 2026)

`report/ipo-performance.html` is built from `report_data.json`, which
`scripts/build_report_data.py` generates from the verified files only. The template is
`report/ipo_report.template.html`. It was published as a private artifact:
https://claude.ai/artifact/4UCnG8zQJVidMuVp1wM2gq

Findings recorded in the report beyond the tables:
- **SME opening cap.** Since January 2025, no SME IPO opened more than 90% above its issue
  price, and 33 opened at exactly +90%. Before 2025, 60 opened higher. The 2025–26 SME
  listing gains are therefore not like-for-like with 2024's.
- **Issue size left out.** Issue size (₹) was not used: only 229 of 774 records reconcile
  with shares offered × price, because of unit errors and the anchor portion. Money raised
  and money left on the table need a separate verification pass.
