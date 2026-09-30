"""Market cap at issue price and SEBI/AMFI size bucket for each verified IPO.

Shares outstanding:
  - listing-day NSE MCAP file (in the NSE PR bundle from Feb 2024) -> exact;
  - otherwise current shares (28 Sep 2026 MCAP), traced through NSE symbol changes,
    divided by the cumulative split/bonus factor (NSE listing close / Kite adjusted close) -> estimate.
Bucket: compare mcap at issue price with the AMFI list in force at listing
(latest six-month period ending at least 7 days before listing).
Large = rank 1-100, Mid = 101-250, Small = 251-500, Micro = beyond 500 (convention; SEBI has no micro tier).
"""
import io, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

S = Path(__file__).parent
ROOT = Path("<SITE_REPO>")
PR = ROOT / "data/raw/nse_pr"
V = pd.read_csv(ROOT / "analysis/ipo-2020-2026/verified/ipo_cohort_verified.csv")
K = pd.read_csv(S / "kite_verification.csv")[["issue_id", "kite_nse_close"]]
V = V.merge(K, on="issue_id", how="left")


def mcap_file(day: str) -> pd.DataFrame | None:
    p = PR / f"{day}.zip"
    if not p.exists():
        return None
    z = zipfile.ZipFile(p)
    names = [n for n in z.namelist() if n.upper().startswith("MCAP")]
    if not names:
        return None
    m = pd.read_csv(io.BytesIO(z.read(names[0])), skipinitialspace=True)
    m.columns = [c.strip() for c in m.columns]
    m["Symbol"] = m.Symbol.astype(str).str.strip()
    m["shares"] = pd.to_numeric(m["Issue Size"].astype(str).str.strip(), errors="coerce")
    return m.drop_duplicates("Symbol").set_index("Symbol")


# symbol changes: follow old -> new chains to the current symbol
sc = pd.read_csv(S / "symbolchange.csv", header=None, names=["name", "old", "new", "date"], skipinitialspace=True)
sc = sc.assign(old=sc.old.str.strip(), new=sc.new.str.strip(), date=pd.to_datetime(sc.date.str.strip(), format="%d-%b-%Y", errors="coerce"))


def current_symbol(sym: str, since: str) -> str:
    seen = set()
    while sym not in seen:
        seen.add(sym)
        nxt = sc[(sc.old == sym) & (sc.date >= pd.Timestamp(since))].sort_values("date")
        if nxt.empty:
            break
        sym = nxt.new.iloc[0]
    return sym


LATEST = mcap_file("2026-09-28")
cache: dict[str, pd.DataFrame | None] = {}
rows = []
for r in V.itertuples():
    rec = {"issue_id": r.issue_id, "shares_basis": None, "shares_out": np.nan}
    sym = r.nse_symbol if isinstance(r.nse_symbol, str) else None
    if sym and r.listing_date >= "2024-02-01":
        if r.listing_date not in cache:
            cache[r.listing_date] = mcap_file(r.listing_date)
        m = cache[r.listing_date]
        if m is not None and sym in m.index:
            rec.update(shares_out=m.at[sym, "shares"], shares_basis="listing-day NSE MCAP")
    # estimate from current shares for every NSE-listed IPO (also used to validate on the exact set)
    if sym:
        cur = current_symbol(sym, r.listing_date)
        factor = 1.0
        if pd.notna(r.kite_nse_close) and r.kite_nse_close > 0 and pd.notna(r.nse_close):
            factor = r.nse_close / r.kite_nse_close
        if cur in LATEST.index and pd.notna(r.kite_nse_close):
            rec["shares_est"] = LATEST.at[cur, "shares"] / factor
            rec["current_symbol"] = cur
            rec["adj_factor"] = round(factor, 4)
    rows.append(rec)
X = V.merge(pd.DataFrame(rows), on="issue_id")

# validate the estimate where the exact listing-day count is known
val = X[X.shares_basis.notna() & X.shares_est.notna()]
err = (val.shares_est / val.shares_out - 1) * 100
print(f"estimate vs exact (n={len(val)}): median abs err {err.abs().median():.2f}%, 90th pct {err.abs().quantile(.9):.2f}%, >10%: {(err.abs()>10).sum()}")

use_est = X.shares_basis.isna() & X.shares_est.notna()
X.loc[use_est, "shares_out"] = X.loc[use_est, "shares_est"]
X.loc[use_est, "shares_basis"] = "current NSE shares / split-bonus factor (estimate)"
X["mcap_issue_cr"] = X.shares_out * X.issue_price_inr / 1e7

# AMFI list in force at listing
A = pd.read_csv(S / "amfi/amfi_cutoffs.csv").dropna(subset=["period_end"])
A["period_end"] = pd.to_datetime(A.period_end)
A = A.sort_values("period_end")


def bucket(row):
    if pd.isna(row.mcap_issue_cr):
        return pd.Series({"amfi_period_end": None, "size_bucket": None})
    a = A[A.period_end + pd.Timedelta(days=7) <= pd.Timestamp(row.listing_date)].iloc[-1]
    mc = row.mcap_issue_cr
    b = "Large" if mc >= a.rank100 else "Mid" if mc >= a.rank250 else "Small" if mc >= a.rank500 else "Micro"
    return pd.Series({"amfi_period_end": a.period_end.date(), "size_bucket": b})


X = pd.concat([X, X.apply(bucket, axis=1)], axis=1)
X.to_csv(S / "size_work.csv", index=False)
print(X.shares_basis.value_counts(dropna=False).to_string())
print(pd.crosstab([X.board_type], X.size_bucket.fillna("unknown")).to_string())
print(pd.crosstab([X.board_type, X.listing_year], X.size_bucket.fillna("unknown")).to_string())
