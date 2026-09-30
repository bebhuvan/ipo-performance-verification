# Data dictionary

`ipo_cohort.csv` and `ipo_cohort.jsonl` have one row per published listed IPO
record in the date window. Empty numeric cells mean unavailable, not zero.

| Column | Meaning |
|---|---|
| `issue_id` | Stable site issue slug; join key for this export. |
| `company_name` | Current display name; may differ from the name at listing. |
| `board_type` | Published `Main Board` or `SME Board` label. |
| `symbol`, `isin` | Published security identifiers, blank if unavailable. Neither alone identifies an offer. |
| `issue_url_path` | Relative URL of the issue page. |
| `offer_open_date`, `offer_close_date` | Published offer window, ISO date or blank. |
| `listing_date`, `listing_year` | Published first listing date and calendar year. |
| `issue_price_paise`, `issue_price_inr` | Final offer price, in integer paise and INR. |
| `listing_open_paise`, `listing_open_inr` | Verified listing-day opening price if available. |
| `listing_close_paise`, `listing_close_inr` | Verified listing-day close; blank for unmatched records. |
| `listing_close_return_bps`, `listing_close_return_pct` | Unadjusted close versus issue price; blank if no verified close. 100 bps = 1%. |
| `listing_price_source` | Matching source label from the published performance snapshot. |
| `verified_close` | `1` if a source-backed listing close exists; otherwise `0`. |
| `cohort_include` | `1` if verified and not an excluded duplicate; use this for IPO return summaries. |
| `duplicate_of_issue_id` | Primary issue ID when this priced row is a duplicate observation. |
| `quality_state` | Published issue quality label; the public index omits quarantined issues. |

`coverage_by_year_board.csv` counts records, not companies. Its
`verified_coverage_pct` is `verified_close_records / listed_issue_records ×
100`, before duplicate exclusion. `analysis_rows` removes duplicate priced
records. `missing_verified_close_records` counts records without a verified
close and reconciles with `unmatched_issues.csv`.

`unmatched_issues.csv` lists the 105 published IPO records without a
performance-snapshot close. `review_reason` describes the missing match; it
does not diagnose why the source observation is absent.
