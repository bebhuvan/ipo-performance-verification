"""Summaries of post-listing performance. Main Board: total return vs Nifty 500 TRI.
SME: price return vs Nifty 500 price index (dividends negligible). Writes CSVs to verified/."""
import glob
import duckdb, numpy as np, pandas as pd
S = "/tmp/claude-546000862/-home-bhuvanesh-r-Documents-Bhuvan-projects-IPO/213c5a5a-b9c6-4e64-80ea-71cc2d993201/scratchpad/"
OUT = "/home/bhuvanesh.r/Documents/Bhuvan projects/IPO/analysis/ipo-2020-2026/verified/"
DB = "/home/bhuvanesh.r/Documents/Data/Data bank/"
con = duckdb.connect()
fp = glob.glob(DB + "data/warehouse/source_native/nifty_index_history/*.parquet")
ft = glob.glob(DB + "data/warehouse/source_native/nifty_index_total_returns/*.parquet")
pr = con.execute(f"select date, close v from read_parquet({fp!r},union_by_name=true) where index_name='Nifty 500' and return_variant='price_return'").df()
tr = con.execute(f"select date, level v from read_parquet({ft!r},union_by_name=true) where index_name='Nifty 500' and return_variant='total_return'").df()
PR = pr.drop_duplicates("date", keep="last").assign(date=lambda d: pd.to_datetime(d.date)).set_index("date").v.sort_index()
TR = tr.drop_duplicates("date", keep="last").assign(date=lambda d: pd.to_datetime(d.date)).set_index("date").v.sort_index()
last_tr = TR.index.max()
for d in PR.index[PR.index > last_tr]:          # carry TRI past its last print using the price index
    TR.loc[d] = TR.loc[last_tr] * PR.loc[d] / PR.loc[last_tr]
TR = TR.sort_index()
def lvl(s, d): return s[s.index <= pd.Timestamp(d)].iloc[-1]

R = pd.read_csv(S + "post_listing_returns.csv"); R = R[R.horizon_date.notna()].copy()
V = pd.read_csv(OUT + "ipo_cohort_verified.csv")[["issue_id", "company_name", "listing_date"]]
B = pd.read_csv(OUT + "size_and_benchmark.csv")[["issue_id", "offer_close_date", "size_bucket"]]
R = R.merge(V, on="issue_id").merge(B, on="issue_id")
mb = R.board_type == "Main Board"
R["basis"] = np.where(mb, "total return vs Nifty 500 TRI", "price return vs Nifty 500 price index")
R["r_issue"] = np.where(mb, R.tr_from_issue, R.ret_from_issue)
R["r_listing"] = np.where(mb, R.tr_from_listing, R.ret_from_listing)
R["idx_listing"] = [(lvl(TR if m else PR, h) / lvl(TR if m else PR, l) - 1) * 100 for m, l, h in zip(mb, R.listing_date, R.horizon_date)]
R["idx_issue"] = [(lvl(TR if m else PR, h) / lvl(TR if m else PR, o) - 1) * 100 for m, o, h in zip(mb, R.offer_close_date, R.horizon_date)]
R["x_listing"] = R.r_listing - R.idx_listing
R["x_issue"] = R.r_issue - R.idx_issue
R["years"] = (pd.to_datetime(R.horizon_date) - pd.to_datetime(R.listing_date)).dt.days / 365.25
R.to_csv(OUT + "post_listing_returns.csv", index=False)

H = ["1m", "3m", "6m", "1y", "2y", "3y"]
def horizon_table(d):
    g = d.groupby("horizon")
    return pd.DataFrame({
        "n": g.size(), "median_from_issue_%": g.r_issue.median(), "median_from_listing_%": g.r_listing.median(),
        "p25_from_listing_%": g.r_listing.quantile(.25), "p75_from_listing_%": g.r_listing.quantile(.75),
        "below_issue_%": g.r_issue.apply(lambda s: (s < 0).mean() * 100),
        "below_listing_close_%": g.r_listing.apply(lambda s: (s < 0).mean() * 100),
        "median_vs_index_from_listing_pts": g.x_listing.median(), "beat_index_from_listing_%": g.x_listing.apply(lambda s: (s > 0).mean() * 100),
        "median_vs_index_from_issue_pts": g.x_issue.median(), "beat_index_from_issue_%": g.x_issue.apply(lambda s: (s > 0).mean() * 100),
        "stale_or_stopped": g.status.apply(lambda s: s.str.startswith("stale").sum())}).reindex(H).round(1)

def fixed_cohort(d, upto="2y"):
    ids = d[d.horizon == upto].issue_id
    f = d[d.issue_id.isin(ids) & d.horizon.isin(H[:H.index(upto) + 1])]
    g = f.groupby("horizon")
    return pd.DataFrame({"n": g.size(), "median_from_listing_%": g.r_listing.median(), "median_from_issue_%": g.r_issue.median(),
                         "median_vs_index_from_listing_pts": g.x_listing.median(),
                         "beat_index_from_listing_%": g.x_listing.apply(lambda s: (s > 0).mean() * 100)}).reindex(H[:H.index(upto) + 1]).round(1)

def vintage(d):
    t = d[(d.horizon == "to_date") & (d.years >= 1)].copy()
    ann = lambda r, y: ((1 + r / 100) ** (1 / y) - 1) * 100
    t["ann_from_listing"] = ann(t.r_listing, t.years); t["ann_index"] = ann(t.idx_listing, t.years)
    t["ann_from_issue"] = ann(t.r_issue, (pd.to_datetime(t.horizon_date) - pd.to_datetime(t.offer_close_date)).dt.days / 365.25)
    g = t.groupby("listing_year")
    return pd.DataFrame({"n": g.size(), "median_ann_from_issue_%": g.ann_from_issue.median(), "median_ann_from_listing_%": g.ann_from_listing.median(),
                         "index_ann_median_%": g.ann_index.median(), "median_ann_excess_pts": (g.ann_from_listing.median() - g.ann_index.median()),
                         "beat_index_since_listing_%": g.x_listing.apply(lambda s: (s > 0).mean() * 100),
                         "below_issue_today_%": g.r_issue.apply(lambda s: (s < 0).mean() * 100),
                         "stopped_trading": g.status.apply(lambda s: s.str.startswith("stale").sum())}).round(1)

for board, tag in [("Main Board", "mainboard"), ("SME Board", "sme")]:
    d = R[R.board_type == board]
    ht, fc, vt = horizon_table(d), fixed_cohort(d), vintage(d)
    ht.to_csv(OUT + f"post_listing_by_horizon_{tag}.csv"); fc.to_csv(OUT + f"post_listing_fixed_cohort_2y_{tag}.csv"); vt.to_csv(OUT + f"vintage_{tag}.csv")
    print(f"\n######## {board} ({d.basis.iloc[0]})"); print(ht.to_string()); print("\n-- fixed cohort (IPOs with 2 years of history)"); print(fc.to_string()); print("\n-- by listing year (listing to 28 Sep 2026, IPOs with >=1 year)"); print(vt.to_string())
