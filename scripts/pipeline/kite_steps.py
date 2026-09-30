"""Derive split/bonus events per IPO from Kite's adjusted daily candles vs raw exchange closes.

r_t = raw close / Kite adjusted close. Kite back-adjusts history for corporate actions, so r is
a step function; each step r_{t-1}/r_t is the factor of an event with ex-date t. Steps that snap
(within 1%) to a clean share ratio (n:1 split, a:b bonus with b<=10, or a product of two) are
share events; other steps are price-only adjustments (dividends/rights) and are ignored.
Output: kite_steps.csv (issue_id, ex_date, factor, snapped, kind, instrument).
"""
import csv, time
from fractions import Fraction
from pathlib import Path
import duckdb, numpy as np, pandas as pd, requests

S = Path(__file__).parent
ENV = Path("<SITE_REPO>/.env")
v = dict(l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l and not l.startswith("#"))
H = {"X-Kite-Version": "3", "Authorization": f"token {v['KITE_API_KEY'].strip()}:{v['KITE_ACCESS_TOKEN'].strip()}"}
V = pd.read_csv("<SITE_REPO>/analysis/ipo-2020-2026/verified/ipo_cohort_verified.csv")
W = pd.read_csv(S / "size_work5.csv")[["issue_id", "current_symbol"]]
V = V.merge(W, on="issue_id", how="left")

def load(ex):
    rows = [r for r in csv.DictReader(open(S / f"kite_inst_{ex}.csv")) if r["segment"] == ex and r["instrument_type"] == "EQ"]
    return {r["tradingsymbol"]: r["instrument_token"] for r in rows}, {r["exchange_token"]: r["instrument_token"] for r in rows}
NSE_SYM, _ = load("NSE"); BSE_SYM, BSE_CODE = load("BSE")

con = duckdb.connect()
files = [str(p) for p in (S / "panel").glob("*.parquet")]
P = con.execute(f"select cast(date as varchar) date, ex, symbol, code, close from read_parquet({files!r}, union_by_name=true)").df()
P["code"] = P.code.astype(str).str.replace(r"\.0$", "", regex=True)

CLEAN = sorted({float(Fraction(a + b, b)) for b in range(1, 11) for a in range(1, 101)} | {float(n) for n in range(2, 101)})
def snap(f):
    for c in CLEAN:
        if abs(f / c - 1) < 0.01:
            return c
    for c in CLEAN:
        if c < f:
            for c2 in CLEAN:
                if abs(f / (c * c2) - 1) < 0.01:
                    return c * c2
    return None

def candles(token, start):
    out, s = [], pd.Timestamp(start)
    while s <= pd.Timestamp("2026-09-28"):
        e = min(s + pd.Timedelta(days=1999), pd.Timestamp("2026-09-28"))
        for _ in range(4):
            r = requests.get(f"https://api.kite.trade/instruments/historical/{token}/day", headers=H,
                             params={"from": s.date().isoformat(), "to": e.date().isoformat()}, timeout=30)
            time.sleep(0.36)
            if r.status_code != 429:
                break
            time.sleep(2)
        if r.status_code == 200:
            out += r.json()["data"]["candles"]
        s = e + pd.Timedelta(days=1)
    return pd.DataFrame([(c[0][:10], c[4]) for c in out], columns=["date", "kclose"])

rows, meta = [], []
for i, r in enumerate(V.itertuples()):
    if r.price_exchange == "NSE":
        cur = r.current_symbol if isinstance(r.current_symbol, str) else r.nse_symbol
        tok = next((NSE_SYM[s] for s in [cur, f"{cur}-SM", f"{cur}-ST", f"{cur}-BE"] if isinstance(cur, str) and s in NSE_SYM), None)
        raw = P[(P.ex == "NSE") & (P.symbol.isin({r.nse_symbol, cur}))][["date", "close"]]
    else:
        code = str(r.bse_symbol).split(".")[0]
        if not code.isdigit():
            m = P[(P.ex == "BSE") & (P.date == r.listing_date) & (P.symbol == code)]
            code = m.code.iloc[0] if len(m) else ""
        tok = BSE_CODE.get(code)
        raw = P[(P.ex == "BSE") & (P.code == code)][["date", "close"]]
    if not tok:
        meta.append({"issue_id": r.issue_id, "kite": "no instrument"}); continue
    k = candles(tok, r.listing_date)
    j = raw.drop_duplicates("date").merge(k, on="date").sort_values("date")
    j = j[j.date >= r.listing_date]
    if len(j) < 2:
        meta.append({"issue_id": r.issue_id, "kite": "no overlap"}); continue
    j["r"] = j.close / j.kclose
    j["step"] = j.r.shift(1) / j.r
    n_ev = 0
    for e in j[(j.step - 1).abs() > 0.005].itertuples():
        sn = snap(e.step) if e.step > 1 else None
        rows.append({"issue_id": r.issue_id, "ex_date": e.date, "factor": round(e.step, 5), "snapped": sn,
                     "kind": "share event" if sn else "price-only (ignored)", "instrument": tok})
        n_ev += bool(sn)
    meta.append({"issue_id": r.issue_id, "kite": "ok", "overlap_days": len(j), "share_events": n_ev,
                 "r_first": round(j.r.iloc[0], 5), "r_last": round(j.r.iloc[-1], 5)})
    if i % 100 == 0:
        print(i, len(V), flush=True)
pd.DataFrame(rows).to_csv(S / "kite_steps.csv", index=False)
pd.DataFrame(meta).to_csv(S / "kite_steps_meta.csv", index=False)
print("done")
