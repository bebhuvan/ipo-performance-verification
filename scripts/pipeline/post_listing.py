"""Post-listing returns for the verified IPO cohort from raw exchange closes.

For each IPO, follow its security on the exchange whose listing close we use:
  NSE: by symbol (following NSE symbol changes), any equity/SME series;
  BSE: by scrip code (persistent through renames and splits).
Corporate-action adjustment comes from the exchange itself: on an ex-date the bhavcopy's
previous-close is adjusted, so the day's factor = last actual close / published prev close.
Cumulative factor since listing converts later raw closes to the listing-day share basis.

Horizons are counted in the stock's own trading days on that exchange calendar (the
exchange trading calendar, not the stock's traded days). A horizon price is the close on the
horizon day, or the last trade within 10 trading days before it (else 'stale').
If the security stops appearing, the last traded price is used and the IPO is flagged.
Outputs: post_listing_returns.csv (one row per IPO x horizon) and adj_events.csv.
"""
import glob
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

S = Path(__file__).parent
V = pd.read_csv("/home/bhuvanesh.r/Documents/Bhuvan projects/IPO/analysis/ipo-2020-2026/verified/ipo_cohort_verified.csv")
DET = pd.read_csv(S / "verification_merged.csv")[["issue_id", "bse_symbol", "bse_isin", "nse_isin"]]
V = V.merge(DET, on="issue_id", how="left", suffixes=("", "_det"))
# IPOs priced by manual lookup carry no symbol in the verified file: take the listing-day identifiers
MANUAL_IDS = {"bombay-metrics-supply-chain-6ab5d0": ("BMETRICS", None), "s-v-j-enterprises-8a0d89": (None, "543799"),
              "vishnusurya-projects-infra-0f1853": ("VISHNUINFR", None), "akanksha-power-infrastructure-a1a57e": ("AKANKSHA", None),
              "excellent-wires-packaging-518ddd": ("EXCELLENT", None)}
for iid, (nsym, bcode) in MANUAL_IDS.items():
    m = V.issue_id == iid
    assert m.sum() == 1, iid
    if nsym: V.loc[m, "nse_symbol"] = nsym
    if bcode: V.loc[m, "bse_symbol"] = bcode
HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
AS_OF = "2026-09-28"

con = duckdb.connect()
files = [str(p) for p in (S / "panel").glob("*.parquet")]
P = con.execute(f"select date, ex, symbol, code, series, isin, close, prev from read_parquet({files!r}, union_by_name=true)").df()
P["date"] = P.date.astype(str)
P["code"] = P.code.astype(str).str.replace(r"\.0$", "", regex=True)
cal = {ex: sorted(P[P.ex == ex].date.unique()) for ex in ("NSE", "BSE")}
NSE_G = {k: g.sort_values("date") for k, g in P[P.ex == "NSE"].groupby("symbol")}
_n = P[P.ex == "NSE"].assign(stem=P["isin"].fillna("").str[:9])
NSE_ISIN = {k: g.sort_values("date") for k, g in _n[_n.stem != ""].groupby("stem")}
BSE = P[P.ex == "BSE"].copy()
BSE_G = {k: g.sort_values("date") for k, g in BSE.groupby("code")}

sc = pd.read_csv(S / "symbolchange.csv", header=None, names=["n", "old", "new", "d"], skipinitialspace=True)
sc = sc.assign(old=sc.old.str.strip(), new=sc.new.str.strip(),
               d=pd.to_datetime(sc.d.str.strip(), format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d"))


from fractions import Fraction
SIMPLE = sorted({float(n) for n in range(2, 101)} | {float(Fraction(a + b, b)) for a in range(1, 11) for b in range(1, 11)})
SIMPLE2 = sorted(set(SIMPLE) | {x * y for x in SIMPLE for y in SIMPLE if x * y <= 100})


def resnap(f):
    """Nearest simple split/bonus ratio (or product of two) within 1.5%; else None."""
    best = min(SIMPLE2, key=lambda c: abs(f / c - 1))
    return best if abs(f / best - 1) < 0.015 else None


def load_stocks_events():
    """Official NSE+BSE corporate actions (stocks.events year files), keyed by 7-char ISIN issuer stem."""
    import json, re
    ev = []
    for y in range(2020, 2027):
        ev += json.load(open(S / f"se/y{y}.json"))["events"]
    SB, RT, DV = {}, {}, {}
    for e in ev:
        if e.get("cl") != "equity":
            continue
        k = e["iss"]
        if e["t"] in ("split", "bonus", "consolidation") and e.get("adj_factor"):
            SB.setdefault(k, []).append((e["ex"], round(1 / e["adj_factor"], 6), "stocks.events " + e["t"]))
        elif e["t"] == "rights":
            m = re.match(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*at\s*Rs\.?\s*([\d.]+)", e.get("d", ""), re.I)
            if m:
                RT.setdefault(k, []).append((e["ex"], float(m.group(1)), float(m.group(2)), float(m.group(3))))
        elif e["t"] == "dividend" and e.get("div_amount"):
            DV.setdefault(k, []).append((e["ex"], float(e["div_amount"])))
    for d in (SB, RT, DV):
        for k in d:
            d[k] = sorted(set(d[k]))
    return SB, RT, DV


SE_SB, SE_RT, SE_DV = load_stocks_events()


def build_events():
    """Union of Kite share steps and NSE split/bonus lists, de-duplicated within 5 days."""
    ev = {}
    K = pd.read_csv(S / "kite_steps.csv")
    for e in K[K.factor > 1.02].itertuples():
        sn = resnap(e.factor)
        if sn:
            ev.setdefault(e.issue_id, []).append((e.ex_date, sn, "kite"))
    C = pd.read_csv(S / "corp_actions_adjustment/corp_actions.csv")
    CA = pd.read_csv(S / "corp_actions.csv")
    W = pd.read_csv(S / "size_work5.csv")[["issue_id", "current_symbol", "listing_date"]]
    for w in W.itertuples():
        cand = [(e.ex_date, round(1 / e.ratio, 4), "calendar") for e in C[(C.symbol == w.current_symbol) & (C.ex_date > w.listing_date)].itertuples()]
        cand += [(e.exDate, round(1 / e.adjustmentFactor, 4), "nse_mcp") for e in
                 CA[(CA.issue_id == w.issue_id) & CA.actionType.isin(["SPLIT", "BONUS"]) & (CA.exDate > w.listing_date)].itertuples()]
        for d, f, src in cand:
            have = ev.setdefault(w.issue_id, [])
            if not any(abs((pd.Timestamp(d) - pd.Timestamp(x[0])).days) <= 5 for x in have):
                have.append((d, f, src))
    return ev


def nse_series(sym, start):
    """Concatenate daily rows for sym and its later renamed symbols from start."""
    parts, cur, since, seen = [], sym, start, set()
    while cur and cur not in seen:
        seen.add(cur)
        ch = sc[(sc.old == cur) & (sc.d > since)].sort_values("d")
        until = ch.d.iloc[0] if len(ch) else "9999"
        if cur in NSE_G:
            rows = NSE_G[cur]
            parts.append(rows[(rows.date >= since) & (rows.date < until)])
        if not len(ch):
            break
        cur, since = ch.new.iloc[0], ch.d.iloc[0]
    if not parts:
        return pd.DataFrame(columns=["date", "close", "prev", "series", "isin"])
    d = pd.concat(parts).sort_values("date").drop_duplicates("date", keep="last")
    # renames missing from NSE's symbol-change file: continue under the same ISIN stem (first 9
    # characters survive face-value-change ISIN rolls) when this symbol's history ends early
    for _ in range(3):
        last = d.date.iloc[-1]
        if last >= "2026-09-01":
            break
        stem = str(d["isin"].iloc[-1])[:9]
        nxt = NSE_ISIN.get(stem)
        if nxt is None:
            break
        nxt = nxt[(nxt.date > last) & (nxt.symbol != d.symbol.iloc[-1])]
        if nxt.empty:
            break
        new_sym = nxt.symbol.iloc[0]
        cont = NSE_G[new_sym]
        d = pd.concat([d, cont[cont.date > last]]).sort_values("date").drop_duplicates("date", keep="last")
    return d[["date", "close", "prev", "series", "isin"]].reset_index(drop=True)


def bse_series(code, start):
    if code not in BSE_G:
        return pd.DataFrame(columns=["date", "close", "prev", "series", "isin"])
    d = BSE_G[code]
    d = d[d.date >= start].sort_values("date").drop_duplicates("date", keep="last")
    return d[["date", "close", "prev", "series", "isin"]].reset_index(drop=True)


out, events = [], []
EVENTS = build_events()
for r in V.itertuples():
    ex = r.price_exchange
    if ex == "NSE":
        sym = r.nse_symbol if isinstance(r.nse_symbol, str) else None
        s = nse_series(sym, r.listing_date) if sym else pd.DataFrame()
    else:
        code = str(r.bse_symbol).split(".")[0] if isinstance(r.bse_symbol, (str, float)) and str(r.bse_symbol) != "nan" else None
        if code and not code.isdigit():  # new-format ticker: look up its scrip code on the listing date
            m = BSE[(BSE.date == r.listing_date) & (BSE.symbol == code)]
            code = m.code.iloc[0] if len(m) else None
        s = bse_series(code, r.listing_date) if code else pd.DataFrame()
    base = {"issue_id": r.issue_id, "board_type": r.board_type, "listing_year": r.listing_year, "price_exchange": ex,
            "issue_price": r.issue_price_inr, "listing_close": r.listing_close_inr}
    if s.empty or s.date.iloc[0] != r.listing_date or abs(s.close.iloc[0] - r.listing_close_inr) > 0.005:
        out.append({**base, "horizon": "all", "status": "series not found or listing row mismatch"})
        continue
    # Corporate actions. Share events (split/bonus/consolidation) come from stocks.events (official
    # exchange files) plus Kite share steps; each candidate must match the raw overnight price move
    # (adjusted move within 25%), and where sources disagree the ratio closest to the raw move wins.
    # Rights issues use the theoretical ex-rights price from the official terms. Dividends are
    # reinvested at the previous close (total-return factor), kept separate from the price factor.
    s = s.reset_index(drop=True)
    s["raw_prev"] = s.close.shift(1)
    s["f"] = 1.0
    s["dv"] = 1.0
    iss = str(s["isin"].iloc[0])[:7]
    rights_dates = [pd.Timestamp(ed) for ed, *_ in SE_RT.get(iss, []) if ed > r.listing_date]
    cands = {}
    se_by_date = {}
    for ed, f, src in SE_SB.get(iss, []):
        if ed > r.listing_date:
            se_by_date.setdefault(ed, []).append((f, src))
    for ed, lst in se_by_date.items():
        opts = list(lst)
        types = {x[1] for x in lst}
        if len(types) > 1:                             # split and bonus on the same ex-date
            opts.append((float(np.prod([x[0] for x in lst])), "stocks.events " + "+".join(sorted(t.split()[-1] for t in types))))
        cands[ed] = opts
    for ed, f, src in EVENTS.get(r.issue_id, []):
        if any(abs((pd.Timestamp(ed) - d).days) <= 5 for d in rights_dates):
            continue                                   # a rights issue explains this Kite step
        near = [d for d in cands if abs((pd.Timestamp(d) - pd.Timestamp(ed)).days) <= 5]
        cands.setdefault(near[0] if near else ed, []).append((f, src))
    applied = {}                                       # row -> factors already applied there
    for ed, opts in sorted(cands.items()):
        # the recorded date can be a record/announcement date: test trading days from 3 before to 5 after
        idx = s.index[s.date >= ed]
        if not len(idx):
            continue
        j0 = idx[0]
        best = None
        for j in range(max(1, j0 - 3), min(len(s), j0 + 6)):
            gap = s.close[j] / s.raw_prev[j]
            for f, src in opts:
                err = abs(gap * f - 1)
                if best is None or err < best[0]:
                    best = (err, j, f, src, gap)
        if best is None:
            continue
        err, j, f, src, gap = best
        if any(abs(f / g - 1) < 0.02 for g in applied.get(j, [])):
            continue                                   # same event recorded twice by different sources
        ok = err < 0.25
        events.append({"issue_id": r.issue_id, "ex_date": s.date[j], "recorded_date": ed, "factor": f, "source": src,
                       "alternatives": "; ".join(f"{o[1]}={o[0]:g}" for o in opts), "raw_gap": round(gap, 4), "accepted": ok})
        if ok:
            s.loc[j, "f"] = s.f[j] * f
            applied.setdefault(j, []).append(f)
    for ed, a, b, px in SE_RT.get(iss, []):
        hit = s.index[s.date >= ed]
        if ed <= r.listing_date or not len(hit) or hit[0] == 0:
            continue
        j = hit[0]
        cum = s.raw_prev[j]
        if px < cum:                                   # in-the-money rights carry value
            terp = (cum * b + px * a) / (a + b)
            s.loc[j, "f"] = s.f[j] * cum / terp
            events.append({"issue_id": r.issue_id, "ex_date": s.date[j], "factor": round(cum / terp, 5),
                           "source": f"stocks.events rights {a:g}:{b:g} at {px:g}", "raw_gap": round(s.close[j] / cum, 4), "accepted": True})
    for ed, amt in SE_DV.get(iss, []):
        hit = s.index[s.date >= ed]
        if ed <= r.listing_date or not len(hit) or hit[0] == 0:
            continue
        j = hit[0]
        s.loc[j, "dv"] = s.dv[j] * (1 + amt / s.raw_prev[j])
    s["cum"] = s.f.cumprod()               # price factor: shares/entitlements per listing-day share
    s["trf"] = s.dv.cumprod()              # dividend reinvestment factor
    s["adj_close"] = s.close * s.cum       # value of one listing-day share (price only)
    s["tr_close"] = s.adj_close * s.trf    # with dividends reinvested
    c = cal[ex]
    i0 = c.index(r.listing_date)
    last_trade = s.date.iloc[-1]
    for h, k in HORIZONS.items():
        rec = {**base, "horizon": h}
        if i0 + k >= len(c) or c[i0 + k] > AS_OF:
            rec["status"] = "not reached"
            out.append(rec)
            continue
        hd = c[i0 + k]
        upto = s[s.date <= hd]
        px = upto.iloc[-1]
        lag = c.index(hd) - c.index(px.date) if px.date in c else None
        status = "ok" if lag == 0 else ("last trade within 10 days" if lag is not None and lag <= 10 else "stale / stopped trading")
        rec.update(horizon_date=hd, price_date=px.date, raw_close=px.close, cum_factor=px.cum, adj_close=px.adj_close,
                   tr_factor=px.trf, tr_from_issue=(px.tr_close / r.issue_price_inr - 1) * 100,
                   tr_from_listing=(px.tr_close / r.listing_close_inr - 1) * 100,
                   ret_from_issue=(px.adj_close / r.issue_price_inr - 1) * 100,
                   ret_from_listing=(px.adj_close / r.listing_close_inr - 1) * 100,
                   status=status, last_trade_date=last_trade)
        out.append(rec)

    # listing to date (last trade on or before the as-of date)
    upto = s[s.date <= AS_OF]; px = upto.iloc[-1]
    lag = c.index(c[-1] if c[-1] <= AS_OF else AS_OF) - c.index(px.date) if px.date in c else None
    out.append({**base, "horizon": "to_date", "horizon_date": AS_OF, "price_date": px.date, "raw_close": px.close,
                "cum_factor": px.cum, "adj_close": px.adj_close, "tr_factor": px.trf,
                "ret_from_issue": (px.adj_close / r.issue_price_inr - 1) * 100, "ret_from_listing": (px.adj_close / r.listing_close_inr - 1) * 100,
                "tr_from_issue": (px.tr_close / r.issue_price_inr - 1) * 100, "tr_from_listing": (px.tr_close / r.listing_close_inr - 1) * 100,
                "status": "ok" if lag == 0 else ("last trade within 10 days" if lag is not None and lag <= 10 else "stale / stopped trading"),
                "last_trade_date": px.date})

R = pd.DataFrame(out)
R.to_csv(S / "post_listing_returns.csv", index=False)
pd.DataFrame(events).to_csv(S / "adj_events.csv", index=False)
print(R.groupby(["horizon", "status"]).size().unstack(fill_value=0).to_string())
print("adjustment events:", len(events))
