# Pipeline scripts (reference)

These are the scripts that built `data/verified/`, copied as run. They point to paths on the
original machine (a scratch directory, the site's `data/raw/nse_pr/` cache, and a local data
bank of Nifty index history), and the Kite steps read an API key and daily access token from
a local `.env` that is not part of this repository. Read them as the exact specification of
the method; to reproduce results independently, use `verify/` and the official sources listed
in the top-level README.

Path placeholders used in these scripts:
`<WORKDIR>` is the scratch directory where intermediate files were written;
`<SITE_REPO>` is the IPO site repository, used only for its cached NSE PR bundles
(`data/raw/nse_pr/`, public from nsearchives) and the Codex export;
`<DATA_BANK>` is a local store of Nifty index history, now snapshotted in `data/inputs/indices/`.

Run order:

1. `verify_bhav.py`: listing-day NSE/BSE bhavcopy match for every IPO
2. `verify_kite.py`: Kite listing-day candles
3. `build_verified.py`: exclusions, exchange rule, board correction → `ipo_cohort_verified.csv`
4. `size_classify.py`, `ca_adjust.py`, `anchor_feb2024.py`: market cap at issue and size buckets
5. `fetch_panel.py`: daily bhavcopy panel for both exchanges, 2020 to 28 Sep 2026
6. `kite_steps.py`: split/bonus steps from Kite adjusted history
7. `post_listing.py`: corporate actions (stocks.events + Kite, price-move confirmed), dividends, horizon returns
8. `summarise_post.py`: benchmarks (Nifty 500 PR/TRI) and summary tables
9. `build_report_data.py`: `report_data.json` for the report page

`nse_mcp.py` and `fetch_ca.py` query NSE's corporate-action MCP server for cross-checking.
