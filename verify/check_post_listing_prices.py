"""Spot-check post-listing prices and corporate-action factors against official bhavcopies.

For a sample of IPO x horizon rows, download the bhavcopy for the recorded price_date and
check that the security's raw close equals raw_close. The security is found by ISIN stem
(first 9 characters, which survive the ISIN change on a face-value split) on the same
exchange. Then check that cum_factor equals the product of accepted corporate-action
factors dated after listing and on or before price_date.

Usage:  python verify/check_post_listing_prices.py [--n 40] [--seed 2] [--horizon 1y]
"""
import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import _bhav

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--horizon", default="1y", choices=["1m", "3m", "6m", "1y", "2y", "3y", "to_date"])
    a = ap.parse_args()
    R = pd.read_csv(ROOT / "data/verified/post_listing_returns.csv")
    Dt = pd.read_csv(ROOT / "data/verified/verification_detail.csv", dtype=str)[["issue_id", "nse_isin", "bse_isin"]]
    E = pd.read_csv(ROOT / "data/verified/corporate_action_events_applied.csv")
    E = E[E.accepted]
    R = R[(R.horizon == a.horizon) & R.raw_close.notna()].merge(Dt, on="issue_id", how="left")
    # oversample IPOs that had corporate actions, since those are the risky ones
    has_ca = R.issue_id.isin(E.issue_id)
    sample = pd.concat([R[has_ca].sample(min(has_ca.sum(), a.n // 2), random_state=a.seed),
                        R[~has_ca].sample(min((~has_ca).sum(), a.n - a.n // 2), random_state=a.seed)])
    ok = bad = nf = 0
    for r in sample.itertuples():
        d = date.fromisoformat(r.price_date)
        data = _bhav.nse(d) if r.price_exchange == "NSE" else _bhav.bse(d)
        isin = r.nse_isin if r.price_exchange == "NSE" else r.bse_isin
        if not isinstance(isin, str):  # an equity ISIN is the same on both exchanges
            isin = r.bse_isin if r.price_exchange == "NSE" else r.nse_isin
        if not isinstance(isin, str):
            nf += 1
            print(f"NO ISIN  {r.company_name}")
            continue
        hit = [x for x in data if x["isin"][:9] == isin[:9]]
        # prefer the equity/SME series row
        hit = [x for x in hit if x["series"] in ("EQ", "BE", "BZ", "SM", "ST", "A", "B", "T", "X", "XT", "Z", "M", "MT", "TS")] or hit
        ev = E[(E.issue_id == r.issue_id) & (E.ex_date > r.listing_date) & (E.ex_date <= r.price_date)]
        fac = float(np.prod(ev.factor)) if len(ev) else 1.0
        fac_ok = abs(fac / r.cum_factor - 1) < 1e-4  # rights factors are stored to 5 decimals
        if not hit:
            nf += 1
            print(f"NOT FOUND {r.company_name} {r.price_exchange} {r.price_date} isin={isin}")
            continue
        px_ok = any(abs(x["close"] - r.raw_close) < 0.005 for x in hit)
        if px_ok and fac_ok:
            ok += 1
        else:
            bad += 1
            print(f"MISMATCH {r.company_name} {r.price_date}: raw {r.raw_close} vs exchange {[x['close'] for x in hit]}; "
                  f"cum_factor {r.cum_factor} vs events {fac}")
    print(f"\n{a.horizon}: checked {len(sample)}: {ok} match, {bad} mismatch, {nf} not located")


if __name__ == "__main__":
    main()
