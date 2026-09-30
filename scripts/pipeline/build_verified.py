"""Build the verified IPO cohort from the Codex export + independent exchange checks.

Inputs (scratchpad): verification_merged.csv (bhavcopy + Kite results per issue).
Output: analysis/ipo-2020-2026/verified/ipo_cohort_verified.csv and exclusions.csv
Price rule: NSE listing-day close when the IPO has an NSE first-day row, else BSE.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import numpy as np
import pandas as pd

S = Path(__file__).parent
OUT = Path("<SITE_REPO>/analysis/ipo-2020-2026/verified")
OUT.mkdir(exist_ok=True)
M = pd.read_csv(S / "verification_merged.csv")

# 1. Loose NSE "prev close == issue price" matches can hit bonds or unrelated stocks: keep one only when
#    its close independently equals Codex's close to the paisa; otherwise discard it.
anchor = M.nse_how.fillna("").str.startswith(("new-listing anchor", "new-listing+name")) & ~((M.nse_close - M.codex_close).abs() < 0.005)
for c in ["nse_open", "nse_close", "nse_symbol", "kite_nse_close"]:
    M.loc[anchor, c] = np.nan
# Same rule for fuzzy-name BSE matches, which may also be corroborated by Kite's unadjusted candle.
# ICL Organic Dairy (BSE 542935) is kept: its first trade is on the listing date and the scrip name matches.
bse_loose = M.bse_how.fillna("").str.startswith("new-listing+name")
bse_ok = ((M.bse_close - M.codex_close).abs() < 0.005) | ((M.bse_close - M.kite_bse_close).abs() < 0.005) | M.issue_id.str.startswith("icl-organic")
for c in ["bse_open", "bse_close", "bse_symbol", "kite_bse_close"]:
    M.loc[bse_loose & ~bse_ok, c] = np.nan
for ex, bad in (("nse", anchor), ("bse", bse_loose & ~bse_ok)):
    for c in ["isin", "series", "prev"]:
        M.loc[bad, f"{ex}_{c}"] = np.nan

# 1b. ISIN cross-lookup: an IPO found on one exchange is searched on the other exchange's listing-day
#     bhavcopy by the same ISIN. The row must be a first-day row (NSE prev close = issue price; BSE prev 0).
import csv, io, zipfile  # noqa: E402

CACHE = S / "bhav" / "cache"


def _bhav(ex, d):
    names = [f"nse_u_{d}.zip", f"nse_o_{d}.zip"] if ex == "nse" else [f"bse_n_{d}.csv", f"bse_o_{d}.zip"]
    for n in names:
        p = CACHE / n
        if p.exists() and p.stat().st_size:
            b = p.read_bytes()
            if n.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(b)); b = z.read(z.namelist()[0])
            return list(csv.DictReader(io.StringIO(b.decode("latin-1"))))
    return []


def _pick(row, *keys):
    for k in keys:
        if k in row and row[k] is not None:
            return row[k].strip()
    return ""


for i, r in M.iterrows():
    d = r.listing_date.replace("-", "")
    for ex, other in (("nse", "bse"), ("bse", "nse")):
        isin = r[f"{other}_isin"]
        if pd.notna(r[f"{ex}_close"]) or not isinstance(isin, str):
            continue
        for row in _bhav(ex, d):
            row = {k.strip(): v for k, v in row.items() if k}
            if _pick(row, "ISIN", "ISIN_CODE") != isin:
                continue
            prev = float(_pick(row, "PrvsClsgPric", "PREVCLOSE"))
            if not (prev == 0 or abs(prev - r.issue_price_inr) < 0.005):
                break
            M.loc[i, [f"{ex}_open", f"{ex}_close", f"{ex}_symbol", f"{ex}_series", f"{ex}_isin", f"{ex}_how"]] = [
                float(_pick(row, "OpnPric", "OPEN")), float(_pick(row, "ClsPric", "CLOSE")),
                _pick(row, "TckrSymb", "SYMBOL", "SC_CODE"), _pick(row, "SctySrs", "SERIES", "SC_GROUP"), isin,
                f"isin cross-lookup from {other.upper()}"]
            break

# 2. Exclusions: duplicate records of an IPO already present, and a non-listing.
EXCLUDE = {
    "burger-king-india-42a752": "duplicate of restaurant-brands-asia-1da5f6 (renamed)",
    "indian-railway-finance-d5b79b": "duplicate of irfc-e64083",
    "network-people-a21276": "duplicate of network-people-services-technologies-123316",
    "abans-financial-services-9a62fe": "duplicate of abans-ad9fe1",
    "radiant-cash-mgmt-553813": "duplicate of radiant-cash-management-services-445bb3 (also carried wrong issue price 99)",
    "aeroflex-neu-3e474a": "duplicate of sah-polymers-50a05a (renamed)",
    "ikio-technologies-c95af9": "duplicate of ikio-lighting-bfb508",
    "landmark-global-learning-8bfdd3": "duplicate of landmark-immigration-consultants-fbfa90",
    "monarch-surveyors-1ed2f4": "duplicate of monarch-surveyors-engineering-consultants-d6cdc9",
    "dmr-engineering-7643c9": "duplicate of DMR Hydroengineering (renamed); only one ₹21 listing that day",
    "suumaya-ce25aa": "duplicate of Rangoli Tradecomm (renamed); only one ₹207 listing that day (RTL)",
    "trafiksol-its-technologies-62536b": "no first-day trade on NSE or BSE on the published listing date (reported as cancelled before listing; confirm with the BSE notice before citing)",
}
missing = set(EXCLUDE) - set(M.issue_id)
assert not missing, missing
excl = M[M.issue_id.isin(EXCLUDE)][["issue_id", "company_name", "board_type", "listing_date", "codex_close"]].copy()
excl["reason"] = excl.issue_id.map(EXCLUDE)
X = M[~M.issue_id.isin(EXCLUDE)].copy()

# 3. Manual listing-day lookups where identifiers were missing from the export (read from the cached bhavcopies).
MANUAL = {
    "abans-ad9fe1": ("NSE", 273.00, 218.40, "AHL NSE listing-day row; BSE close 216.05"),
    "sah-polymers-50a05a": ("NSE", 85.00, 89.25, "SAH NSE listing-day row"),
    "ikio-lighting-bfb508": ("NSE", 392.50, 403.85, "IKIO NSE listing-day row; BSE close 403.75"),
    "bombay-metrics-supply-chain-6ab5d0": ("NSE", 98.30, 103.20, "BMETRICS NSE SME listing-day row"),
    "s-v-j-enterprises-8a0d89": ("BSE", 38.00, 36.10, "SVJ BSE SME listing-day row"),
}
X["price_exchange"] = np.where(X.nse_close.notna(), "NSE", np.where(X.bse_close.notna(), "BSE", None))
X["listing_open_inr"] = np.where(X.nse_close.notna(), X.nse_open, X.bse_open)
X["listing_close_inr"] = np.where(X.nse_close.notna(), X.nse_close, X.bse_close)
X["close_basis"] = np.where(X.listing_close_inr.notna(), "exchange bhavcopy", None)
X["note"] = ""
for k, (ex, o, c, n) in MANUAL.items():
    m = X.issue_id == k
    assert m.sum() == 1, k
    X.loc[m, ["price_exchange", "listing_open_inr", "listing_close_inr", "close_basis", "note"]] = [ex, o, c, "exchange bhavcopy (manual lookup)", n]

# 4. Anything still without an exchange row: keep Codex's close only if Kite reproduces it unadjusted.
kite_same = np.where(X.codex_ex == "nse", X.kite_nse_close, X.kite_bse_close)
rest = X.listing_close_inr.isna() & X.codex_close.notna() & (np.abs(kite_same - X.codex_close) < 0.005)
X.loc[rest, "listing_close_inr"] = X.loc[rest, "codex_close"]
X.loc[rest, "price_exchange"] = X.loc[rest, "codex_ex"].str.upper()
X.loc[rest, "close_basis"] = "Codex close reproduced by Kite"
unresolved = X[X.listing_close_inr.isna()]
assert unresolved.empty, unresolved[["issue_id", "company_name"]].to_string()

# 4b. Board from the exchange's own classification: NSE Emerge series SM/ST, BSE SME groups M/MT/TS.
#     Main board otherwise. Overrides the published label where they disagree.
sme_series = X.nse_series.isin(["SM", "ST"]) | X.bse_series.isin(["M", "MT", "TS"])
main_series = X.nse_series.isin(["EQ", "BE", "BZ"]) | X.bse_series.isin(["A", "B", "T", "X", "XT", "Z"])
exch_board = np.where(sme_series, "SME Board", np.where(main_series, "Main Board", None))
flip = pd.notna(exch_board) & (exch_board != X.board_type)
X.loc[flip, "note"] = (X.loc[flip, "note"] + "; board corrected from " + X.loc[flip, "board_type"] + " (exchange series/group)").str.lstrip("; ")
X.loc[flip, "board_type"] = exch_board[flip]
X["venue"] = np.select([X.nse_close.notna() & X.bse_close.notna(), X.nse_close.notna(), X.bse_close.notna()],
                       ["NSE + BSE", "NSE only", "BSE only"], "unknown")
X.loc[X.venue.eq("unknown"), "venue"] = X.price_exchange + " only"

# 5. Returns in integer basis points, half-up, as in the Codex methodology.
def bps(close, issue):
    return int(((Decimal(str(close)) / Decimal(str(issue)) - 1) * 10000).quantize(Decimal(1), ROUND_HALF_UP))

X["return_bps"] = [bps(c, i) for c, i in zip(X.listing_close_inr, X.issue_price_inr)]
X["return_pct"] = X.return_bps / 100
X["listing_year"] = X.listing_date.str[:4].astype(int)
X["codex_status"] = np.where(X.codex_close.isna(), "unpriced in Codex export",
                    np.where((X.codex_close - X.listing_close_inr).abs() < 0.005, "matches", "differs (Codex used BSE close)"))
kite = np.where(X.price_exchange == "NSE", X.kite_nse_close, X.kite_bse_close)
X["kite_check"] = np.where(pd.isna(kite), "no Kite instrument",
                  np.where(np.abs(kite - X.listing_close_inr) < 0.005, "exact", "differs by later split/bonus adjustment"))
cols = ["issue_id", "company_name", "board_type", "listing_date", "listing_year", "issue_price_inr", "venue", "price_exchange",
        "listing_open_inr", "listing_close_inr", "return_bps", "return_pct", "close_basis", "codex_close", "codex_status",
        "nse_symbol", "nse_series", "nse_close", "bse_symbol", "bse_series", "bse_close", "kite_check", "note"]
X[cols].sort_values(["listing_date", "company_name"]).to_csv(OUT / "ipo_cohort_verified.csv", index=False)
excl.sort_values("listing_date").to_csv(OUT / "exclusions.csv", index=False)
print("verified rows", len(X), "excluded", len(excl))
print(X.codex_status.value_counts().to_string())
print(X.kite_check.value_counts().to_string())
print(X.close_basis.value_counts().to_string())
