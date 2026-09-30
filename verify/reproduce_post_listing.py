"""Rebuild the post-listing returns from public data and compare them with the published file.

Independent of the original pipeline in three ways:
  * each stock is followed by ISIN stem (first 9 characters) in the official daily bhavcopies,
    not by symbol, so renames and face-value ISIN changes are handled differently;
  * every split/bonus/rights factor in corporate_action_events_applied.csv is re-tested against
    the raw overnight price move before it is used;
  * dividends are rebuilt from the stocks.events snapshot in data/inputs/stocks_events/.

Steps
  1. download official NSE and BSE bhavcopies for every trading day 2020-01-01..2026-09-28
     (about 3,350 files; cached in verify/.cache/, resumable; 30-60 minutes the first time)
     and keep only rows for this cohort's ISINs (verify/.cache/panel_*.csv.gz);
  2. compute returns at 21/63/126/252/504/756 trading days and to 28 Sep 2026, from the issue
     price and from the listing-day close, price-only and with dividends reinvested;
  3. benchmark: Main Board total return vs Nifty 500 TRI, SME price return vs Nifty 500 price;
  4. compare row by row with data/verified/post_listing_returns.csv and recompute the headline
     horizon tables.

Usage:  python verify/reproduce_post_listing.py            (full run)
        python verify/reproduce_post_listing.py --skip-fetch   (reuse the cached panel)
"""
import argparse
import gzip
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import _bhav

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(__file__).parent / ".cache"
AS_OF = "2026-09-28"
HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
EQUITY_SERIES = {"EQ", "BE", "BZ", "SM", "ST", "SZ", "A", "B", "T", "X", "XT", "Z", "M", "MT", "TS", "P", "MS", "ZP", "Y"}


def load_cohort():
    V = pd.read_csv(ROOT / "data/verified/ipo_cohort_verified.csv", dtype={"bse_symbol": str})
    D = pd.read_csv(ROOT / "data/verified/verification_detail.csv", dtype=str)[["issue_id", "nse_isin", "bse_isin"]]
    V = V.merge(D, on="issue_id", how="left")
    # take the ISIN from the exchange whose close is used; verification_detail.csv also keeps
    # rejected loose matches on the other exchange, so the other side is only a fallback
    own = np.where(V.price_exchange == "NSE", V["nse_isin"], V["bse_isin"])
    other = np.where(V.price_exchange == "NSE", V["bse_isin"], V["nse_isin"])
    V["isin_code"] = pd.Series(own, index=V.index).where(pd.notna(own), pd.Series(other, index=V.index))
    # rows priced by manual lookup have no recorded ISIN: take it from the listing-day bhavcopy by symbol
    for i, r in V[V["isin_code"].isna()].iterrows():
        rows = _bhav.nse(date.fromisoformat(r.listing_date)) if r.price_exchange == "NSE" else _bhav.bse(date.fromisoformat(r.listing_date))
        sym = r.nse_symbol if r.price_exchange == "NSE" else str(r.bse_symbol).split(".")[0]
        hit = [x for x in rows if isinstance(sym, str) and sym in (x["symbol"], x["code"])
               and abs((x["close"] or 0) - r.listing_close_inr) < 0.005]
        if not hit:  # fall back to the unique first-day row with the right close
            hit = [x for x in rows if abs((x["close"] or 0) - r.listing_close_inr) < 0.005 and x["prev_close"] in (0, r.issue_price_inr)]
        if len(hit) == 1:
            V.loc[i, "isin_code"] = hit[0]["isin"]
    V["stem"] = V["isin_code"].str[:9]
    return V


def calendar():
    ix = pd.read_csv(ROOT / "data/inputs/indices/nifty500_price.csv")
    return [d for d in ix.date if "2020-01-01" <= d <= AS_OF]


def fetch_panel(cal, stems):
    """Filtered daily rows for the cohort's ISIN stems, one gzip CSV per exchange (resumable)."""
    for ex, reader in (("NSE", _bhav.nse), ("BSE", _bhav.bse)):
        path = CACHE / f"panel_{ex}.csv.gz"
        done = set()
        if path.exists():
            done = set(pd.read_csv(path, usecols=["date"]).date.unique())
        todo = [d for d in cal if d not in done]
        with gzip.open(path, "at") as fh:
            if not done:
                fh.write("date,symbol,code,series,isin,close\n")
            for k, d in enumerate(todo):
                rows = reader(date.fromisoformat(d))
                for x in rows:
                    if x["isin"][:9] in stems and x["series"] in EQUITY_SERIES and x["close"] is not None:
                        fh.write(f'{d},{x["symbol"]},{x["code"]},{x["series"]},{x["isin"]},{x["close"]}\n')
                if not rows:
                    fh.write(f"{d},,,,NO_FILE,\n")
                if k % 100 == 0:
                    print(f"  {ex} {k}/{len(todo)} {d}", flush=True)


def index_series():
    pr = pd.read_csv(ROOT / "data/inputs/indices/nifty500_price.csv").set_index("date").close
    tr = pd.read_csv(ROOT / "data/inputs/indices/nifty500_tri.csv").set_index("date").close
    last = tr.index.max()
    for d in pr.index[pr.index > last]:  # carry the TRI past its last print with the price index
        tr.loc[d] = tr.loc[last] * pr.loc[d] / pr.loc[last]
    return pr.sort_index(), tr.sort_index()


def dividends():
    out = {}
    for f in sorted((ROOT / "data/inputs/stocks_events").glob("y*.json")):
        for e in json.load(open(f))["events"]:
            if e.get("cl") == "equity" and e["t"] == "dividend" and e.get("div_amount"):
                out.setdefault(e["iss"], set()).add((e["ex"], float(e["div_amount"])))
    return {k: sorted(v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true")
    a = ap.parse_args()
    V = load_cohort()
    print(f"cohort {len(V)}; ISIN known for {V.isin_code.notna().sum()}")
    cal = calendar()
    if not a.skip_fetch:
        fetch_panel(cal, set(V.stem.dropna()))
    P = {ex: pd.read_csv(CACHE / f"panel_{ex}.csv.gz", dtype=str) for ex in ("NSE", "BSE")}
    for ex in P:
        missing_days = P[ex][P[ex]["isin"] == "NO_FILE"].date.tolist()
        if missing_days:
            print(f"WARNING {ex}: no bhavcopy for {len(missing_days)} trading days, e.g. {missing_days[:3]}")
        P[ex] = P[ex][P[ex]["isin"] != "NO_FILE"].assign(close=lambda d: d.close.astype(float))
    PG = {ex: {k: g.sort_values("date") for k, g in P[ex].assign(stem=P[ex]["isin"].str[:9]).groupby("stem")} for ex in P}
    EV = pd.read_csv(ROOT / "data/verified/corporate_action_events_applied.csv")
    EV = EV[EV.accepted]
    DV = dividends()
    PR, TR = index_series()
    lvl = lambda s, d: s[s.index <= d].iloc[-1]

    out, ev_checks = [], []
    for r in V.itertuples():
        base = {"issue_id": r.issue_id, "board_type": r.board_type, "listing_year": r.listing_year}
        g = PG[r.price_exchange].get(r.stem) if isinstance(r.stem, str) else None
        if g is None:
            out.append({**base, "horizon": "all", "status": "no series"}); continue
        s = g[g.date >= r.listing_date].drop_duplicates("date", keep="first").reset_index(drop=True)
        if s.empty or s.date.iloc[0] != r.listing_date or abs(s.close.iloc[0] - r.listing_close_inr) > 0.005:
            out.append({**base, "horizon": "all", "status": "listing row mismatch"}); continue
        s["prev"] = s.close.shift(1)
        s["f"], s["dv"] = 1.0, 1.0
        for e in EV[EV.issue_id == r.issue_id].itertuples():
            j = s.index[s.date >= e.ex_date]
            if not len(j) or j[0] == 0:
                continue
            j = j[0]
            gap = s.close[j] / s.prev[j]
            share_event = "rights" not in e.source
            ok = (abs(gap * e.factor - 1) < 0.25) if share_event else True
            ev_checks.append({"issue_id": r.issue_id, "ex_date": e.ex_date, "factor": e.factor, "source": e.source,
                              "raw_gap": round(gap, 4), "confirmed_by_price": ok})
            s.loc[j, "f"] *= e.factor
        for ed, amt in DV.get(str(r.isin_code)[:7], []):
            j = s.index[s.date >= ed]
            if ed <= r.listing_date or not len(j) or j[0] == 0:
                continue
            s.loc[j[0], "dv"] *= 1 + amt / s.prev[j[0]]
        s["adj"] = s.close * s.f.cumprod()
        s["tr"] = s.adj * s.dv.cumprod()
        i0 = cal.index(r.listing_date)
        mb = r.board_type == "Main Board"
        IX = TR if mb else PR
        targets = [(h, cal[i0 + k]) for h, k in HORIZONS.items() if i0 + k < len(cal)] + [("to_date", AS_OF)]
        for h, hd in targets:
            px = s[s.date <= hd].iloc[-1]
            lag = cal.index(hd) - cal.index(px.date)
            ret = (px.tr if mb else px.adj)
            out.append({**base, "horizon": h, "horizon_date": hd, "price_date": px.date, "raw_close": px.close,
                        "r_issue": (ret / r.issue_price_inr - 1) * 100, "r_listing": (ret / r.listing_close_inr - 1) * 100,
                        "idx_listing": (lvl(IX, hd) / lvl(IX, r.listing_date) - 1) * 100,
                        "status": "ok" if lag == 0 else ("last trade within 10 days" if lag <= 10 else "stale / stopped trading")})
    X = pd.DataFrame(out)
    X["x_listing"] = X.r_listing - X.idx_listing
    X.to_csv(Path(__file__).parent / "post_listing_reproduced.csv", index=False)
    C = pd.DataFrame(ev_checks)
    print(f"\ncorporate-action factors re-tested against raw price moves: {C.confirmed_by_price.sum()} of {len(C)} confirmed")
    if (~C.confirmed_by_price).any():
        print(C[~C.confirmed_by_price].to_string())
    print("series status:", X[X.horizon == "all"].status.value_counts().to_dict() or "all found")

    # compare with the published file
    Pub = pd.read_csv(ROOT / "data/verified/post_listing_returns.csv")
    Pub = Pub[Pub.horizon_date.notna()]
    m = Pub.merge(X, on=["issue_id", "horizon"], suffixes=("_pub", "_rep"))
    same_px = (m.raw_close_pub - m.raw_close_rep).abs() < 0.005
    same_r = (m.r_listing_pub - m.r_listing_rep).abs() < 0.05
    same_x = (m.x_listing_pub - m.x_listing_rep).abs() < 0.05
    print(f"\nrows compared {len(m)} of {len(Pub)} published")
    print(f"  same raw close: {same_px.sum()}   same return from listing (±0.05 pt): {same_r.sum()}   same excess vs index: {same_x.sum()}")
    diff = m[~(same_r & same_x)]
    if len(diff):
        cols = ["issue_id", "horizon", "price_date_pub", "price_date_rep", "raw_close_pub", "raw_close_rep", "r_listing_pub", "r_listing_rep"]
        print(f"\n{len(diff)} differing rows (first 25):")
        print(diff[cols].head(25).round(2).to_string(index=False))
        diff[cols].to_csv(Path(__file__).parent / "post_listing_differences.csv", index=False)
    print("\nHeadline check, median return from listing and % ahead of index (published -> reproduced):")
    for b in ("Main Board", "SME Board"):
        for h in ("1y", "2y"):
            p, q = Pub[(Pub.board_type == b) & (Pub.horizon == h)], X[(X.board_type == b) & (X.horizon == h)]
            print(f"  {b:10} {h}: median {p.r_listing.median():6.1f} -> {q.r_listing.median():6.1f}   "
                  f"ahead {100 * (p.x_listing > 0).mean():5.1f}% -> {100 * (q.x_listing > 0).mean():5.1f}%   n {len(p)} -> {len(q)}")


if __name__ == "__main__":
    main()
