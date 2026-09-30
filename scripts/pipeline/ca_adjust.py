"""Corporate-action guard for estimated share counts.

Kite's adjusted prices reflect splits and bonuses (which change the share count) but also
price-only adjustments (e.g. dividends/rights) that don't. A Kite factor is accepted as a
share multiplier only if it is within 1% of a clean share ratio: an NSE-recorded split/bonus
product, or (a+b)/b for small integers (splits n:1, bonuses a:b with b <= 10).
Otherwise the estimate falls back to the NSE split/bonus product (1.0 when none).
Updates size_and_benchmark.csv in place and writes corporate_actions_check.csv.
"""
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd

S = Path(__file__).parent
OUT = Path("<SITE_REPO>/analysis/ipo-2020-2026/verified")
X = pd.read_csv(S / "size_work4.csv")
CA = pd.read_csv(S / "corp_actions.csv")
A = pd.read_csv(S / "amfi/amfi_cutoffs.csv").dropna(subset=["period_end"])
A["period_end"] = pd.to_datetime(A.period_end); A = A.sort_values("period_end")
nse_mult = 1 / CA[CA.actionType.isin(["SPLIT", "BONUS"])].groupby("issue_id").adjustmentFactor.prod()
X["nse_ca_mult"] = X.issue_id.map(nse_mult).fillna(1.0)
CLEAN = sorted({float(Fraction(a + b, b)) for b in range(1, 11) for a in range(0, 101)} |
               {float(n) for n in range(1, 101)})


def clean(f):
    return any(abs(f / c - 1) < 0.01 for c in CLEAN) or False


def product_clean(f):
    # chains of up to three clean events (e.g. split 5:1 then bonus 1:1 = 10)
    if clean(f):
        return True
    return any(clean(f / c) for c in CLEAN if 1 < c <= f)


est = X.shares_basis.fillna("").str.startswith("current")
cur_shares = X.shares_est * X.adj_factor
kite_ok = X.adj_factor.map(lambda f: pd.notna(f) and (abs(f - 1) < 0.01 or product_clean(f)))
agree_nse = (X.adj_factor / X.nse_ca_mult - 1).abs() < 0.01
X["share_mult_used"] = np.where(kite_ok | agree_nse, X.adj_factor, X.nse_ca_mult)
X["share_mult_basis"] = np.where(agree_nse, "Kite = NSE corporate actions",
                         np.where(kite_ok, "Kite factor (clean split/bonus ratio; NSE list incomplete)",
                                  "NSE corporate actions (Kite factor is a price-only adjustment)"))
X.loc[est, "shares_out"] = cur_shares[est] / X.share_mult_used[est]
X["mcap_issue_cr"] = X.shares_out * X.issue_price_inr / 1e7


def bucket(mc, ld):
    a = A[A.period_end + pd.Timedelta(days=7) <= pd.Timestamp(ld)].iloc[-1]
    return "Large" if mc >= a.rank100 else "Mid" if mc >= a.rank250 else "Small" if mc >= a.rank500 else "Micro"


new = [bucket(m, d) if pd.notna(m) else None for m, d in zip(X.mcap_issue_cr, X.listing_date)]
X["size_bucket_new"] = np.where(X.board_type == "SME Board", "Micro (SME)", new)
X.loc[X.size_bucket_new.isna() | (X.size_bucket_new == "None"), "size_bucket_new"] = "unclassified"
B = pd.read_csv(OUT / "size_and_benchmark.csv")
chg = B.merge(X[["issue_id", "size_bucket_new", "mcap_issue_cr", "shares_out", "share_mult_used", "share_mult_basis", "nse_ca_mult"]],
              on="issue_id", suffixes=("_old", ""))
moved = chg[chg.size_bucket != chg.size_bucket_new]
print("bucket changes:\n", moved[["issue_id", "size_bucket", "size_bucket_new", "share_mult_basis"]].to_string())
print(chg[est.values].share_mult_basis.value_counts().to_string())
chg["size_bucket"] = chg.size_bucket_new
chg = chg.drop(columns=["size_bucket_new", "mcap_issue_cr_old", "shares_out_old"])
chg.to_csv(OUT / "size_and_benchmark.csv", index=False)
CA.to_csv(OUT / "corporate_actions_check.csv", index=False)
