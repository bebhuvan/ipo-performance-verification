"""Independently re-check listing-day prices against the exchanges' own bhavcopies.

For a random sample of IPOs (or all, with --all), download the official bhavcopy for the
listing date on the exchange whose close the dataset uses, find the security, and check:
  1. the close equals listing_close_inr to the paisa;
  2. it is a first-day row (NSE: previous close = issue price; BSE: previous close 0 or = issue price),
     which also confirms the issue price on NSE.
The security is located by ISIN where we recorded one, else by symbol / BSE scrip code.

Usage:  python verify/check_listing_closes.py [--n 60] [--seed 1] [--all]
"""
import argparse
import random
import sys
from datetime import date
from pathlib import Path

import pandas as pd

import _bhav

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--since", help="Check listings strictly after this ISO date")
    a = ap.parse_args()
    V = pd.read_csv(ROOT / "data/verified/ipo_cohort_verified.csv", dtype=str)
    Dt = pd.read_csv(ROOT / "data/verified/verification_detail.csv", dtype=str)[["issue_id", "nse_isin", "bse_isin"]]
    V = V.merge(Dt, on="issue_id", how="left")
    if a.since:
        V = V[V.listing_date > a.since]
    if not a.all:
        random.seed(a.seed)
        # stratify: at least a few from every board x year
        picks = []
        for _, g in V.groupby(["board_type", "listing_year"]):
            picks += random.sample(list(g.index), min(len(g), max(2, a.n // 14)))
        V = V.loc[sorted(set(picks))]
    ok = bad = missing = 0
    rows = []
    for r in V.itertuples():
        d = date.fromisoformat(r.listing_date)
        ex = r.price_exchange
        data = _bhav.nse(d) if ex == "NSE" else _bhav.bse(d)
        isin = (r.nse_isin if ex == "NSE" else r.bse_isin)
        if not isinstance(isin, str):  # an equity ISIN is the same on both exchanges
            isin = r.bse_isin if ex == "NSE" else r.nse_isin
        sym = r.nse_symbol if ex == "NSE" else str(r.bse_symbol).split(".")[0]
        hit = [x for x in data if isinstance(isin, str) and x["isin"] == isin] or \
              [x for x in data if isinstance(sym, str) and sym not in ("", "nan") and sym in (x["symbol"], x["code"])]
        close, issue = float(r.listing_close_inr), float(r.issue_price_inr)
        if len(hit) != 1:
            missing += 1
            rows.append((r.company_name, r.listing_date, ex, "NOT FOUND", f"{len(hit)} rows for isin={isin} sym={sym}"))
            continue
        h = hit[0]
        first_day = (h["prev_close"] == 0) or abs((h["prev_close"] or -1) - issue) < 0.005
        match = abs(h["close"] - close) < 0.005
        if match and first_day:
            ok += 1
        else:
            bad += 1
            rows.append((r.company_name, r.listing_date, ex, "MISMATCH",
                         f"dataset close {close}, exchange close {h['close']}, prev_close {h['prev_close']}, issue {issue}"))
    print(f"checked {len(V)}: {ok} match exactly, {bad} mismatch, {missing} not located")
    for x in rows:
        print(" | ".join(map(str, x)))
    print("\nNote: 'not located' usually means the dataset lacks an identifier for that row (five IPOs were "
          "resolved by manual lookup; see the note column). Check those by hand in the bhavcopy.")
    sys.exit(1 if bad or missing else 0)


if __name__ == "__main__":
    main()
