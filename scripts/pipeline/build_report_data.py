"""Assemble every number the report shows into report_data.json (from verified/ outputs only)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
import numpy as np, pandas as pd
D = str(ROOT / "data/verified") + "/"
V = pd.read_csv(D + "ipo_cohort_verified.csv")
B = pd.read_csv(D + "size_and_benchmark.csv")
R = pd.read_csv(D + "post_listing_returns.csv")
X = V.merge(B, on="issue_id", how="left")
X["open_ret"] = (X.listing_open_inr / X.issue_price_inr - 1) * 100
X["board"] = X.board_type.map({"Main Board": "main", "SME Board": "sme"})
q = lambda s, p: float(np.nanpercentile(s, p)) if len(s) else None
r1 = lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 1)
out = {"as_of": "2026-09-28", "counts": {}, "listing": {}, "listing_overall": {}, "hist": {}, "open_close": {},
       "size": [], "horizon": {}, "cohort": {}, "vintage": {}, "excess_hist": {}, "ipos": []}
YEARS = list(range(2020, 2027))
for b in ["main", "sme"]:
    d = X[X.board == b]
    out["counts"][b] = [int((d.listing_year == y).sum()) for y in YEARS]
    rows = []
    for y in YEARS:
        s = d[d.listing_year == y].return_pct
        rows.append({"year": y, "n": int(len(s)), "median": r1(s.median()), "p25": r1(q(s, 25)), "p75": r1(q(s, 75)),
                     "above": r1((s > 0).mean() * 100), "flat": r1((s == 0).mean() * 100), "below": r1((s < 0).mean() * 100),
                     "big": r1((s > 50).mean() * 100), "adj_median": r1(d[d.listing_year == y].excess_nifty500_pct.median()),
                     "b_down": r1((s <= 0).mean() * 100), "b_0_15": r1(((s > 0) & (s <= 15)).mean() * 100), "b_15p": r1((s > 15).mean() * 100)})
    out["listing"][b] = rows
    s = d.return_pct
    out["listing_overall"][b] = {"n": int(len(s)), "median": r1(s.median()), "mean": r1(s.mean()), "above": r1((s > 0).mean() * 100),
                                 "b_down": r1((s <= 0).mean() * 100), "b_0_15": r1(((s > 0) & (s <= 15)).mean() * 100),
                                 "b_15p": r1((s > 15).mean() * 100), "b_50p": r1((s > 50).mean() * 100), "b_100p": r1((s > 100).mean() * 100),
                                 "adj_median": r1(d.excess_nifty500_pct.median()), "median_window_index": r1(d.nifty500_pct.median())}
    edges = list(range(-50, 170, 10))
    cl = s.clip(-49.99, 159.99)
    out["hist"][b] = [{"lo": e, "hi": e + 10, "n": int(((cl >= e) & (cl < e + 10)).sum())} for e in edges[:-1]]
    oc = []
    for y in YEARS:
        e = d[d.listing_year == y]
        oc.append({"year": y, "open_median": r1(e.open_ret.median()), "close_median": r1(e.return_pct.median()),
                   "close_below_open": r1((e.listing_close_inr < e.listing_open_inr).mean() * 100)})
    out["open_close"][b] = {"by_year": oc, "all": {"open_median": r1(d.open_ret.median()), "close_median": r1(d.return_pct.median()),
                            "close_below_open": r1((d.listing_close_inr < d.listing_open_inr).mean() * 100),
                            "n_open": int(d.open_ret.notna().sum())}}

R["board"] = R.board_type.map({"Main Board": "main", "SME Board": "sme"})
H = ["1m", "3m", "6m", "1y", "2y", "3y"]
for b in ["main", "sme"]:
    d = R[(R.board == b) & R.horizon.isin(H)]
    out["horizon"][b] = [{"h": h, "n": int(len(g)), "med_issue": r1(g.r_issue.median()), "med_listing": r1(g.r_listing.median()),
                          "p25": r1(q(g.r_listing, 25)), "p75": r1(q(g.r_listing, 75)),
                          "below_issue": r1((g.r_issue < 0).mean() * 100), "below_listing": r1((g.r_listing < 0).mean() * 100),
                          "beat_listing": r1((g.x_listing > 0).mean() * 100), "beat_issue": r1((g.x_issue > 0).mean() * 100),
                          "med_x_listing": r1(g.x_listing.median()), "stale": int(g.status.str.startswith("stale").sum())}
                         for h in H for g in [d[d.horizon == h]]]
    ids = d[d.horizon == "2y"].issue_id
    f = d[d.issue_id.isin(ids) & d.horizon.isin(H[:5])]
    out["cohort"][b] = [{"h": h, "n": int(len(g)), "med": r1(g.r_listing.median()), "p25": r1(q(g.r_listing, 25)), "p75": r1(q(g.r_listing, 75)),
                         "idx_med": r1(g.idx_listing.median()), "med_issue": r1(g.r_issue.median()), "beat": r1((g.x_listing > 0).mean() * 100)}
                        for h in H[:5] for g in [f[f.horizon == h]]]
    t = R[(R.board == b) & (R.horizon == "to_date")].copy()
    t = t.merge(V[["issue_id", "listing_date"]].rename(columns={"listing_date": "ld"}), on="issue_id")
    t["yrs"] = (pd.to_datetime("2026-09-28") - pd.to_datetime(t.ld)).dt.days / 365.25
    ann = lambda r, y: ((1 + r / 100) ** (1 / y) - 1) * 100
    t["ann"] = ann(t.r_listing, t.yrs); t["ann_idx"] = ann(t.idx_listing, t.yrs); t["ann_x"] = t.ann - t.ann_idx
    v = []
    for y in range(2020, 2026):
        g = t[(t.listing_year == y) & (t.yrs >= 1)]
        v.append({"year": y, "n": int(len(g)), "ann_med": r1(g.ann.median()), "ann_p25": r1(q(g.ann, 25)), "ann_p75": r1(q(g.ann, 75)),
                  "ann_idx_med": r1(g.ann_idx.median()), "ann_x_med": r1(g.ann_x.median()),
                  "beat": r1((g.x_listing > 0).mean() * 100), "below_issue": r1((g.r_issue < 0).mean() * 100),
                  "stopped": int(g.status.str.startswith("stale").sum())})
    out["vintage"][b] = v
    g = t[t.yrs >= 1]
    cx = g.ann_x.clip(-60, 79.99)
    out["excess_hist"][b] = {"bins": [{"lo": e, "hi": e + 10, "n": int(((cx >= e) & (cx < e + 10)).sum())} for e in range(-60, 80, 10)],
                             "n": int(len(g)), "beat": r1((g.x_listing > 0).mean() * 100), "median": r1(g.ann_x.median())}

# Main Board by size, with 1-year outcome
mb = X[X.board == "main"]
r1y = R[(R.board == "main") & (R.horizon == "1y")].set_index("issue_id")
for s_ in ["Large", "Mid", "Small", "Micro"]:
    g = mb[mb.size_bucket == s_]
    y = r1y.reindex(g.issue_id).dropna(subset=["r_listing"])
    out["size"].append({"bucket": s_, "n": int(len(g)), "mcap_med": round(float(g.mcap_issue_cr.median())), "listing_med": r1(g.return_pct.median()),
                        "above": r1((g.return_pct > 0).mean() * 100), "n_1y": int(len(y)), "med_1y_listing": r1(y.r_listing.median()),
                        "beat_1y": r1((y.x_listing > 0).mean() * 100)})

# per-IPO table
piv = R[R.horizon.isin(["1y", "to_date"])].pivot_table(index="issue_id", columns="horizon", values=["r_listing", "x_listing"])
piv.columns = [f"{a}_{b}" for a, b in piv.columns]
T = X.merge(piv, left_on="issue_id", right_index=True, how="left")
for r in T.sort_values("listing_date").itertuples():
    out["ipos"].append({"n": r.company_name.replace(" Limited", "").replace(" Ltd", ""), "b": r.board, "d": r.listing_date, "y": int(r.listing_year),
                        "ip": r.issue_price_inr, "lr": r1(r.return_pct), "sz": r.size_bucket if r.board == "main" and pd.notna(r.size_bucket) else None,
                        "r1": r1(getattr(r, "r_listing_1y", np.nan)), "x1": r1(getattr(r, "x_listing_1y", np.nan)),
                        "rt": r1(getattr(r, "r_listing_to_date", np.nan)), "xt": r1(getattr(r, "x_listing_to_date", np.nan))})
meta = json.load(open(D + "update_manifest.json"))
out["listing_as_of"] = meta["listing_as_of"]
out["post_listing_as_of"] = meta["post_listing_as_of"]
out["coverage"] = {"listing": len(V), "benchmark": len(B), "size": int(B.size_bucket.notna().sum()), "post_listing_ipos": int(R.issue_id.nunique())}
for key in ["main", "sme"]:
    out["listing_overall"][key]["n_benchmark"] = int(X.loc[X.board == key, "nifty500_pct"].notna().sum())
json.dump(out, open(D + "report_data.json", "w"), indent=1, allow_nan=False)
template = (ROOT / "report/ipo_report.template.html").read_text()
(ROOT / "report/ipo-performance.html").write_text(template.replace("__DATA__", json.dumps(out, separators=(",", ":"), allow_nan=False)))
print(json.dumps({k: out[k] for k in ["counts", "listing_overall", "size"]}, indent=0)[:2500])
print(json.dumps(out["open_close"])[:800]); print(json.dumps(out["cohort"])[:900]); print(json.dumps(out["vintage"])[:1400]); print(json.dumps(out["excess_hist"]["main"])[:500])
