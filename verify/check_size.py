"""Re-check the Main Board size buckets.

  1. rebuild the AMFI rank cutoffs (market cap at ranks 100 / 250 / 500) from the raw AMFI
     spreadsheets in data/inputs/amfi/ and compare with data/verified/amfi_cutoffs.csv;
  2. recompute every Main Board bucket from mcap_issue_cr and the AMFI list in force at listing
     (latest six-month period ending at least 7 days before the listing date);
  3. for a sample of IPOs whose share count came from NSE's listing-day market-cap file,
     download that day's NSE PR bundle and compare the share count ("Issue Size" column).

Usage:  python verify/check_size.py [--n 30]
"""
import argparse
import io
import re
import zipfile
from pathlib import Path

import pandas as pd
from dateutil import parser as dparser

import _bhav

ROOT = Path(__file__).resolve().parents[1]


def amfi_cutoffs():
    out = []
    for f in sorted((ROOT / "data/inputs/amfi").glob("*.xlsx")):
        raw = pd.read_excel(f, header=None)
        m = re.search(r"ended\s+(\d+\s+\w+\s+\d{4})", str(raw.iloc[0, 0]))
        if not m:
            continue
        hdr = raw.index[raw.apply(lambda r: r.astype(str).str.contains("Sr", case=False).any(), axis=1)][0]
        df = pd.read_excel(f, header=hdr)
        df.columns = [str(c).strip() for c in df.columns]
        rank = [c for c in df.columns if re.match(r"sr", c, re.I)][0]
        avg = [c for c in df.columns if re.search(r"average of all", c, re.I)][-1]
        df = df[pd.to_numeric(df[rank], errors="coerce").notna()]
        r, a = pd.to_numeric(df[rank]), pd.to_numeric(df[avg], errors="coerce")
        out.append({"period_end": str(dparser.parse(m.group(1)).date()), **{f"rank{k}": float(a[r == k].iloc[0]) for k in (100, 250, 500)}})
    return pd.DataFrame(out).sort_values("period_end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    A = amfi_cutoffs()
    P = pd.read_csv(ROOT / "data/verified/amfi_cutoffs.csv").dropna(subset=["period_end"])
    m = A.merge(P, on="period_end", suffixes=("", "_pub"))
    ok = all(abs(m[f"rank{k}"] - m[f"rank{k}_pub"]).max() < 0.01 for k in (100, 250, 500))
    print(f"{'PASS' if ok else 'FAIL'} AMFI cutoffs rebuilt from raw spreadsheets ({len(m)} periods)")

    V = pd.read_csv(ROOT / "data/verified/ipo_cohort_verified.csv")
    B = pd.read_csv(ROOT / "data/verified/size_and_benchmark.csv")
    X = V.merge(B, on="issue_id")
    X = X[X.board_type == "Main Board"]
    A["pe"] = pd.to_datetime(A.period_end)

    def bucket(mc, ld):
        c = A[A.pe + pd.Timedelta(days=7) <= pd.Timestamp(ld)].iloc[-1]
        return "Large" if mc >= c.rank100 else "Mid" if mc >= c.rank250 else "Small" if mc >= c.rank500 else "Micro"
    X["re_bucket"] = [bucket(mc, ld) for mc, ld in zip(X.mcap_issue_cr, X.listing_date)]
    same = (X.re_bucket == X.size_bucket)
    print(f"{'PASS' if same.all() else 'FAIL'} Main Board buckets recomputed: {same.sum()} of {len(X)} agree")
    X["mc_check"] = X.shares_out * X.issue_price_inr / 1e7
    print(f"{'PASS' if ((X.mc_check - X.mcap_issue_cr).abs() < 0.01).all() else 'FAIL'} mcap_issue_cr = shares_out x issue price / 1e7")
    print(X.size_bucket.value_counts().to_string())

    s = X[X.shares_basis == "listing-day NSE MCAP"].sample(min(a.n, (X.shares_basis == "listing-day NSE MCAP").sum()), random_state=3)
    good = bad = 0
    for r in s.itertuples():
        d = pd.Timestamp(r.listing_date)
        b = _bhav._get(f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip", f"pr_{d:%Y%m%d}.zip")
        if not b:
            print(f"  no PR bundle for {r.listing_date}"); bad += 1; continue
        z = zipfile.ZipFile(io.BytesIO(b))
        name = [n for n in z.namelist() if n.upper().startswith("MCAP")][0]
        mc = pd.read_csv(io.BytesIO(z.read(name)), skipinitialspace=True)
        mc.columns = [c.strip() for c in mc.columns]
        row = mc[mc.Symbol.astype(str).str.strip() == r.nse_symbol]
        sh = float(str(row["Issue Size"].iloc[0]).strip()) if len(row) == 1 else None
        if sh is not None and abs(sh - r.shares_out) < 0.5:
            good += 1
        else:
            bad += 1
            print(f"  MISMATCH {r.company_name}: dataset {r.shares_out}, NSE MCAP {sh}")
    print(f"{'PASS' if bad == 0 else 'FAIL'} share counts vs NSE listing-day MCAP: {good} of {len(s)} match")


if __name__ == "__main__":
    main()
