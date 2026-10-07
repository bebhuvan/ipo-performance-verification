"""Recompute the published numbers from the per-IPO files. No network needed.

Checks:
  1. every listing return equals (close / issue - 1), rounded half-up to whole basis points;
  2. the year x board listing summary (summary_by_year_board.csv) reproduces;
  3. the post-listing horizon tables reproduce from post_listing_returns.csv;
  4. listing-year (vintage) 'ahead of index' shares reproduce;
  5. internal consistency: no duplicate IPOs, board counts, excluded records absent.

Usage:  python verify/check_calculations.py
"""
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V = pd.read_csv(ROOT / "data/verified/ipo_cohort_verified.csv")
E = pd.read_csv(ROOT / "data/verified/exclusions.csv")
R = pd.read_csv(ROOT / "data/verified/post_listing_returns.csv")
M = json.loads((ROOT / "data/verified/update_manifest.json").read_text())
fails = 0


def check(name, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    fails += (not cond)


# 1. arithmetic
bps = [int(((Decimal(str(c)) / Decimal(str(i)) - 1) * 10000).quantize(Decimal(1), ROUND_HALF_UP))
       for c, i in zip(V.listing_close_inr, V.issue_price_inr)]
check("listing return basis points recompute for all rows", (np.array(bps) == V.return_bps.values).all())

# 5. consistency
check("manifest cohort total, no duplicate issue_id", len(V) == M["count"] and V.issue_id.is_unique)
check("board counts agree with manifest", V.board_type.value_counts().to_dict() == M["counts_by_board"])
check("excluded records are absent", not V.issue_id.isin(E.issue_id).any())
check("listing dates within listing cutoff", V.listing_date.between("2020-01-01", M["listing_as_of"]).all())
check("post-listing dates within separate price cutoff", R.horizon_date.dropna().le(M["post_listing_as_of"]).all())

# 2. listing summary
S = pd.read_csv(ROOT / "data/summaries/summary_by_year_board.csv")
g = V.groupby(["board_type", "listing_year"]).return_pct
re = pd.DataFrame({"n": g.size(), "median_%": g.median().round(2), "above_issue_%": g.apply(lambda s: (s > 0).mean() * 100).round(1)}).reset_index()
m = S.merge(re, on=["board_type", "listing_year"], suffixes=("", "_re"))
check("listing summary: counts, medians, % above issue", len(m) == len(S) and (m.n == m.n_re).all()
      and np.allclose(m["median_%"], m["median_%_re"]) and np.allclose(m["above_issue_%"], m["above_issue_%_re"]))

# 3. horizon tables
for tag, board in [("mainboard", "Main Board"), ("sme", "SME Board")]:
    T = pd.read_csv(ROOT / f"data/summaries/post_listing_by_horizon_{tag}.csv").set_index("horizon")
    d = R[R.board_type == board]
    for h in T.index:
        x = d[d.horizon == h]
        okn = len(x) == T.loc[h, "n"]
        okm = abs(x.r_listing.median() - T.loc[h, "median_from_listing_%"]) < 0.051
        okb = abs((x.x_listing > 0).mean() * 100 - T.loc[h, "beat_index_from_listing_%"]) < 0.051
        check(f"{board} {h}: n, median from listing, % ahead of index", okn and okm and okb)
    # returns column = basis: total return (Main Board) or price return (SME)
    col = "tr_from_listing" if board == "Main Board" else "ret_from_listing"
    y = d.dropna(subset=["r_listing"])
    check(f"{board}: r_listing uses {col}", np.allclose(y.r_listing, y[col]))
    check(f"{board}: excess = return - index", np.allclose(y.x_listing, y.r_listing - y.idx_listing))

# 4. vintage
for tag, board in [("mainboard", "Main Board"), ("sme", "SME Board")]:
    T = pd.read_csv(ROOT / f"data/summaries/vintage_{tag}.csv").set_index("listing_year")
    t = R[(R.board_type == board) & (R.horizon == "to_date") & (R.years >= 1)]
    for y, x in t.groupby("listing_year"):
        check(f"{board} listed {y}: count and % ahead of index since listing",
              len(x) == T.loc[y, "n"] and abs((x.x_listing > 0).mean() * 100 - T.loc[y, "beat_index_since_listing_%"]) < 0.051)

# 6. index windows, recomputed from the included Nifty series
PRX = pd.read_csv(ROOT / "data/inputs/indices/nifty500_price.csv").set_index("date").close.sort_index()
TRX = pd.read_csv(ROOT / "data/inputs/indices/nifty500_tri.csv").set_index("date").close.sort_index()
for d in PRX.index[PRX.index > TRX.index.max()]:
    TRX.loc[d] = TRX.loc[TRX.index.max()] * PRX.loc[d] / PRX.loc[TRX.index.max()]
TRX = TRX.sort_index()
lv = lambda s, d: s[s.index <= d].iloc[-1]
B = pd.read_csv(ROOT / "data/verified/size_and_benchmark.csv").merge(V[["issue_id", "listing_date", "return_pct"]], on="issue_id")
re_ix = [(lv(PRX, l) / lv(PRX, o) - 1) * 100 for o, l in zip(B.offer_close_date, B.listing_date)]
check("listing-day Nifty 500 move (offer close -> listing) recomputes for all IPOs", np.allclose(re_ix, B.nifty500_pct, atol=1e-4))  # published to 4 decimals
check("listing-day excess = listing return - index move", np.allclose(B.excess_nifty500_pct, B.return_pct - B.nifty500_pct, atol=1e-3))
Rh = R[R.horizon_date.notna() & R.idx_listing.notna()]
re_h = [(lv(TRX if b == "Main Board" else PRX, h) / lv(TRX if b == "Main Board" else PRX, l) - 1) * 100
        for b, l, h in zip(Rh.board_type, Rh.listing_date, Rh.horizon_date)]
check("post-listing index returns recompute (Main Board TRI, SME price)", np.allclose(re_h, Rh.idx_listing, atol=1e-6))

print(f"\n{fails} failure(s)")

sys.exit(1 if fails else 0)
